"""Global data tables (file location table 1-3) and decoders for the verified types."""
from __future__ import annotations

import struct
from dataclasses import dataclass

from .body import SaveBody
from .errors import SaveParseError
from .player import read_vsval
from .reader import Reader
from .refs import read_refid

STAT_CATEGORIES = {0: "General", 1: "Quest", 2: "Combat", 3: "Magic", 4: "Crafting",
                   5: "Crime", 6: "DLC"}
# Verified on a real save: 0x35..0x3A decode to 201 / 6 / 12 / 8.5 / 6.36 / 20.0.
KNOWN_GLOBALS = {0x35: "GameYear", 0x36: "GameMonth", 0x37: "GameDay", 0x38: "GameHour",
                 0x39: "GameDaysPassed", 0x3A: "TimeScale"}


@dataclass
class GlobalEntry:
    table: int
    type: int
    offset: int   # body index of data
    length: int


@dataclass
class MiscStat:
    name: str
    category: int
    value: int

    @property
    def category_name(self) -> str:
        return STAT_CATEGORIES.get(self.category, str(self.category))


@dataclass
class PlayerLocation:
    next_object_id: int
    worldspace: int | None
    coord_x: int
    coord_y: int
    worldspace2: int | None
    pos: tuple[float, float, float]


def walk_tables(body: SaveBody) -> list[GlobalEntry]:
    t, base, buf = body.table, body.offset_base, body.raw
    out = []
    for n, (off, cnt) in enumerate([(t["globalDataTable1Offset"], t["globalDataTable1Count"]),
                                    (t["globalDataTable2Offset"], t["globalDataTable2Count"]),
                                    (t["globalDataTable3Offset"], t["globalDataTable3Count"])], 1):
        if not cnt:
            continue
        r = Reader(buf, off - base, "decompressed body")
        for _ in range(cnt):
            typ, ln = r.u32("global data type"), r.u32("global data length")
            out.append(GlobalEntry(n, typ, r.pos, ln))
            r.take(ln, f"global data type {typ}")
    return out


def _find(body: SaveBody, typ: int, table: int = 1) -> GlobalEntry | None:
    return next((e for e in walk_tables(body) if e.type == typ and e.table == table), None)


def parse_misc_stats(body: SaveBody) -> list[MiscStat]:
    e = _find(body, 0)
    if e is None:
        return []
    r = Reader(body.raw[e.offset:e.offset + e.length], 0, "misc stats")
    stats = []
    for _ in range(r.u32("stat count")):
        name = r.wstring("stat name")
        cat = r.u8("stat category")
        stats.append(MiscStat(name, cat, struct.unpack("<i", r.take(4, "stat value"))[0]))
    if r.pos != e.length:
        raise SaveParseError(f"misc stats: {e.length - r.pos} trailing bytes")
    return stats


def parse_player_location(body: SaveBody) -> PlayerLocation | None:
    e = _find(body, 1)
    if e is None or e.length < 30:
        return None
    d = body.raw[e.offset:e.offset + e.length]
    fa = body.form_id_array
    nid = struct.unpack_from("<I", d, 0)[0]
    cx, cy = struct.unpack_from("<ii", d, 7)
    return PlayerLocation(nid, read_refid(d[4:7], fa), cx, cy, read_refid(d[15:18], fa),
                          struct.unpack_from("<3f", d, 18))


def parse_global_variables(body: SaveBody) -> dict[int, float]:
    e = _find(body, 3)
    if e is None:
        return {}
    r = Reader(body.raw[e.offset:e.offset + e.length], 0, "global variables")
    out = {}
    for _ in range(read_vsval(r, "global count")):
        fid = read_refid(r.take(3, "global refid"), body.form_id_array)
        out[fid] = r.f32("global value")
    return out
