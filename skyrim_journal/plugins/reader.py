"""Seek-based reader for TES5/SSE plugin files.

Only EDID and FULL of a whitelist of record types are extracted. Top-level
groups for other types are skipped without being read, and records are only
decompressed when they are of a wanted type.
"""
from __future__ import annotations

import mmap
import os
import struct
import zlib
from dataclasses import dataclass, field

RECORD_TYPES = frozenset(
    "QUST PERK WEAP ARMO AMMO ALCH INGR BOOK MISC KEYM SLGM SCRL SPEL SHOU "
    "WOOP MGEF ENCH FACT RACE NPC_ LCTN CELL WRLD AVIF GLOB".split()
)
_WANTED_BYTES = frozenset(t.encode("ascii") for t in RECORD_TYPES)
_EXTRA_TYPES = frozenset((b"PERK", b"AVIF", b"QUST"))

FLAG_ESM = 0x1
FLAG_DELETED = 0x20
FLAG_LOCALIZED = 0x80
FLAG_LIGHT = 0x200
FLAG_COMPRESSED = 0x00040000

_HDR = struct.Struct("<4sIII")  # type/label, size, flags/label2, formid/groupType
# group types whose children are records/groups we want to descend into
_DESCEND_GROUP_TYPES = frozenset({0, 1, 2, 3, 4, 5})


class PluginError(Exception):
    pass


@dataclass
class RawRecord:
    rtype: str
    form_id: int
    edid: str | None
    full: str | int | None  # int = localized string id
    # Type-specific data (raw form ids as stored, i.e. relative to the plugin's own masters):
    #   PERK: playable, hidden (bool), next (int form id)
    #   AVIF: perks (list of int form ids from the skill tree)
    #   QUST: quest_type (int), objectives (int), complete_stages, fail_stages (list of int)
    extra: dict = field(default_factory=dict)


@dataclass
class PluginScan:
    path: str
    name: str
    flags: int = 0
    masters: list[str] = field(default_factory=list)
    records: list[RawRecord] = field(default_factory=list)

    @property
    def localized(self) -> bool:
        return bool(self.flags & FLAG_LOCALIZED)

    @property
    def light(self) -> bool:
        return bool(self.flags & FLAG_LIGHT) or self.name.lower().endswith(".esl")


def decode_text(raw: bytes) -> str:
    raw = raw.split(b"\x00", 1)[0]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _iter_subrecords(buf):
    """Yield (type bytes, data) honouring XXXX oversize markers."""
    pos, n = 0, len(buf)
    override = None
    while pos + 6 <= n:
        t = bytes(buf[pos:pos + 4])
        (size,) = struct.unpack_from("<H", buf, pos + 4)
        pos += 6
        if t == b"XXXX":
            if size != 4 or pos + 4 > n:
                raise PluginError("bad XXXX subrecord")
            (override,) = struct.unpack_from("<I", buf, pos)
            pos += 4
            continue
        if override is not None:
            size = override
            override = None
        if pos + size > n:
            raise PluginError("subrecord overruns record")
        yield t, buf[pos:pos + size]
        pos += size


def parse_header_subrecords(buf):
    masters = []
    for t, data in _iter_subrecords(buf):
        if t == b"MAST":
            masters.append(decode_text(bytes(data)))
    return masters


def _extract(buf, localized: bool):
    edid = None
    full = None
    have_full = False
    for t, data in _iter_subrecords(buf):
        if t == b"EDID" and edid is None:
            edid = decode_text(bytes(data))
        elif t == b"FULL" and not have_full:
            have_full = True
            if localized and len(data) == 4:
                full = struct.unpack("<I", bytes(data))[0]
            else:
                full = decode_text(bytes(data))
        if edid is not None and have_full:
            break
    return edid, full


def _u32(data) -> int | None:
    return struct.unpack_from("<I", bytes(data), 0)[0] if len(data) == 4 else None


