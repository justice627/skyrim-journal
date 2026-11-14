from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from . import compression
from .errors import BadMagicError, FormatError, TruncatedFileError, UnsupportedVersionError
from .reader import Reader

MAGIC = b"TESV_SAVEGAME"
SUPPORTED_VERSIONS = {7, 8, 9, 12}  # 7-9 Legendary Edition, 12 Special/Anniversary


@dataclass
class SaveHeader:
    version: int
    save_number: int
    player_name: str
    player_level: int
    player_location: str
    game_date: str
    player_race: str
    player_sex: int
    cur_exp: float
    lvlup_exp: float
    filetime: int
    filetime_iso: str | None
    shot_width: int
    shot_height: int
    compression_type: int  # 0 none, 1 zlib, 2 lz4 (always 0 for LE)
    header_size: int
    header_includes_screenshot: bool
    body_start: int   # file offset right after the screenshot
    data_start: int   # file offset where body bytes (possibly compressed) begin
    uncompressed_len: int | None
    compressed_len: int | None

    @property
    def is_se(self) -> bool:
        return self.version >= 12

    @property
    def compression_name(self) -> str:
        return compression.NAMES.get(self.compression_type, str(self.compression_type))


def _filetime_iso(ft: int) -> str | None:
    try:
        return (dt.datetime(1601, 1, 1) + dt.timedelta(microseconds=ft // 10)).isoformat() + "Z"
    except OverflowError:
        return None


def parse_header(data: bytes) -> SaveHeader:
    if len(data) < len(MAGIC):
        if data != MAGIC[:len(data)]:
            raise BadMagicError(f"Not a valid Skyrim save (magic mismatch): file is only {len(data)} bytes")
        raise TruncatedFileError(f"Truncated while reading magic: file is {len(data)} bytes")
    if data[:len(MAGIC)] != MAGIC:
        raise BadMagicError(
            f"Not a valid Skyrim save (magic mismatch): expected {MAGIC!r}, got {data[:13]!r}"
        )
    r = Reader(data, len(MAGIC), "file")
    header_size = r.u32("headerSize")
    header_start = r.pos
    version = r.u32("version")
    if version not in SUPPORTED_VERSIONS:
        raise UnsupportedVersionError(
            f"Save version {version} is not supported (supported: {sorted(SUPPORTED_VERSIONS)}). "
            "Please report this file."
        )
    save_number = r.u32("saveNumber")
    name = r.wstring("playerName")
    level = r.u32("playerLevel")
    location = r.wstring("playerLocation")
    game_date = r.wstring("gameDate")
    race = r.wstring("playerRaceEditorId")
    sex = r.u16("playerSex")
    cur_exp = r.f32("playerCurExp")
    lvlup_exp = r.f32("playerLvlUpExp")
    ft = int.from_bytes(r.take(8, "filetime"), "little")
    w = r.u32("shotWidth")
    h = r.u32("shotHeight")
    comp = r.u16("compressionType") if version >= 12 else compression.NONE
    fields_end = r.pos

    bpp = 4 if version >= 12 else 3
    shot = w * h * bpp
    if shot > len(data) - fields_end:
        raise FormatError(
            f"Implausible screenshot size {w}x{h}x{bpp}={shot} bytes at file offset {fields_end}: "
            f"only {len(data) - fields_end} bytes remain"
        )
    r.pos = fields_end + shot
    body_start = r.pos

    # UESP wording is ambiguous about whether headerSize covers the screenshot; accept both.
    declared_end = header_start + header_size
    if declared_end == body_start:
        includes = True
    elif declared_end == fields_end:
        includes = False
    else:
        raise FormatError(
            f"headerSize {header_size} (header ends at file offset {declared_end}) matches neither "
            f"end of header fields ({fields_end}) nor end of screenshot ({body_start})"
        )

    if comp not in compression.NAMES:
        raise UnsupportedVersionError(f"Unsupported compressionType {comp} in header (file offset {fields_end - 2})")

    unc = cmp_len = None
    data_start = body_start
    if comp != compression.NONE:
        unc = r.u32("uncompressedLen")
        cmp_len = r.u32("compressedLen")
        data_start = r.pos
    return SaveHeader(
        version, save_number, name, level, location, game_date, race, sex, cur_exp, lvlup_exp,
        ft, _filetime_iso(ft), w, h, comp, header_size, includes, body_start, data_start, unc, cmp_len,
    )
