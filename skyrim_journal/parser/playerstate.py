"""Decoders for the player reference (ACHR 0x14) change form.

Everything here was found empirically on one real Skyrim SE save and cross-checked:

* Actor values: a vsval-counted list of (u32 actor-value index, f32 value). Indices 6-23 are
  the 18 skills (OneHanded=6 ... Enchanting=23), 24-26 are Health/Magicka/Stamina. The
  sum of (value - race base) over the skills equals the "Skill Increases" misc stat, and
  the three attributes sum to 300 + 10 per level gained. These are the saved base values,
  i.e. they include level-ups but not temporary buffs.
* Skill block: ``f32 cur_exp, f32 lvlup_exp`` (equal to the header values), ``u32 18``, then
  18 x (f32 level, f32 xp, f32 threshold, u32 0). Levels equal the actor-value list.
* Inventory: vsval count, then per item RefID(3) + i32 count + vsval list-count, each list =
  vsval extra-count + (u8 type + type-specific payload). The extra-data payload sizes below
  were inferred from one save: a walk with them lands exactly on the end of all 38 items.
  An unknown extra type makes the walk fail, in which case nothing is returned.
* Perk-shaped list: vsval count + count x (RefID(3), u8 rank). Matches a unique list of 102
  entries; its identification as the perk list is NOT confirmed by names.
"""
from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass, field

from .body import PLAYER_REFR, SaveBody, payload_decompress
from .refs import read_refid

SKILL_NAMES = ["OneHanded", "TwoHanded", "Marksman", "Block", "Smithing", "HeavyArmor",
               "LightArmor", "Pickpocket", "Lockpicking", "Sneak", "Alchemy", "Speechcraft",
               "Alteration", "Conjuration", "Destruction", "Illusion", "Restoration",
               "Enchanting"]
FIRST_SKILL_AV = 6
ATTRIBUTE_AVS = {"Health": 24, "Magicka": 25, "Stamina": 26}
GOLD, LOCKPICK = 0x0000000F, 0x0000000A
EXTRA_WORN = 0x16


class _Bad(Exception):
    pass


def _vsval(buf: bytes, k: int) -> tuple[int, int]:
    """Return (value, next position)."""
    if k >= len(buf):
        raise _Bad("vsval past end")
    w = buf[k] & 3
    if w == 3:
        raise _Bad("invalid vsval")
    sz = 1 << w
    if k + sz > len(buf):
        raise _Bad("vsval past end")
    return int.from_bytes(buf[k:k + sz], "little") >> 2, k + sz


# Extra-data payload length by type byte, given (buffer, position of first payload byte).
def _fixed(n):
    return lambda buf, k: n


def _vs_list(item_size):
    def f(buf, k):
        n, k2 = _vsval(buf, k)
        return (k2 - k) + n * item_size
    return f


EXTRA_SIZES = {
    0x16: _fixed(0),     # flag only; present on 7 weapon/armour-range items (worn, inferred)
    0x1C: _fixed(3),     # RefID
    0x24: _fixed(2),     # u16 (equals the stack count on the 39-stack)
    0x88: _vs_list(7),   # vsval n x (RefID, u32): looks like quest alias instances
    0x8E: _fixed(3),     # RefID
    0x99: _fixed(10),    # 10 opaque bytes (zeros + RefID + i32 in the sample)
    0x9F: _fixed(6),     # 6 opaque bytes
}


@dataclass
class InventoryItem:
    form_id: int
    count: int
    extra_types: list[int]

    @property
    def worn(self) -> bool:
        return EXTRA_WORN in self.extra_types


@dataclass
class PlayerState:
    actor_values: dict[int, float] = field(default_factory=dict)  # AV index -> value
    skill_block: list[tuple[float, float, float]] | None = None    # (level, xp, threshold)
    inventory: list[InventoryItem] | None = None
    inventory_is_partial: bool = False   # only gold/lockpicks recovered
    perks: list[tuple[int, int]] | None = None                     # (form id, rank)

    @property
    def skills(self) -> dict[str, float]:
        if not all(FIRST_SKILL_AV + i in self.actor_values for i in range(18)):
            return {}
        return {n: self.actor_values[FIRST_SKILL_AV + i] for i, n in enumerate(SKILL_NAMES)}

    @property
    def attributes(self) -> dict[str, float]:
        return {n: self.actor_values[i] for n, i in ATTRIBUTE_AVS.items()
                if i in self.actor_values}

    def gold(self) -> int | None:
        return self._count_of(GOLD)

    def lockpicks(self) -> int | None:
        return self._count_of(LOCKPICK)

    def _count_of(self, fid: int) -> int | None:
        if self.inventory is None:
            return None
        return sum(i.count for i in self.inventory if i.form_id == fid) or None


def find_actor_values(data: bytes) -> dict[int, float]:
    """Locate the run of 18 consecutive (6..23, f32) pairs and read it plus 24-26 if present."""
    needle = struct.pack("<I", FIRST_SKILL_AV)
    hits = []
    for m in re.finditer(re.escape(needle), data):
        o = m.start()
        if o + 8 * 18 > len(data):
            continue
        ok = True
        for j in range(18):
            idx, v = struct.unpack_from("<If", data, o + 8 * j)
            if idx != FIRST_SKILL_AV + j or not math.isfinite(v) or not 0 <= v <= 1000:
                ok = False
                break
        if ok:
            hits.append(o)
    if len(hits) != 1:      # none, or ambiguous: refuse to guess
        return {}
    o = hits[0]
    out: dict[int, float] = {}
    j = 0
    while o + 8 * (j + 1) <= len(data):
        idx, v = struct.unpack_from("<If", data, o + 8 * j)
        if idx != FIRST_SKILL_AV + j or not math.isfinite(v):
            break
        out[idx] = v
        j += 1
        if idx == 26:
            break
    return out


