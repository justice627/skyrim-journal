"""Quest text data (alias fills, global snapshots) and objective-text tag rendering."""
import glob
import os
import struct
from types import SimpleNamespace

import pytest

from skyrim_journal.names import NameBook, NamesFileError
from skyrim_journal.parser import parse_save
from skyrim_journal.parser.questtext import parse_instance_tail, parse_quest_instances
from skyrim_journal.parser.quests import QuestProgress
from skyrim_journal.parser.refs import describe
from skyrim_journal.sheet import _quest_section
from skyrim_journal.texttags import render_tags

SAMPLES = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "samples", "*.ess")))
needs_sample = pytest.mark.skipif(not SAMPLES, reason="no real sample save present")
NAMES_PATH = os.path.join(os.path.dirname(__file__), "..", "names.json")

u32 = lambda v: struct.pack("<I", v)  # noqa: E731


def ref(src, val):
    return ((src << 22) | val).to_bytes(3, "big")


def vs(n):
    return bytes([n << 2])


FORM_IDS = [0x00000800, 0x01000801, 0x00000802]       # RefID source 0, values 1..3


def payload(*, rundata=b"", instances=b"", last=True, stages=b"", objectives=b"", counter=1):
    return (b"\x00\x20" + stages + objectives + rundata + u32(counter) + instances
            + (b"\x01" if last else b""))


def instance(iid, aliases, globs=()):
    return (u32(iid) + vs(len(aliases)) + b"".join(u32(a) + ref(1, f) for a, f in aliases)
            + vs(len(globs)) + b"".join(ref(0, g) + struct.pack("<f", v) for g, v in globs)
            + b"\x00\x00\x00")


FLAGS = 0x08000000 | 0x04000000 | 0x2


def test_instance_tail_simple_and_multiple_instances():
    inst = (instance(1, [(0x11, 0x14142), (0x13, 0x1915A)], [(2, 29.0)])
            + instance(2, [(0x11, 0x14143)]))
    d = payload(instances=vs(2) + inst, counter=2)
    out = parse_instance_tail(d, FLAGS, FORM_IDS)
    assert out.counter == 2 and [i.instance_id for i in out.instances] == [1, 2]
    assert out.instances[0].aliases == {0x11: 0x14142, 0x13: 0x1915A}
    assert out.instances[0].globals == [(0x01000801, 29.0)]         # RefID 2 -> form id array[1]
    assert out.alias_values(0x11) == {0x14142, 0x14143} and out.alias_values(0x99) == set()
    assert out.global_snapshots() == {0x01000801: 29.0}


def test_instance_tail_with_stages_objectives_and_rundata():
    stages = vs(2) + b"\x0a\x00\x01\x14\x00\x00"
    objs = vs(1) + u32(10) + u32(1)
    lists = (b"\x00" + u32(1) + u32(5) + b"\x00" + ref(1, 0x1234)      # list 1: 8-byte entries
             + u32(1) + u32(6) + ref(1, 0x1915A))                        # list 2: 7-byte entries
    inst = vs(1) + instance(1, [(4, 0x16772)])
    rd = lists + b"\x00"                                                  # extra flag 0
    out = parse_instance_tail(payload(stages=stages, objectives=objs, rundata=rd, instances=inst),
                              FLAGS | 0x80000000 | 0x20000000 | 0x10000000, FORM_IDS)
    assert out.instances[0].aliases == {4: 0x16772}
    # CLOC block (count + 7-byte entries) and the fixed-size SCPT block are skipped
    cloc = b"\x01" + u32(9) + b"CLOC" + u32(2) + (u32(0) + ref(1, 0x14)) + (u32(2) + ref(1, 0x8A57))
    out = parse_instance_tail(payload(rundata=lists + cloc, instances=inst),
                              FLAGS | 0x10000000, FORM_IDS)
    assert out.instances[0].aliases == {4: 0x16772}
    scpt = b"\x01" + u32(9) + b"SCPT" + bytes(48)
    assert parse_instance_tail(payload(rundata=lists + scpt, instances=inst),
                               FLAGS | 0x10000000, FORM_IDS) is not None


def test_instance_tail_rejects_what_it_does_not_understand():
    inst = vs(1) + instance(1, [(4, 0x16772)])
    good = payload(instances=inst)
    assert parse_instance_tail(good, FLAGS, FORM_IDS) is not None
    assert parse_instance_tail(good + b"\x00", FLAGS, FORM_IDS) is None       # trailing byte
    assert parse_instance_tail(good[:-5], FLAGS, FORM_IDS) is None            # truncated
    assert parse_instance_tail(good, 0x04000002, FORM_IDS) is None            # no instance flag
    assert parse_instance_tail(good, FLAGS | 0x4, FORM_IDS) is None           # unknown flag
    odd = b"\x01" + u32(9) + b"ASSU" + bytes(30)
    lists = b"\x00" + u32(0) + u32(0)
    assert parse_instance_tail(payload(rundata=lists + odd, instances=inst),
                               FLAGS | 0x10000000, FORM_IDS) is None          # unknown tag
    bad_pad = b"\x00" + u32(1) + u32(5) + b"\x07" + ref(1, 4) + u32(0) + b"\x00"
    assert parse_instance_tail(payload(rundata=bad_pad, instances=inst),
                               FLAGS | 0x10000000, FORM_IDS) is None          # pad byte not 0


