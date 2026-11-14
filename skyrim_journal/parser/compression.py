import zlib

import lz4.block

from .errors import DecompressionError

NONE, ZLIB, LZ4 = 0, 1, 2
NAMES = {NONE: "none", ZLIB: "zlib", LZ4: "lz4"}
MAX_UNCOMPRESSED = 1 << 30  # refuse absurd sizes from corrupt length fields


def decompress(kind: int, data: bytes, expected_len: int, what: str, offset: int) -> bytes:
    """Decompress `data` (found at file `offset`) and check the result size."""
    name = NAMES.get(kind, f"unknown({kind})")
    where = f"{what} (compression {name}, file offset {offset}, {len(data)} bytes in)"
    if kind == NONE:
        return data
    if expected_len > MAX_UNCOMPRESSED:
        raise DecompressionError(f"Implausible uncompressed length {expected_len} for {where}")
    try:
        if kind == LZ4:
            out = lz4.block.decompress(data, uncompressed_size=expected_len)
        elif kind == ZLIB:
            out = zlib.decompress(data)
        else:
            raise DecompressionError(f"Unknown compression type {kind} for {where}")
    except DecompressionError:
        raise
    except Exception as e:  # lz4.block.LZ4BlockError, zlib.error, ...
        raise DecompressionError(
            f"Could not decompress {where}: {type(e).__name__}: {e}. "
            "File may be corrupt or use an unsupported mode."
        ) from e
    if len(out) != expected_len:
        raise DecompressionError(
            f"Decompressed size mismatch for {where}: expected {expected_len}, got {len(out)}"
        )
    return out
