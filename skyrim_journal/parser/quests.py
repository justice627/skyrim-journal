"""Quest stage progress from QUST change forms.

Verified on a real save: for QUST change forms whose changeFlags include 0x80000000 the
payload starts with a 2-byte header (the 0x2 flags byte and one further byte; not
interpreted as a pair), then a vsval count and ``count`` x (u16 stage id, u8 flag). Flag 1 means
the stage was reached.

Empirically established on the same save (see tests): the first 2 bytes are a little-endian u16
of runtime quest flags (present whenever changeFlag 0x2 is set). Bit 0x0002 is "completed";
0x0040 is "failed" (never set in the sample, so unverified); 0x2000 is set exactly on quests
that have a displayed objective. When changeFlag 0x20000000 is set, a second list follows the
stage list: vsval count and ``count`` x (u32 objective index, u32 state), state 0 dormant,
1 displayed, 2 completed, 3 completed and displayed, 4 failed, 5 failed and displayed (only
1 and 3 occur in the sample; 4 occurs once). Bytes after that belong to other change flags
and are ignored.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .body import SaveBody, payload_decompress
from .errors import SaveParseError
from .player import read_vsval
from .reader import Reader

QUST_TYPE = 8
F_STAGES = 0x80000000
F_OBJECTIVES = 0x20000000
FLAG_COMPLETED = 0x0002
FLAG_FAILED = 0x0040
FLAG_OBJECTIVE_DISPLAYED = 0x2000
OBJECTIVE_DISPLAYED, OBJECTIVE_COMPLETED_DISPLAYED = 1, 3


@dataclass
class QuestProgress:
    form_id: int | None
    stages: list[tuple[int, int]]  # (stage id, flag) in stored order
    flags: int | None = None       # runtime quest flags (u16), see module docstring
    objectives: list[tuple[int, int]] = field(default_factory=list)  # (index, state)

    @property
    def completed(self) -> bool:
        return bool(self.flags is not None and self.flags & FLAG_COMPLETED)

    @property
    def failed(self) -> bool:
        return bool(self.flags is not None and self.flags & FLAG_FAILED)

    @property
    def has_displayed_objective(self) -> bool:
        return any(s == OBJECTIVE_DISPLAYED for _, s in self.objectives) or bool(
            self.flags is not None and self.flags & FLAG_OBJECTIVE_DISPLAYED)

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


def _read_stages(r: Reader) -> list[tuple[int, int]]:
    n = read_vsval(r, "stage count")
    if r.pos + 3 * n > len(r.buf):
        raise SaveParseError(f"QUST stage list of {n} entries overruns payload of {len(r.buf)} bytes")
    return [(r.u16("stage id"), r.u8("stage flag")) for _ in range(n)]


def parse_quest_stages(data: bytes) -> list[tuple[int, int]]:
    return _read_stages(Reader(data, 2, "QUST payload"))


def _read_objectives(r: Reader) -> list[tuple[int, int]]:
    n = read_vsval(r, "objective count")
    if r.pos + 8 * n > len(r.buf):
        raise SaveParseError(f"QUST objective list of {n} entries overruns payload")
    out = [(r.u32("objective index"), r.u32("objective state")) for _ in range(n)]
    if any(s > 5 for _, s in out):
        raise SaveParseError("implausible QUST objective state")
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
            r = Reader(data, 2, "QUST payload")
            stages = _read_stages(r)
        except SaveParseError:
            continue
        flags = int.from_bytes(data[:2], "little") if cf.change_flags & 0x2 else None
        objectives: list[tuple[int, int]] = []
        if cf.change_flags & F_OBJECTIVES:
            try:
                objectives = _read_objectives(r)
            except SaveParseError:
                objectives = []     # keep the stage list; objectives just stay unknown
        out.append(QuestProgress(cf.form_id, stages, flags, objectives))
    return out