# ---- tag rendering -------------------------------------------------------------------------

def test_render_tags_fallback_and_filled():
    aliases = {"QuestItem": "Bear Pelt", "QuestGiver": "Jenassa"}
    gl = {"manny_up_cp_count": 3.0, "ratio": 0.5}
    f = lambda t: render_tags(t, lambda n: aliases.get(n), lambda n: gl.get(n))  # noqa: E731
    assert f("Collect <Alias=QuestItem>s for <Alias.ShortName=QuestGiver> "
             "(<Global=manny_up_cp_count>/<Global=missing>)") \
        == "Collect Bear Pelts for Jenassa (3/[missing])"
    assert f("Go to <Alias=Dungeon>, said <Alias.Name=QuestGiver>.") == "Go to [Dungeon], said Jenassa."
    assert f("<Global=ratio> and <Global=manny_up_cp_count>") == "0.5 and 3"
    assert f("<Alias.Race=Boss> <BaseName> <Foo=Bar> plain") == "<Alias.Race=Boss> <BaseName> <Foo=Bar> plain"
    assert render_tags("<Alias=X>", lambda n: None, lambda n: None) == "[X]"


# ---- names file aliases ----------------------------------------------------------------------

def test_names_file_aliases():
    nb = NameBook({"Q.esp:000800": {"edid": "Q", "type": "QUST", "aliases": {
        "3": {"name": "QuestGiver", "kind": "ref"}, "7": {"name": "Dungeon", "kind": "loc"}}},
        "Q.esp:000801": {"edid": "Old", "type": "QUST"}})
    assert nb.entry("Q.esp:000800").aliases == {3: ("QuestGiver", "ref"), 7: ("Dungeon", "loc")}
    assert nb.entry("Q.esp:000801").aliases is None
    for bad in ({"x": {"name": "A"}}, {"3": "A"}, {"3": {"kind": "ref"}}, [1]):
        with pytest.raises(NamesFileError):
            NameBook({"Q.esp:000800": {"aliases": bad}})


# ---- sheet substitution on synthetic data ------------------------------------------------------

def _body():
    return SimpleNamespace(plugins=["Skyrim.esm", "Mod.esp"], light_plugins=[])


def _names(with_aliases=True):
    q = {"edid": "Dig", "name": "Dungeon Delving", "type": "QUST", "quest_type": 6, "objectives": 1,
         "complete_stages": [], "fail_stages": [],
         "objective_text": {"10": "Find <Alias=QuestItem> inside <Alias=Dungeon> for "
                                  "<Alias.ShortName=QuestGiver> (<Global=cnt>/<Global=tot>)"}}
    if with_aliases:
        q["aliases"] = {"17": {"name": "QuestGiver", "kind": "ref"},
                        "18": {"name": "QuestItem", "kind": "ref"},
                        "19": {"name": "Dungeon", "kind": "loc"}}
    return NameBook({"Mod.esp:000800": q,
                     "Skyrim.esm:000901": {"edid": "Giver", "name": "Shahvee", "type": "NPC_"},
                     "Skyrim.esm:000902": {"edid": "Amulet", "name": "Old Amulet", "type": "ARMO"},
                     "Skyrim.esm:000903": {"edid": "Cave", "name": "Winter War", "type": "LCTN"},
                     "Skyrim.esm:000904": {"edid": "NoDisplayName", "type": "ARMO"},
                     "Mod.esp:000A01": {"edid": "cnt", "type": "GLOB"},
                     "Mod.esp:000A02": {"edid": "tot", "type": "GLOB"}})


def _section(names, instances, gv):
    q = QuestProgress(0x01000800, [(10, 1)], 0x0, [(10, 1)])
    return "\n".join(_quest_section([q], _body(), names, [], instances, gv))


def _ins(aliases, globs=()):
    from skyrim_journal.parser.questtext import QuestInstance, QuestInstances
    return {0x01000800: QuestInstances(0x01000800, 1, [QuestInstance(1, aliases, list(globs))])}


def test_sheet_fills_aliases_and_globals():
    ins = _ins({17: 0x901, 18: 0x902, 19: 0x903}, [(0x01000A02, 99.0)])
    text = _section(_names(), ins, {0x01000A01: 3.0, 0x01000A02: 29.0})
    assert "Find Old Amulet inside Winter War for Shahvee (3/29)" in text
    # a global the save's table lacks falls back to the value stored with the quest text
    text = _section(_names(), ins, {0x01000A01: 3.0})
    assert "(3/99)" in text


