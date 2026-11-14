"""Player base record (NPC_ 0x7) change form decoder.

Layout verified empirically against a real save (sections appear in this on-disk order,
which is NOT ascending flag order): ACBS 0x2 (24 bytes), FACTIONS 0x40 (vsval count +
RefID(3)+int8 rank), AIDATA 0x8 (20 bytes), FULLNAME 0x20 (wstring), SKILLS 0x200
(52 bytes), then 0x800/0x02000000 data (RACE RefID + undecoded face blob).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from .errors import SaveParseError
from .reader import Reader

F_ACBS, F_AIDATA, F_FULLNAME, F_FACTIONS, F_SKILLS = 0x2, 0x8, 0x20, 0x40, 0x200
F_FACE, F_RACE = 0x800, 0x02000000
SKILL_NAMES = ["OneHanded", "TwoHanded", "Marksman", "Block", "Smithing", "HeavyArmor",
               "LightArmor", "Pickpocket", "Lockpicking", "Sneak", "Alchemy", "Speechcraft",
               "Alteration", "Conjuration", "Destruction", "Illusion", "Restoration", "Enchanting"]


def read_vsval(r: Reader, field: str) -> int:
    first = r.buf[r.pos] if r.pos < len(r.buf) else 0
    width = first & 3
    if width == 3:
        raise SaveParseError(f"invalid vsval width in {field}")
    return (r.u8, r.u16, r.u32)[width](field) >> 2


@dataclass
class PlayerBase:
    acbs_flags: int
    magicka_offset: int
    stamina_offset: int
    level: int
    calc_min: int
    calc_max: int
    speed_mult: int
    disposition_base: int
    template_flags: int
    health_offset: int
    bleedout_override: int
    factions: list[tuple[int, int]]          # (resolved form id or raw ref, rank)
    ai_data: bytes                           # 20 raw bytes (layout unconfirmed)
    name: str
    skills: dict[str, int]                   # base values as stored in the NPC_ record
    skill_offsets: dict[str, int]
    base_health: int
    base_magicka: int
    base_stamina: int
    race_ref: int | None                     # resolved form id
    consumed: int = 0
    total: int = 0
    face_blob: bytes = field(default=b"", repr=False)  # undecoded tail (face/head parts)

    @property
    def undecoded_bytes(self) -> int:
        return self.total - self.consumed


def parse_player_base(data: bytes, flags: int, form_ids: list[int]) -> PlayerBase:
    from .refs import read_refid
    need = F_ACBS | F_FACTIONS | F_AIDATA | F_FULLNAME | F_SKILLS
    if flags & need != need:
        raise SaveParseError(f"player NPC_ changeFlags 0x{flags:08X} lack expected sections")
    r = Reader(data, 0, "NPC_ payload")
    acbs = struct.unpack("<I10H", r.take(24, "ACBS"))
    n = read_vsval(r, "faction count")
    factions = []
    for i in range(n):
        fid = read_refid(r.take(3, "faction refid"), form_ids)
        rank = struct.unpack("<b", r.take(1, "faction rank"))[0]
        factions.append((fid, rank))
    ai = r.take(20, "AIDATA")
    name = r.wstring("FULLNAME")
    vals = list(r.take(18, "skill values"))
    offs = list(r.take(18, "skill offsets"))
    hp, mp, sp = struct.unpack("<3H", r.take(6, "base attributes"))
    r.take(2 + 4 + 1 + 3, "skills trailer (unused/far-model dist/geared-up)")
    consumed = r.pos
    race = None
    if flags & F_RACE:
        race = read_refid(r.take(3, "race refid"), form_ids)
        consumed = r.pos
    return PlayerBase(*acbs, factions, ai, name, dict(zip(SKILL_NAMES, vals)),
                      dict(zip(SKILL_NAMES, offs)), hp, mp, sp, race, consumed, len(data),
                      data[consumed:])
