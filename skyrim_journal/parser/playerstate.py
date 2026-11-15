"""Decoders for the player reference (ACHR 0x14) change form.

Everything here was found empirically on one real Skyrim SE save and cross-checked:

* Actor values: a vsval-counted list of (u32 actor-value index, f32 value). Indices 6-23 are
  the 18 skills (OneHanded=6 ... Enchanting=23), 24-26 are Health/Magicka/Stamina. The
  sum of (value - race base) over the skills equals the "Skill Increases" misc stat, and
  the three attributes sum to 300 + 10 per level gained. These are the saved base values,
  i.e. they include level-ups but not temporary buffs.
* Skill block: ``f32 cur_exp, f32 lvlup_exp`` (equal to the header values), ``u32 18``, then
  18 x (f32 level, f32 xp, f32 threshold, u32 0). Levels equal the actor-value list in save 5
  but can lag it in save 6 (see ``find_skill_block``).
* Inventory: vsval count, then per item RefID(3) + i32 count + vsval list-count, each list =
  vsval extra-count + (u8 type + type-specific payload). The extra-data payload sizes below
  were inferred from two saves of one character: a walk with them lands exactly on the end of
  all 38 (save 5) and 49 (save 6) items, and what follows the list is the same structure in
  both. An extra type with an unknown size does not abort the walk: the walker resynchronises
  (see ``_walk_items``) and flags the item ``details_incomplete``. Only if that fails too is
  nothing returned.
* Perk-shaped list: vsval count + count x (RefID(3), u8 rank). Matches a unique list of 102
  entries; its identification as the perk list is NOT confirmed by names.
"""
from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass, field
from typing import Callable

from .body import PLAYER_REFR, SaveBody, payload_decompress
from .refs import read_refid

SKILL_NAMES = ["OneHanded", "TwoHanded", "Marksman", "Block", "Smithing", "HeavyArmor",
               "LightArmor", "Pickpocket", "Lockpicking", "Sneak", "Alchemy", "Speechcraft",
               "Alteration", "Conjuration", "Destruction", "Illusion", "Restoration",
               "Enchanting"]
FIRST_SKILL_AV = 6
ATTRIBUTE_AVS = {"Health": 24, "Magicka": 25, "Stamina": 26}
MAX_BLOCK_LEVEL_LAG = 10
GOLD, LOCKPICK = 0x0000000F, 0x0000000A
EXTRA_WORN = 0x16
CARRYABLE_TYPES = frozenset({"WEAP", "ARMO", "AMMO", "ALCH", "INGR", "BOOK", "MISC", "KEYM",
                             "SLGM", "SCRL", "LIGH"})

# Optional oracle: form id -> True (known carryable record type), False (known to be something
# else, e.g. an NPC or a cell) or None (not known).
ItemKind = Callable[[int], "bool | None"]


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
    0x24: _fixed(2),     # u16 equal to the stack count (39 and 44 arrows, two saves)
    0x27: _fixed(4),     # f32 (224.47 in save 6). Only size 4 walks all 49 items; 12 comes close
                         # but fails. Probably a charge value, unconfirmed (item not in names)
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
    payloads: list[bytes] = field(default_factory=list)   # raw payload per decoded extra
    details_incomplete: bool = False   # an unknown extra type was skipped by resynchronising

    @property
    def worn(self) -> bool:
        return EXTRA_WORN in self.extra_types

    def payload(self, extra_type: int) -> bytes | None:
        for t, p in zip(self.extra_types, self.payloads):
            if t == extra_type:
                return p
        return None


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
    # The block's level field equals the actor value in save 5 but lags it in save 6 (by 1-3
    # levels on 5 skills, the ones that levelled since save 5; xp and threshold are current).
    # A block that is ahead of the actor values, or lags by more than MAX_BLOCK_LEVEL_LAG, is
    # not trusted.
    if levels and any(not -1e-3 <= levels[n] - rows[i][0] <= MAX_BLOCK_LEVEL_LAG
                      for i, n in enumerate(SKILL_NAMES)):
        return None
    return rows


class _Unknown(Exception):
    """An extra type with no known size; ``k`` is the position just after the type byte."""

    def __init__(self, item: InventoryItem, k: int, t: int):
        super().__init__(f"unknown extra type 0x{t:02X}")
        self.item, self.k, self.type = item, k, t


MAX_RESYNC_SKIP = 64     # longest unknown payload (plus any later extras of that item) searched
MAX_RESYNC_DEPTH = 4     # unknown-type items tolerated in one list
MIN_ITEMS_BEFORE_NESTED = 3   # a list that has not yet walked 3 items gets no nested resync


