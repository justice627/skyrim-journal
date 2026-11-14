import struct

from .errors import ImplausibleLengthError, TruncatedFileError


class Reader:
    """Bounds-checked little-endian cursor. Every read names its field."""

    def __init__(self, buf: bytes, pos: int = 0, space: str = "file"):
        self.buf = buf
        self.pos = pos
        self.space = space  # e.g. "file" or "decompressed body"

    def _need(self, n: int, field: str) -> None:
        if n < 0 or self.pos + n > len(self.buf):
            raise TruncatedFileError(
                f"Truncated while reading {field}: need {n} bytes at {self.space} "
                f"offset {self.pos}, but only {len(self.buf) - self.pos} remain "
                f"({self.space} size {len(self.buf)})"
            )

    def take(self, n: int, field: str) -> bytes:
        self._need(n, field)
        out = self.buf[self.pos:self.pos + n]
        self.pos += n
        return out

    def _unpack(self, fmt: str, size: int, field: str):
        self._need(size, field)
        (v,) = struct.unpack_from(fmt, self.buf, self.pos)
        self.pos += size
        return v

    def u8(self, field: str) -> int:
        return self._unpack("<B", 1, field)

    def u16(self, field: str) -> int:
        return self._unpack("<H", 2, field)

    def u32(self, field: str) -> int:
        return self._unpack("<I", 4, field)

    def f32(self, field: str) -> float:
        return self._unpack("<f", 4, field)

    def wstring(self, field: str) -> str:
        start = self.pos
        n = self.u16(f"{field} length")
        if self.pos + n > len(self.buf):
            raise ImplausibleLengthError(
                f"Implausible (or truncated) string length {n} for {field} at {self.space} offset "
                f"{start}: runs past end of {self.space} (size {len(self.buf)})"
            )
        return self.take(n, field).decode("cp1252", errors="replace")
