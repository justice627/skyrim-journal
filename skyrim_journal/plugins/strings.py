"""Localized string lookup: loose .STRINGS files and SSE BSA v105 archives."""
from __future__ import annotations

import os
import struct

from .reader import decode_text


class StringsError(Exception):
    pass


def parse_strings(data: bytes) -> dict[int, str]:
    """Parse a .STRINGS file (zstring entries) into id -> text."""
    if len(data) < 8:
        raise StringsError("strings file too short")
    count, _dsize = struct.unpack_from("<II", data, 0)
    base = 8 + count * 8
    if base > len(data):
        raise StringsError("strings directory overruns file")
    out = {}
    for i in range(count):
        sid, off = struct.unpack_from("<II", data, 8 + i * 8)
        start = base + off
        if start >= len(data):
            continue
        end = data.find(b"\x00", start)
        if end < 0:
            end = len(data)
        out[sid] = decode_text(data[start:end])
    return out


class DirIndex:
    """Case-insensitive file lookup for Linux."""

    def __init__(self):
        self._cache: dict[str, dict[str, str]] = {}

    def listing(self, d: str) -> dict[str, str]:
        if d not in self._cache:
            try:
                self._cache[d] = {e.lower(): e for e in os.listdir(d)}
            except OSError:
                self._cache[d] = {}
        return self._cache[d]

    def child(self, d: str, name: str) -> str | None:
        real = self.listing(d).get(name.lower())
        return os.path.join(d, real) if real else None


# ---------------------------------------------------------------- BSA v105

_BSA_COMPRESSED = 0x4
_BSA_EMBED_NAMES = 0x100
_BSA_TOGGLE = 0x40000000


class Bsa:
    """Minimal SSE (v105) BSA reader; only indexes names and extracts files."""

    def __init__(self, path: str):
        self.path = path
        self.files: dict[str, tuple[int, int, bool]] = {}  # lower path -> (offset,size,compressed)
        self.flags = 0
        self._load_index()

    def _load_index(self):
        with open(self.path, "rb") as f:
            head = f.read(36)
            if len(head) < 36 or head[:4] != b"BSA\x00":
                raise StringsError("not a BSA")
            (_m, ver, folder_off, flags, nfolders, nfiles,
             _fnlen, total_file_names, _ft, _pad) = struct.unpack("<4sIIIIIIIHH", head)
            if ver != 105:
                raise StringsError(f"unsupported BSA version {ver}")
            if not (flags & 0x1 and flags & 0x2):
                raise StringsError("BSA lacks directory/file names")
            self.flags = flags
            f.seek(folder_off)
            raw = f.read(24 * nfolders)
            if len(raw) != 24 * nfolders:
                raise StringsError("truncated folder records")
            counts = [struct.unpack_from("<Q I I Q", raw, i * 24)[1] for i in range(nfolders)]
            # file record blocks follow folder records, in folder order
            blocks = []  # (folder name, [(size, offset)])
            for cnt in counts:
                ln = f.read(1)
                if not ln:
                    raise StringsError("truncated file record block")
                nm = f.read(ln[0])
                recs = f.read(16 * cnt)
                if len(recs) != 16 * cnt:
                    raise StringsError("truncated file records")
                folder = decode_text(nm).replace("\\", "/").lower()
                blocks.append((folder, [struct.unpack_from("<Q I I", recs, j * 16)[1:]
                                        for j in range(cnt)]))
            names_blob = f.read(total_file_names)
        names = names_blob.split(b"\x00")
        default_comp = bool(flags & _BSA_COMPRESSED)
        k = 0
        for folder, recs in blocks:
            for size, offset in recs:
                if k >= len(names):
                    raise StringsError("file name table too short")
                fname = decode_text(names[k]).lower()
                k += 1
                comp = default_comp ^ bool(size & _BSA_TOGGLE)
                self.files[f"{folder}/{fname}" if folder else fname] = (
                    offset, size & 0x3FFFFFFF, comp)

    def read(self, path: str) -> bytes | None:
        ent = self.files.get(path.replace("\\", "/").lower())
        if ent is None:
            return None
        offset, size, comp = ent
        with open(self.path, "rb") as f:
            f.seek(offset)
            data = f.read(size)
        if len(data) != size:
            raise StringsError("truncated file data")
        if self.flags & _BSA_EMBED_NAMES:
            if not data:
                raise StringsError("empty file entry")
            data = data[1 + data[0]:]
        if comp:
            if len(data) < 4:
                raise StringsError("compressed entry too short")
            (orig,) = struct.unpack_from("<I", data, 0)
            import lz4.frame
            try:
                out = lz4.frame.decompress(data[4:])
            except Exception as e:
                raise StringsError(f"lz4 error: {e}") from e
            if len(out) != orig:
                raise StringsError("decompressed size mismatch")
            return out
        return data


class StringsFinder:
    """Locate <Plugin>_<Language>.STRINGS loose or inside BSAs."""

    def __init__(self, data_dirs: list[str], language: str = "english"):
        self.dirs = list(data_dirs)
        self.language = language.lower()
        self.idx = DirIndex()
        self._bsas: dict[str, Bsa | None] = {}
        self.warnings: list[str] = []

    def _bsa_paths(self, plugin_dirs: list[str], base: str) -> list[str]:
        paths = []
        for d in plugin_dirs + self.dirs:
            for low, real in self.idx.listing(d).items():
                if low.endswith(".bsa"):
                    p = os.path.join(d, real)
                    if p not in paths:
                        paths.append(p)
        paths.sort(key=lambda p: not os.path.basename(p).lower().startswith(base.lower()))
        return paths

    def find(self, plugin_path: str) -> tuple[dict[int, str], str] | None:
        """Return (table, source) or None."""
        base = os.path.splitext(os.path.basename(plugin_path))[0]
        fname = f"{base}_{self.language}.strings"
        dirs = []
        for d in [os.path.dirname(os.path.abspath(plugin_path))] + self.dirs:
            if d not in dirs:
                dirs.append(d)
        for d in dirs:
            sdir = self.idx.child(d, "strings")
            if sdir:
                p = self.idx.child(sdir, fname)
                if p:
                    try:
                        with open(p, "rb") as f:
                            return parse_strings(f.read()), f"loose:{p}"
                    except (OSError, StringsError) as e:
                        self.warnings.append(f"{p}: {e}")
        for p in self._bsa_paths(dirs, base):
            if p not in self._bsas:
                try:
                    self._bsas[p] = Bsa(p)
                except (OSError, StringsError, struct.error) as e:
                    self._bsas[p] = None
                    self.warnings.append(f"{os.path.basename(p)}: cannot index ({e})")
            bsa = self._bsas[p]
            if bsa is None:
                continue
            try:
                data = bsa.read(f"strings/{fname}")
                if data is not None:
                    return parse_strings(data), f"bsa:{os.path.basename(p)}"
            except (OSError, StringsError) as e:
                self.warnings.append(f"{os.path.basename(p)}: {e}")
        return None
