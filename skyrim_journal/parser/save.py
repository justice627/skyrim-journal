from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from . import compression
from .body import (DUMP_BYTES, PLAYER_BASE, PLAYER_REFR, ChangeForm, SaveBody, parse_body,
                   payload_decompress)
from .errors import TruncatedFileError
from .header import SaveHeader, parse_header


@dataclass
class ParsedSave:
    header: SaveHeader
    body: SaveBody

    def type_summary(self) -> list[dict]:
        agg: dict[int, list] = defaultdict(lambda: [0, 0, ""])
        for cf in self.body.change_forms:
            a = agg[cf.form_type]
            a[0] += 1
            a[1] += cf.length
            a[2] = cf.form_type_name
        return [{"type": t, "name": n, "count": c, "total_bytes": b}
                for t, (c, b, n) in sorted(agg.items())]

    def player_records(self) -> list[dict]:
        prefer = self.header.compression_type
        out = []
        for cf in self.body.change_forms:
            kind = ("ACHR" if (cf.form_type == 1 and cf.form_id == PLAYER_REFR) else
                    "NPC_" if (cf.form_type == 9 and cf.form_id == PLAYER_BASE) else None)
            if not kind:
                continue
            data, codec, err = payload_decompress(cf, prefer)
            d = cf.to_dict()
            d.update(role=kind, payload_codec=codec, payload_error=err,
                     payload_size=None if data is None else len(data),
                     first_bytes_hex=None if data is None else data[:DUMP_BYTES].hex(" "))
            out.append(d)
        return out

    def to_dict(self) -> dict:
        h, b = self.header, self.body
        return {
            "header": {k: v for k, v in vars(h).items()},
            "form_version": b.form_version, "plugin_info_size": b.plugin_info_size,
            "plugins": b.plugins, "light_plugins": b.light_plugins,
            "file_location_table": b.table, "offset_base": b.offset_base,
            "form_id_array_count": len(b.form_id_array),
            "change_form_summary": self.type_summary(),
            "player_records": self.player_records(),
            "change_forms": [cf.to_dict() for cf in b.change_forms],
            "warnings": b.warnings,
        }


def parse_save(data: bytes) -> ParsedSave:
    h = parse_header(data)
    if h.compression_type == compression.NONE:
        buf = data[h.body_start:]
        bases = [h.body_start]
    else:
        avail = len(data) - h.data_start
        if h.compressed_len > avail:
            raise TruncatedFileError(
                f"Truncated compressed body: compressedLen {h.compressed_len} at file offset "
                f"{h.data_start}, but only {avail} bytes remain")
        block = data[h.data_start:h.data_start + h.compressed_len]
        buf = compression.decompress(h.compression_type, block, h.uncompressed_len,
                                     "body", h.data_start)
        bases = [h.body_start, h.data_start]
    return ParsedSave(h, parse_body(buf, h.version, bases))