def find_skill_block(data: bytes, cur_exp: float, lvlup_exp: float,
                     levels: dict[str, float] | None = None) -> list[tuple[float, float, float]] | None:
    sig = struct.pack("<ffI", cur_exp, lvlup_exp, 18)
    hits = []
    for m in re.finditer(re.escape(sig), data):
        o = m.end()
        if o + 16 * 18 > len(data):
            continue
        rows = [struct.unpack_from("<3f", data, o + 16 * i) for i in range(18)]
        if all(math.isfinite(x) for r in rows for x in r) and all(0 <= r[0] <= 1000 for r in rows):
            hits.append(rows)
    if len(hits) != 1:
        return None
    rows = hits[0]
    if levels and any(abs(rows[i][0] - levels[n]) > 1e-3 for i, n in enumerate(SKILL_NAMES)):
        return None   # disagrees with the actor-value list: do not trust
    return rows


def _walk_items(data: bytes, k: int, n: int, form_ids: list[int]) -> tuple[list[InventoryItem], int]:
    items = []
    for _ in range(n):
        if k + 8 > len(data):
            raise _Bad("item past end")
        fid = read_refid(data[k:k + 3], form_ids)
        (cnt,) = struct.unpack_from("<i", data, k + 3)
        if fid is None or cnt <= 0:
            raise _Bad("bad item")
        k += 7
        nl, k = _vsval(data, k)
        types: list[int] = []
        for _ in range(nl):
            ne, k = _vsval(data, k)
            for _ in range(ne):
                if k >= len(data):
                    raise _Bad("extra past end")
                t = data[k]
                k += 1
                size = EXTRA_SIZES.get(t)
                if size is None:
                    raise _Bad(f"unknown extra type 0x{t:02X}")
                k += size(data, k)
                types.append(t)
        if k > len(data):
            raise _Bad("extra overrun")
        items.append(InventoryItem(fid, cnt, types))
    return items, k


def find_inventory(data: bytes, form_ids: list[int], max_scan: int = 16384
                   ) -> list[InventoryItem] | None:
    """Find the vsval-counted inventory list near the start of the player ACHR payload.

    Accepted when the full walk of ``count`` items succeeds and either contains gold or has
    at least 8 items; the longest such candidate wins."""
    best: list[InventoryItem] | None = None
    for x in range(0, min(len(data), max_scan)):
        try:
            n, k0 = _vsval(data, x)
            if n < 1 or n > 2000:
                continue
            items, _ = _walk_items(data, k0, n, form_ids)
        except (_Bad, struct.error):
            continue
        if not (any(i.form_id == GOLD for i in items) or n >= 8):
            continue
        if best is None or len(items) > len(best):
            best = items
    return best


def find_gold_lockpicks(data: bytes, form_ids: list[int]) -> list[InventoryItem]:
    """Fallback when the full walk fails: look for the exact byte shape of the two entries
    ``RefID i32 count u8 0`` and accept only a single match each."""
    out = []
    for fid in (GOLD, LOCKPICK):
        pat = re.compile(re.escape(bytes([0x40, 0, fid])) + rb"(.{4})\x00", re.S)
        ms = list(pat.finditer(data))
        if len(ms) == 1:
            (c,) = struct.unpack("<i", ms[0].group(1))
            if c > 0:
                out.append(InventoryItem(fid, c, []))
    return out


def find_perk_list(data: bytes, form_ids: list[int], plugin_count: int) -> list[tuple[int, int]] | None:
    """The unique vsval-counted list of (RefID, rank 1-5) with at least 10 distinct entries."""
    hits = []
    for x in range(0, len(data) - 10):
        try:
            n, k0 = _vsval(data, x)
        except _Bad:
            continue
        if not 10 <= n <= 600 or k0 + 4 * n > len(data):
            continue
        seen: set[int] = set()
        out = []
        for j in range(n):
            p = k0 + 4 * j
            fid = read_refid(data[p:p + 3], form_ids)
            rank = data[p + 3]
            top = None if fid is None else fid >> 24
            if fid is None or rank not in range(1, 6) or fid in seen or (
                    top is not None and top >= plugin_count and top < 0xFE):
                break
            seen.add(fid)
            out.append((fid, rank))
        else:
            hits.append(out)
    return hits[0] if len(hits) == 1 else None


def parse_player_state(body: SaveBody, compression_type: int, cur_exp: float,
                       lvlup_exp: float) -> PlayerState | None:
    cf = next((c for c in body.change_forms if c.form_type == 1 and c.form_id == PLAYER_REFR), None)
    if cf is None:
        return None
    data, _, _ = payload_decompress(cf, compression_type)
    if data is None:
        return None
    st = PlayerState()
    st.actor_values = find_actor_values(data)
    st.skill_block = find_skill_block(data, cur_exp, lvlup_exp, st.skills or None)
    st.inventory = find_inventory(data, body.form_id_array)
    if st.inventory is None:
        part = find_gold_lockpicks(data, body.form_id_array)
        if part:
            st.inventory, st.inventory_is_partial = part, True
    st.perks = find_perk_list(data, body.form_id_array, len(body.plugins))
    return st
