"""Body parsing: plugins, file location table, change-form inventory.

Offset mapping (UNVERIFIED, auto-detected): the file location table stores offsets
as if the file were uncompressed. Buffer index = table offset - base, where base is
the file offset at which the body would start in an uncompressed file. We cannot
tell whether that is the end of the screenshot or the start of the compressed
block (8 bytes later), so parse_body tries both and keeps the one for which the
formID array and every change form parse cleanly. `offset_base` records the result.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import compression
from .errors import FormatError, SaveParseError
from .reader import Reader

# From memory of UESP; not verified against the wiki.
FORM_TYPES = {
    0: "REFR", 1: "ACHR", 2: "PMIS", 3: "PGRE", 4: "PBEA", 5: "PFLA", 6: "CELL", 7: "INFO",
    8: "QUST", 9: "NPC_", 10: "ACTI", 11: "TACT", 12: "ARMO", 13: "BOOK", 14: "CONT",
    15: "DOOR", 16: "INGR", 17: "LIGH", 18: "MISC", 19: "APPA", 20: "STAT", 21: "MSTT",
    22: "FURN", 23: "WEAP", 24: "AMMO", 25: "KEYM", 26: "ALCH", 27: "IDLM", 28: "NOTE",
    29: "ECZN", 30: "CLAS", 31: "FACT", 32: "PACK", 33: "NAVM", 34: "WOOP", 35: "MGEF",
    36: "SMQN", 37: "SCEN", 38: "LCTN", 39: "RELA", 40: "PHZD", 41: "PBAR", 42: "PCON",
    43: "FLST", 44: "LVLN", 45: "LVLI", 46: "LVSP", 47: "PARW", 48: "ENCH",
}
REF_SOURCES = {0: "formIDArray", 1: "default", 2: "created", 3: "unknown"}
TABLE_FIELDS = [
    "formIDArrayCountOffset", "unknownTable3Offset", "globalDataTable1Offset",
    "globalDataTable2Offset", "changeFormsOffset", "globalDataTable3Offset",
    "globalDataTable1Count", "globalDataTable2Count", "globalDataTable3Count",
    "changeFormCount",
]
PLAYER_REFR, PLAYER_BASE = 0x14, 0x7
DUMP_BYTES = 64


@dataclass
class ChangeForm:
    index: int
    body_offset: int           # offset of the record in the decompressed body
    ref_raw: int               # 22-bit value as stored
    ref_source: int            # 0..3
    form_id: int | None        # resolved 32-bit form id (None if unresolvable)
    change_flags: int
    form_type: int
    form_type_name: str
    version: int
    length: int                # stored bytes
    uncompressed_length: int   # 0 if not compressed
    payload: bytes = field(default=b"", repr=False)

    def to_dict(self) -> dict:
        return {
            "index": self.index, "body_offset": self.body_offset,
            "ref_source": REF_SOURCES[self.ref_source], "ref_value": f"0x{self.ref_raw:06X}",
            "form_id": None if self.form_id is None else f"0x{self.form_id:08X}",
            "change_flags": f"0x{self.change_flags:08X}",
            "form_type": self.form_type, "form_type_name": self.form_type_name,
            "version": self.version, "length": self.length,
            "uncompressed_length": self.uncompressed_length,
        }


@dataclass
class SaveBody:
    form_version: int
    plugin_info_size: int
    plugins: list[str]
    light_plugins: list[str]
    table: dict[str, int]
    offset_base: int
    form_id_array: list[int]
    change_forms: list[ChangeForm]
    warnings: list[str]
    raw: bytes = field(default=b"", repr=False)  # decompressed body


def parse_refid(b: bytes) -> tuple[int, int]:
    """3 bytes, big-endian packing: (source type, 22-bit value)."""
    v = int.from_bytes(b, "big")
    return v >> 22, v & 0x3FFFFF


def resolve(source: int, value: int, form_ids: list[int]) -> int | None:
    if source == 1:
        return value
    if source == 2:
        return 0xFF000000 | value
    if source == 0:
        # Assumed 1-based (0 = null); UNVERIFIED.
        if 1 <= value <= len(form_ids):
            return form_ids[value - 1]
        return None
    return None


def payload_decompress(cf: ChangeForm, prefer: int) -> tuple[bytes | None, str | None, str | None]:
    """Return (data, codec name, error). Payload codec is UNVERIFIED, so try both."""
    if cf.uncompressed_length == 0:
        return cf.payload, "none", None
    order = [compression.LZ4, compression.ZLIB]
    if prefer == compression.ZLIB:
        order.reverse()
    errs = []
    for kind in order:
        try:
            return (compression.decompress(kind, cf.payload, cf.uncompressed_length,
                                           "change form payload", cf.body_offset),
                    compression.NAMES[kind], None)
        except SaveParseError as e:
            errs.append(str(e))
    return None, None, " | ".join(errs)


def _walk(buf: bytes, table: dict[str, int], base: int,
          ) -> tuple[list[int], list[ChangeForm]]:
    fa = table["formIDArrayCountOffset"] - base
    if fa < 0 or fa + 4 > len(buf):
        raise FormatError(f"formIDArrayCountOffset {table['formIDArrayCountOffset']} maps to "
                          f"body index {fa}, outside body (size {len(buf)}), base {base}")
    r = Reader(buf, fa, "decompressed body")
    n = r.u32("formIDArray count")
    if fa + 4 + 4 * n > len(buf):
        raise FormatError(f"formIDArray count {n} at body offset {fa} runs past end of body")
    form_ids = [r.u32("formIDArray entry") for _ in range(n)]

    cf_off = table["changeFormsOffset"] - base
    if cf_off < 0 or cf_off > len(buf):
        raise FormatError(f"changeFormsOffset {table['changeFormsOffset']} maps to body index "
                          f"{cf_off}, outside body (size {len(buf)}), base {base}")
    r = Reader(buf, cf_off, "decompressed body")
    forms = []
    for i in range(table["changeFormCount"]):
        start = r.pos
        ctx = f"change form #{i} at body offset {start}"
        src, val = parse_refid(r.take(3, f"{ctx}: formID"))
        flags = r.u32(f"{ctx}: changeFlags")
        tbyte = r.u8(f"{ctx}: type")
        ver = r.u8(f"{ctx}: version")
        width = tbyte >> 6
        ftype = tbyte & 0x3F
        if width == 3:
            raise FormatError(f"{ctx}: invalid length-width bits 3 in type byte 0x{tbyte:02X}")
        rd = (r.u8, r.u16, r.u32)[width]
        l1 = rd(f"{ctx}: length1")
        l2 = rd(f"{ctx}: length2")
        if r.pos + l1 > len(buf):
            raise FormatError(f"{ctx} (type {ftype}, formID 0x{val:06X}): length1 {l1} runs past "
                              f"end of body (size {len(buf)}, data at {r.pos})")
        payload = r.take(l1, f"{ctx}: data")
        forms.append(ChangeForm(i, start, val, src, resolve(src, val, form_ids), flags, ftype,
                                FORM_TYPES.get(ftype, f"UNKNOWN_{ftype}"), ver, l1, l2, payload))
    return form_ids, forms


def parse_body(buf: bytes, version: int, bases: list[int]) -> SaveBody:
    """`buf` is the decompressed body; `bases` are candidate offset bases (see module doc)."""
    r = Reader(buf, 0, "decompressed body")
    form_version = r.u8("formVersion")
    plugin_info_size = r.u32("pluginInfoSize")
    info_start = r.pos
    count = r.u8("pluginCount")
    plugins = [r.wstring(f"plugin[{i}]") for i in range(count)]
    after_plugins = r.pos
    light: list[str] = []
    warnings: list[str] = []
    if version >= 12 and form_version >= 78:
        lc = r.u16("lightPluginCount")
        light = [r.wstring(f"lightPlugin[{i}]") for i in range(lc)]
    if info_start + plugin_info_size not in (after_plugins, r.pos):
        warnings.append(f"pluginInfoSize {plugin_info_size} (ends at body offset "
                        f"{info_start + plugin_info_size}) matches neither end of plugin list "
                        f"({after_plugins}) nor end of light plugin list ({r.pos})")
    table = {name: r.u32(f"fileLocationTable.{name}") for name in TABLE_FIELDS}
    r.take(15 * 4, "fileLocationTable unused[15]")

    last: Exception | None = None
    for base in bases:
        try:
            form_ids, forms = _walk(buf, table, base)
        except SaveParseError as e:
            last = last or e
            warnings.append(f"offset base {base} rejected: {e}")
            continue
        return SaveBody(form_version, plugin_info_size, plugins, light, table, base,
                        form_ids, forms, warnings, buf)
    raise FormatError("Could not map file location table offsets into the body with any "
                      f"candidate base {bases}. First failure: {last}")