# What follows the inventory list in the player record (both saves): RefID(3), u32 2, then a
# u16-length string "BShkbAnimationGraph". Once an extra type has been skipped the walk may
# line up on a wrong offset and keep parsing garbage that happens to look like items, so a
# resynchronised walk must additionally end exactly in front of this structure. If another
# game version lays it out differently, resynchronisation fails and the caller falls back.
POST_LIST_MARKER = b"\x13\x00BShkbAnimationGraph"
POST_LIST_GAP = 7        # RefID(3) + u32 between the end of the list and the length prefix


def _list_end_anchored(data: bytes, end: int) -> bool:
    return data.startswith(POST_LIST_MARKER, end + POST_LIST_GAP)


def _plausible_head(data: bytes, k: int, form_ids: list[int], plugin_count: int | None,
                    kind: ItemKind | None = None) -> bool:
    """Cheap test of the 7 bytes that start an item: resolvable RefID, positive count."""
    if k + 8 > len(data):
        return False
    fid = read_refid(data[k:k + 3], form_ids)
    if fid is None or int.from_bytes(data[k + 3:k + 7], "little", signed=True) <= 0:
        return False
    top = fid >> 24
    if plugin_count is not None and plugin_count <= top < 0xFE:
        return False
    return kind is None or kind(fid) is not False


def _walk_one(data: bytes, k: int, form_ids: list[int], plugin_count: int | None,
              kind: ItemKind | None = None) -> tuple[InventoryItem, int]:
    if k + 8 > len(data):
        raise _Bad("item past end")
    fid = read_refid(data[k:k + 3], form_ids)
    (cnt,) = struct.unpack_from("<i", data, k + 3)
    if fid is None or cnt <= 0:
        raise _Bad("bad item")
    top = fid >> 24
    if plugin_count is not None and top >= plugin_count and top < 0xFE:
        raise _Bad("form id from a plugin not in the load order")
    if kind is not None and kind(fid) is False:
        raise _Bad("form is not a carryable record type")
    k += 7
    item = InventoryItem(fid, cnt, [])
    nl, k = _vsval(data, k)
    for _ in range(nl):
        ne, k = _vsval(data, k)
        for _ in range(ne):
            if k >= len(data):
                raise _Bad("extra past end")
            t = data[k]
            k += 1
            size = EXTRA_SIZES.get(t)
            if size is None:
                item.details_incomplete = True
                raise _Unknown(item, k, t)
            sz = size(data, k)
            if k + sz > len(data):
                raise _Bad("extra overrun")
            item.extra_types.append(t)
            item.payloads.append(data[k:k + sz])
            k += sz
    return item, k


def _walk_items(data: bytes, k: int, n: int, form_ids: list[int],
                plugin_count: int | None = None, allowed: int = MAX_RESYNC_DEPTH,
                _cache: dict | None = None, _seen: int = 0
                ) -> tuple[list[InventoryItem], int | None]:
    """Walk ``n`` items from ``k``; return (items, end position). Raises ``_Bad`` on failure.

    An extra type of unknown size is handled by resynchronisation: the offsets within
    ``MAX_RESYNC_SKIP`` bytes of the unknown type are tried as the start of the next item, and
    one is accepted only when *all* the remaining items walk cleanly from it (every RefID
    resolves and is from a loaded plugin, positive counts, known extra types or, while
    ``allowed`` lasts, further resynchronisation). The affected item is kept with
    ``details_incomplete`` set. Among the offsets that work the one skipping the fewest
    items wins, then the one with the most items the ``kind`` oracle knows to be carryable;
    if none works, or the best ones disagree, the walk fails. When the unknown type is in the last item nothing can validate the end, so
    the end position is ``None``. ``_cache`` memoises item parses and sub-walks."""
    if _cache is None:
        _cache = {}
    key = (k, n, allowed, _seen >= MIN_ITEMS_BEFORE_NESTED)
    memo = _cache.setdefault("walk", {})
    if key in memo:
        if memo[key] is None:
            raise _Bad("memoised failure")
        return memo[key]
    try:
        res = _walk_items_uncached(data, k, n, form_ids, plugin_count, allowed, _cache, _seen)
    except _Bad:
        memo[key] = None
        raise
    memo[key] = res
    return res


