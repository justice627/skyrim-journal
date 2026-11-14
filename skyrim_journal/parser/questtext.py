"""Quest text data ("instances") from QUST change forms: alias fills and global values.

Decoded empirically from a real save (see tests/test_questtext.py for what is asserted). After
the stage list (0x80000000) and objective list (0x20000000) the payload holds, in this order:

* changeFlag 0x10000000: u8 (always 0), u32 n + n x (u32 alias id, u8 0, RefID3), u32 m +
  m x (u32 alias id, RefID3), u8 b. The second list resolves to LCTN records in the sample and
  is probably the location aliases; the first is probably the reference aliases (RefIDs of
  placed or created references). Neither list is used here. If b == 1 an extra block follows:
  u32, a 4-byte tag, then tag-specific data. Tags CLOC, ADIA and CRFT carry u32 count + count x
  (u32, RefID3); SCPT carries 48 fixed bytes. Other tags (SKIL, ASSU) are not understood, so a
  record that has an instance block and such a tag is reported as not parsed.
* changeFlag 0x08000000: u32 (instance counter), vsval instance count, then per instance
  u32 instance id, vsval alias count + count x (u32 alias id, RefID3), vsval global count +
  count x (RefID3 of a GLOB, f32 value), 3 bytes (not interpreted).
* changeFlag 0x04000000: u8, the last byte of the record.

The instance alias RefIDs point at base forms, not placed references (NPC_, WEAP, MISC, LCTN,
...); in the sample 410 of 414 resolve to named records of those types. These are the values
the game uses to fill ``<Alias=...>`` tags of a quest's text. The global snapshot lists the
globals the text mentions (constants the save's global variable table does not list included).
What is not known from the save alone is which alias id carries which tag name; that needs the
quest's alias names from the plugin (names file ``aliases``).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .body import SaveBody, payload_decompress
from .errors import SaveParseError
from .player import read_vsval
from .quests import F_OBJECTIVES, F_STAGES, QUST_TYPE, _read_objectives, _read_stages
from .reader import Reader
from .refs import read_refid

F_RUNDATA, F_INSTANCE, F_ALREADY_RUN = 0x10000000, 0x08000000, 0x04000000
KNOWN_FLAGS = 0x2 | F_STAGES | F_OBJECTIVES | F_RUNDATA | F_INSTANCE | F_ALREADY_RUN
LIST_TAGS = (b"CLOC", b"ADIA", b"CRFT")
SCPT_BYTES = 48


@dataclass
class QuestInstance:
    instance_id: int
    aliases: dict[int, int | None]          # alias id -> form id (None = unresolvable RefID)
    globals: list[tuple[int | None, float]]  # (form id of the GLOB, value when the text was set)


@dataclass
class QuestInstances:
    form_id: int | None
    counter: int
    instances: list[QuestInstance] = field(default_factory=list)

    def alias_values(self, alias_id: int) -> set[int | None]:
        """Distinct form ids the alias has across instances (empty if no instance has it)."""
        return {i.aliases[alias_id] for i in self.instances if alias_id in i.aliases}

    def global_snapshots(self) -> dict[int, float]:
        """Form id -> value; a global listed twice keeps the last value."""
        return {f: v for i in self.instances for f, v in i.globals if f is not None}


@dataclass
class QuestTextScan:
    by_form: dict[int, QuestInstances] = field(default_factory=dict)
    with_instance_flag: int = 0   # QUST change forms carrying changeFlag 0x08000000
    parsed: int = 0               # ... of which decoded to the exact end of the record
    unparsed: list[int | None] = field(default_factory=list)


def _refid(r: Reader, form_ids: list[int], what: str) -> int | None:
    return read_refid(r.take(3, what), form_ids)


def parse_instance_tail(data: bytes, change_flags: int, form_ids: list[int]) -> QuestInstances | None:
    """Decode a QUST payload up to its end. None if the record has no instance block or is not
    understood (nothing is guessed: any mismatch with the layout above gives None)."""
    if not change_flags & F_INSTANCE or change_flags & ~KNOWN_FLAGS or not change_flags & 0x2:
        return None
    try:
        r = Reader(data, 2, "QUST payload")
        if change_flags & F_STAGES:
            _read_stages(r)
        if change_flags & F_OBJECTIVES:
            _read_objectives(r)
        if change_flags & F_RUNDATA:
            if r.u8("rundata byte") != 0:
                return None
            n = r.u32("rundata list 1 count")
            if r.pos + 8 * n > len(data):
                return None
            for _ in range(n):
                r.u32("alias id")
                if r.u8("pad") != 0:
                    return None
                r.take(3, "refid")
            m = r.u32("rundata list 2 count")
            if r.pos + 7 * m > len(data):
                return None
            r.take(7 * m, "rundata list 2")
            b = r.u8("rundata extra flag")
            if b not in (0, 1):
                return None
            if b == 1:
                r.u32("extra block header")
                tag = r.take(4, "extra block tag")
                if tag in LIST_TAGS:
                    c = r.u32("extra block count")
                    if r.pos + 7 * c > len(data):
                        return None
                    r.take(7 * c, "extra block entries")
                elif tag == b"SCPT":
                    r.take(SCPT_BYTES, "SCPT block")
                else:
                    return None
        counter = r.u32("instance counter")
        out = QuestInstances(None, counter)
        for _ in range(read_vsval(r, "instance count")):
            iid = r.u32("instance id")
            aliases: dict[int, int | None] = {}
            for _ in range(read_vsval(r, "alias count")):
                aid = r.u32("alias id")
                aliases[aid] = _refid(r, form_ids, "alias refid")
            globs = []
            for _ in range(read_vsval(r, "global count")):
                globs.append((_refid(r, form_ids, "global refid"), r.f32("global value")))
            r.take(3, "instance trailer")
            out.instances.append(QuestInstance(iid, aliases, globs))
        if change_flags & F_ALREADY_RUN:
            r.u8("already-run byte")
        if r.pos != len(data):
            return None
        return out
    except SaveParseError:
        return None


def parse_quest_instances(body: SaveBody, compression_type: int) -> QuestTextScan:
    """Instance data of every QUST change form that has it (see the module docstring)."""
    scan = QuestTextScan()
    for cf in body.change_forms:
        if cf.form_type != QUST_TYPE or not cf.change_flags & F_INSTANCE:
            continue
        scan.with_instance_flag += 1
        data, _, _ = payload_decompress(cf, compression_type)
        res = parse_instance_tail(data, cf.change_flags, body.form_id_array) if data else None
        if res is None:
            scan.unparsed.append(cf.form_id)
            continue
        res.form_id = cf.form_id
        scan.parsed += 1
        if cf.form_id is not None:
            scan.by_form[cf.form_id] = res
    return scan