def _extract_extra(rtype: bytes, buf) -> dict:
    """Perk, skill-tree and quest details. Defensive: anything unexpected is simply left out."""
    out: dict = {}
    if rtype == b"PERK":
        for t, data in _iter_subrecords(buf):
            if t == b"DATA" and len(data) >= 5:
                out["playable"], out["hidden"] = bool(data[3]), bool(data[4])
            elif t == b"NNAM":
                nxt = _u32(data)
                if nxt:
                    out["next"] = nxt
    elif rtype == b"AVIF":
        perks = []
        for t, data in _iter_subrecords(buf):
            if t == b"PNAM":
                fid = _u32(data)
                if fid:
                    perks.append(fid)
        out["perks"] = perks
    elif rtype == b"QUST":
        objectives, stage = 0, None
        complete, fail = set(), set()
        for t, data in _iter_subrecords(buf):
            if t == b"DNAM":
                # flags u16, priority u8, formVersion u8, [4 unknown bytes], questType u32
                off = 8 if len(data) >= 12 else 4 if len(data) == 8 else None
                if off is not None:
                    qt = struct.unpack_from("<I", bytes(data), off)[0]
                    if qt <= 11:
                        out["quest_type"] = qt
            elif t == b"INDX" and len(data) >= 2:
                stage = struct.unpack_from("<H", bytes(data), 0)[0]
            elif t == b"QSDT" and len(data) >= 1 and stage is not None:
                if data[0] & 0x1:
                    complete.add(stage)
                if data[0] & 0x2:
                    fail.add(stage)
            elif t == b"QOBJ":
                objectives += 1
        out.update(objectives=objectives, complete_stages=sorted(complete),
                   fail_stages=sorted(fail))
    return out


def _record_data(mm, pos, size, flags):
    data = mm[pos:pos + size]
    if flags & FLAG_COMPRESSED:
        if len(data) < 4:
            raise PluginError("compressed record too short")
        (expect,) = struct.unpack_from("<I", data, 0)
        try:
            data = zlib.decompress(data[4:])
        except zlib.error as e:
            raise PluginError(f"zlib error: {e}") from e
        if len(data) != expect:
            raise PluginError("decompressed size mismatch")
    return data


def _walk(mm, start, end, out, localized, size_total):
    pos = start
    while pos < end:
        if pos + 24 > end:
            raise PluginError("truncated record header")
        rtype, size, a, b = _HDR.unpack_from(mm, pos)
        if rtype == b"GRUP":
            if size < 24 or pos + size > end:
                raise PluginError("bad group size")
            gtype = struct.unpack_from("<i", mm, pos + 12)[0]
            if gtype == 0:
                # top-level: label is the record type; skip unwanted wholesale
                if bytes(mm[pos + 8:pos + 12]) in _WANTED_BYTES:
                    _walk(mm, pos + 24, pos + size, out, localized, size_total)
            elif gtype in _DESCEND_GROUP_TYPES:
                _walk(mm, pos + 24, pos + size, out, localized, size_total)
            pos += size
            continue
        if pos + 24 + size > end:
            raise PluginError(f"record {rtype!r} overruns its container")
        if rtype in _WANTED_BYTES and not (a & FLAG_DELETED):
            data = _record_data(mm, pos + 24, size, a)
            edid, full = _extract(data, localized)
            if edid is not None or full is not None:
                try:
                    extra = _extract_extra(rtype, data) if rtype in _EXTRA_TYPES else {}
                except (PluginError, struct.error):
                    extra = {}
                out.append(RawRecord(rtype.decode("ascii"), b, edid, full, extra))
        pos += 24 + size


def scan_plugin(path: str) -> PluginScan:
    name = os.path.basename(path)
    scan = PluginScan(path=path, name=name)
    size = os.path.getsize(path)
    if size < 24:
        raise PluginError("file too small to be a plugin")
    with open(path, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            rtype, dsize, flags, _fid = _HDR.unpack_from(mm, 0)
            if rtype != b"TES4":
                raise PluginError("missing TES4 header record")
            if 24 + dsize > size:
                raise PluginError("TES4 record overruns file")
            scan.flags = flags
            scan.masters = parse_header_subrecords(_record_data(mm, 24, dsize, flags))
            _walk(mm, 24 + dsize, size, scan.records, scan.localized, size)
        except struct.error as e:
            raise PluginError(f"truncated data: {e}") from e
        finally:
            mm.close()
    return scan