def _walk_items_uncached(data, k, n, form_ids, plugin_count, allowed, _cache, _seen):
    one = _cache.setdefault("one", {})
    kind = _cache.get("kind")
    items: list[InventoryItem] = []
    for i in range(n):
        hit = one.get(k)
        if hit is None:
            try:
                hit = one[k] = _walk_one(data, k, form_ids, plugin_count, kind)
            except _Unknown as ex:
                hit = one[k] = (ex.item, ex.k, ex.type)
            except (_Bad, struct.error):
                hit = one[k] = False
        if hit is False:
            raise _Bad("bad item")
        if len(hit) == 2:
            item, k = hit
            items.append(item)
            continue
        # unknown extra type
        if allowed <= 0:
            raise _Bad("too many unknown extra types")
        item, after_type, _t = hit
        items.append(item)
        rest = n - i - 1
        if rest == 0:
            return items, None
        # Every offset from which the rest of the list walks and ends in front of the post-list
        # marker is a candidate. A wrong alignment re-segments real items into garbage that
        # needs more skipped types than the true one, so the candidate with the fewest skipped
        # items wins, ties going to the nearest offset. Further unknown types in the rest are
        # allowed only once the list has walked a few items, so that garbage starts do not
        # search deeply.
        left = allowed - 1 if _seen + i >= MIN_ITEMS_BEFORE_NESTED else 0
        cands: list[tuple[tuple[int, int], tuple[list[InventoryItem], int | None]]] = []
        for e in range(after_type, min(after_type + MAX_RESYNC_SKIP, len(data)) + 1):
            if not _plausible_head(data, e, form_ids, plugin_count, kind):
                continue
            try:
                tail = _walk_items(data, e, rest, form_ids, plugin_count, left,
                                   _cache, _seen + i + 1)
            except (_Bad, struct.error):
                continue
            if tail[1] is not None and not _list_end_anchored(data, tail[1]):
                continue
            cands.append(((sum(x.details_incomplete for x in tail[0]),
                           -sum(1 for x in tail[0] if kind is not None and kind(x.form_id))),
                          tail))
        if not cands:
            raise _Bad("cannot resynchronise after unknown extra type")
        top = min(c[0] for c in cands)
        tails = [c[1] for c in cands if c[0] == top]
        if any(t[0] != tails[0][0] for t in tails[1:]):
            raise _Bad("ambiguous resynchronisation")
        return items + tails[0][0], tails[0][1]
    return items, k


def find_inventory(data: bytes, form_ids: list[int], max_scan: int = 65536,
                   plugin_count: int | None = None, item_kind: ItemKind | None = None
                   ) -> list[InventoryItem] | None:
    """Find the vsval-counted inventory list in the player ACHR payload (no fixed offset: every
    position of the first ``max_scan`` bytes is tried as the list's count).

    A candidate is accepted when the walk of exactly ``count`` items succeeds (with
    resynchronisation over unknown extra types, see ``_walk_items``) and it either contains
    gold, or has at least 8 items and no skipped extras. Candidates with skipped extras must
    contain gold and have no more than half of their items affected. The longest accepted
    candidate wins (a start inside the real list yields a shorter one), ties going to the one
    with fewer incomplete items."""
    best: list[InventoryItem] | None = None
    best_key: tuple[int, int] | None = None
    cache: dict = {"kind": item_kind}
    for x in range(0, min(len(data), max_scan)):
        try:
            n, k0 = _vsval(data, x)
            if n < 1 or n > 2000 or not _plausible_head(data, k0, form_ids, plugin_count,
                                                                  item_kind):
                continue
            items, _ = _walk_items(data, k0, n, form_ids, plugin_count, MAX_RESYNC_DEPTH, cache)
        except (_Bad, struct.error):
            continue
        has_gold = any(i.form_id == GOLD for i in items)
        bad = sum(1 for i in items if i.details_incomplete)
        if bad:
            if not has_gold or bad * 2 > len(items):
                continue
        elif not (has_gold or n >= 8):
            continue
        key = (len(items), -bad)
        if best_key is None or key > best_key:
            best, best_key = items, key
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
                       lvlup_exp: float, item_kind: ItemKind | None = None
                       ) -> PlayerState | None:
    cf = next((c for c in body.change_forms if c.form_type == 1 and c.form_id == PLAYER_REFR), None)
    if cf is None:
        return None
    data, _, _ = payload_decompress(cf, compression_type)
    if data is None:
        return None
    st = PlayerState()
    st.actor_values = find_actor_values(data)
    st.skill_block = find_skill_block(data, cur_exp, lvlup_exp, st.skills or None)
    st.inventory = find_inventory(data, body.form_id_array, plugin_count=len(body.plugins),
                                  item_kind=item_kind)
    if st.inventory is None:
        part = find_gold_lockpicks(data, body.form_id_array)
        if part:
            st.inventory, st.inventory_is_partial = part, True
    st.perks = find_perk_list(data, body.form_id_array, len(body.plugins))
    return st
