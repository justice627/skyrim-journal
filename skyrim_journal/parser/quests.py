"""Quest stage progress from QUST change forms.

Verified on a real save: for QUST change forms whose changeFlags include 0x80000000 the
payload starts with a 2-byte header (the 0x2 flags byte and one further byte; not
interpreted), then a vsval count and ``count`` x (u16 stage id, u8 flag). Flag 1 means the
stage was reached. Bytes after the stage list belong to other change flags and are ignored.
"""
from __future__ import annotations

from dataclasses import dataclass

from .body import SaveBody, payload_decompress
from .errors import SaveParseError
from .player import read_vsval
from .reader import Reader

QUST_TYPE = 8
F_STAGES = 0x80000000


@dataclass
class QuestProgress:
    form_id: int | None
    stages: list[tuple[int, int]]  # (stage id, flag) in stored order

    @property
    def reached(self) -> list[int]:
        return sorted({s for s, f in self.stages if f == 1})

    @property
    def reached_nonzero(self) -> list[int]:
        return [s for s in self.reached if s != 0]

    @property
    def highest(self) -> int | None:
        r = self.reached
        return r[-1] if r else None


def parse_quest_stages(data: bytes) -> list[tuple[int, int]]:
    r = Reader(data, 2, "QUST payload")
    n = read_vsval(r, "stage count")
    if r.pos + 3 * n > len(data):
        raise SaveParseError(f"QUST stage list of {n} entries overruns payload of {len(data)} bytes")
    out = []
    for _ in range(n):
        out.append((r.u16("stage id"), r.u8("stage flag")))
    return out


def parse_quests(body: SaveBody, compression_type: int) -> list[QuestProgress]:
    """All quests with a decodable stage list (including quests with no progress)."""
    out = []
    for cf in body.change_forms:
        if cf.form_type != QUST_TYPE or not cf.change_flags & F_STAGES:
            continue
        data, _, _ = payload_decompress(cf, compression_type)
        if data is None:
            continue
        try:
            out.append(QuestProgress(cf.form_id, parse_quest_stages(data)))
        except SaveParseError:
            continue
    return out