def test_sheet_alias_fallbacks_are_never_guessed():
    full = {17: 0x901, 18: 0x902, 19: 0x903}
    gv = {0x01000A01: 3.0, 0x01000A02: 29.0}
    neutral = "Find [QuestItem] inside [Dungeon] for [QuestGiver] (3/29)"
    assert neutral in _section(_names(with_aliases=False), _ins(full), gv)   # old names file
    assert neutral in _section(_names(), None, gv)                           # no instance data
    assert neutral in _section(_names(), {}, gv)
    # form without a display name stays neutral; the others are still filled
    t = _section(_names(), _ins({17: 0x901, 18: 0x904, 19: 0x903}), gv)
    assert "Find [QuestItem] inside Winter War for Shahvee" in t
    t = _section(_names(), _ins({17: 0x901, 18: 0x902}), gv)                 # alias 19 not filled
    assert "Find Old Amulet inside [Dungeon] for Shahvee" in t
    t = _section(_names(), _ins({17: None, 18: 0x902, 19: 0x903}), gv)       # unresolvable RefID
    assert "for [QuestGiver]" in t
    # two instances disagreeing on an alias: not resolved
    from skyrim_journal.parser.questtext import QuestInstance, QuestInstances
    two = {0x01000800: QuestInstances(0x01000800, 2, [QuestInstance(1, full, []),
                                                      QuestInstance(2, {**full, 19: 0x901}, [])])}
    t = _section(_names(), two, gv)
    assert "Find Old Amulet inside [Dungeon] for Shahvee" in t
    # globals unknown everywhere
    assert "([cnt]/[tot])" in _section(_names(), _ins(full), {})


# ---- real sample ----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parsed():
    with open(SAMPLES[0], "rb") as f:
        return parse_save(f.read())


@needs_sample
def test_sample_every_instance_record_parses_to_its_end(parsed):
    scan = parse_quest_instances(parsed.body, parsed.header.compression_type)
    assert scan.with_instance_flag == 239 and scan.parsed == 239 and scan.unparsed == []
    assert sum(len(q.instances) for q in scan.by_form.values()) == 261


@needs_sample
def test_sample_alias_targets_resolve_to_sensible_records(parsed):
    if not os.path.exists(NAMES_PATH):
        pytest.skip("no names.json present")
    nb = NameBook.load(NAMES_PATH)
    b = parsed.body
    scan = parse_quest_instances(b, parsed.header.compression_type)
    by_name = {}
    for fid, q in scan.by_form.items():
        e = nb.entry(describe(b, fid))
        if e and e.name:
            by_name.setdefault(e.name, []).append(q)

    def targets(qname):
        (q,) = by_name[qname]
        return {a: (nb.entry(describe(b, f)).type, nb.entry(describe(b, f)).name)
                for a, f in q.instances[-1].aliases.items()}
    bandits = targets("Dungeon Delving (Bandits)")
    assert bandits == {0x11: ("NPC_", "Shahvee"), 0x12: ("ARMO", "Shahvee's Amulet of Zenithar"),
                       0x13: ("LCTN", "Winter War")}
    bounty = targets("Bounty: Bandit Boss")
    assert {t for t in bounty.values() if t[0] == "LCTN"} == {("LCTN", "Eastmarch"),
                                                              ("LCTN", "Lost Knife Hideout")}
    pelts = targets("Gather Pelts")
    assert pelts[2] == ("MISC", "Bear Pelt") and pelts[1] == ("NPC_", "Jenassa")
    assert pelts[5] == ("LCTN", "Whiterun")
    (pq,) = by_name["Gather Pelts"]
    snap = {nb.entry(describe(b, f)).edid: v for f, v in pq.global_snapshots().items()}
    assert snap == {"manny_up_cp_count": 0.0, "manny_up_cp_total": 29.0}
    # structure check over everything: every filled alias value is a LCTN, NPC_ or item record
    types = set()
    for q in scan.by_form.values():
        for i in q.instances:
            for f in i.aliases.values():
                e = nb.entry(describe(b, f)) if f else None
                types.add(e.type if e else None)
    assert types - {None} <= {"LCTN", "NPC_", "BOOK", "ARMO", "MISC", "WEAP", "ALCH", "INGR"}


@needs_sample
def test_sample_sheet_has_globals_filled_and_aliases_neutral():
    if not os.path.exists(NAMES_PATH):
        pytest.skip("no names.json present")
    from skyrim_journal.sheet import build_sheet
    text = build_sheet(parse_save(open(SAMPLES[0], "rb").read()), "x.ess", NameBook.load(NAMES_PATH))
    assert "Collect [Pelt]s for [QuestGiver] (0/29)" in text
    assert "Find [QuestItem] inside [Dungeon]" in text
    assert "Kill the bandit leader located at [BountyLocation]" in text
    assert "| Skyrim Unbound |" not in text.split("#### Active quests")[1].split("<details>")[0]
    assert "Skyrim Unbound" in text.split("Background and radiant quests")[1]
