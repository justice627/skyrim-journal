import glob
import json
import os
import struct

import pytest

from skyrim_journal.cli import main
from skyrim_journal.names import NameBook, NamesFileError, normalize_key
from skyrim_journal.parser import parse_save
from skyrim_journal.parser.globaldata import parse_misc_stats
from skyrim_journal.parser.playerstate import (SKILL_NAMES, find_actor_values, find_inventory,
                                               find_skill_block, parse_player_state)
from skyrim_journal.parser.quests import parse_quest_stages, parse_quests
from types import SimpleNamespace

from skyrim_journal.parser.quests import QuestProgress
from skyrim_journal.sheet import _perk_section, _quest_section, build_sheet

SAMPLES = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "samples", "*.ess")))
needs_sample = pytest.mark.skipif(not SAMPLES, reason="no real sample save present")


# ---- synthetic unit tests (always run) ---------------------------------------------------

def test_quest_stage_decode():
    # 2-byte header, vsval 3<<2 = 0x0C, stages (0,1) (10,0) (255,1), trailing bytes ignored
    data = bytes([0x11, 0x00, 0x0C]) + b"\x00\x00\x01" + b"\x0a\x00\x00" + b"\xff\x00\x01" + b"\x99"
    assert parse_quest_stages(data) == [(0, 1), (10, 0), (255, 1)]
    with pytest.raises(Exception):
        parse_quest_stages(bytes([0x11, 0x00, 0x40]))  # count 16 overruns


def test_actor_values_need_all_18_skills_in_order():
    pairs = b"".join(struct.pack("<If", 6 + i, 15.0 + i) for i in range(18))
    pairs += struct.pack("<If", 24, 120.0) + struct.pack("<If", 25, 110.0)
    pairs += struct.pack("<If", 26, 120.0) + struct.pack("<If", 27, 0.7)
    av = find_actor_values(b"\x00" * 7 + pairs + b"\x01\x02")
    assert av[6] == 15.0 and av[23] == 32.0 and av[24] == 120.0 and av[26] == 120.0
    assert 27 not in av
    broken = pairs[:8 * 5] + struct.pack("<If", 99, 1.0) + pairs[8 * 6:]
    assert find_actor_values(broken) == {}


def test_skill_block_must_match_levels():
    levels = {n: 15.0 + i for i, n in enumerate(SKILL_NAMES)}
    blk = struct.pack("<ffI", 57.0, 225.0, 18)
    blk += b"".join(struct.pack("<3fI", levels[n], 1.0, 100.0, 0) for n in SKILL_NAMES)
    assert find_skill_block(blk, 57.0, 225.0, levels)[3] == (18.0, 1.0, 100.0)
    assert find_skill_block(blk, 58.0, 225.0, levels) is None
    assert find_skill_block(blk, 57.0, 225.0, {**levels, "Block": 99.0}) is None


def test_inventory_walk_with_extra_data():
    fa = []
    gold = b"\x40\x00\x0f" + struct.pack("<i", 1157) + b"\x00"
    pick = b"\x40\x00\x0a" + struct.pack("<i", 8) + b"\x00"
    worn = b"\x41\x39\x13" + struct.pack("<i", 1) + b"\x04\x04\x16"
    alias = (b"\x00\x46\x59" + struct.pack("<i", 1) + b"\x04\x0c" + b"\x88\x04" + b"\x00\x39\x45"
             + struct.pack("<I", 0) + b"\x9f" + b"\x02\x00\x14\x00\x00\x00" + b"\x1c\x80\x0f\xd0")
    fa = [0] * 0x5000
    fa[0x4659 - 1] = 0x0A001234
    blob = b"\xaa\xbb" + bytes([4 << 2]) + worn + gold + pick + alias + b"\xff\xff"
    # count byte 4<<2 = 0x10 is a 1-byte vsval
    items = find_inventory(blob, fa)
    assert items is not None and len(items) == 4
    assert [i.count for i in items] == [1, 1157, 8, 1]
    assert items[0].worn and not items[1].worn
    # an unknown extra type makes the walk fail rather than guess
    bad = b"\x04" + (b"\x41\x39\x13" + struct.pack("<i", 1) + b"\x04\x04\x7f") + gold
    assert find_inventory(bad, fa) is None


def test_names_keys_and_labels(tmp_path):
    assert normalize_key("SKYRIM.esm:00000f") == ("skyrim.esm", 15)
    assert normalize_key("nocolon") is None
    p = tmp_path / "n.json"
    p.write_text(json.dumps({"Skyrim.ESM:000DB1": {"edid": "PF"},
                             "mod.esp:12": {"edid": "E", "name": "Nice", "type": "QUST"},
                             "empty.esp:1": {"type": "QUST"}}))
    nb = NameBook.load(str(p))
    assert nb.label("mod.esp:000012") == "Nice"          # name wins, leading zeros irrelevant
    assert nb.label("Skyrim.esm:000DB1") == "PF"         # user entry overrides built-in edid
    assert nb.label("Skyrim.esm:00000F") == "Gold"       # built-in
    assert nb.label("empty.esp:000001") == "`empty.esp:000001`"  # no name or edid: raw
    assert nb.label("other.esp:000001") == "`other.esp:000001`"
    assert nb.user_entries == 3


def test_names_file_errors(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    with pytest.raises(NamesFileError):
        NameBook.load(str(p))
    p.write_text(json.dumps({"nocolon": {}}))
    with pytest.raises(NamesFileError):
        NameBook.load(str(p))
    p.write_text(json.dumps({"a.esp:1": "string"}))
    with pytest.raises(NamesFileError):
        NameBook.load(str(p))
    with pytest.raises(NamesFileError):
        NameBook.load(str(tmp_path / "missing.json"))


# ---- real sample ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parsed():
    with open(SAMPLES[0], "rb") as f:
        return parse_save(f.read())


@needs_sample
def test_quests_real(parsed):
    qs = parse_quests(parsed.body, parsed.header.compression_type)
    assert len(qs) == 289
    assert sum(1 for q in qs if q.reached_nonzero) == 127
    unbound = next(q for q in qs if q.reached_nonzero and q.highest == 100 and 90 in q.reached)
    assert unbound.reached == [0, 1, 10, 20, 90, 100]


@needs_sample
def test_player_state_real(parsed):
    h = parsed.header
    st = parse_player_state(parsed.body, h.compression_type, h.cur_exp, h.lvlup_exp)
    base = parsed.player_info()["skills"]
    cur = st.skills
    assert cur["OneHanded"] == 21 and cur["LightArmor"] == 23 and cur["Restoration"] == 22
    # the sum of level-ups equals the save's own "Skill Increases" counter
    stats = {s.name: s.value for s in parse_misc_stats(parsed.body)}
    assert sum(cur[n] - base[n] for n in SKILL_NAMES) == stats["Skill Increases"] == 16
    assert st.attributes == {"Health": 120.0, "Magicka": 110.0, "Stamina": 120.0}
    assert sum(st.attributes.values()) == 300 + 10 * (h.player_level - 1)
    # the independent skill block agrees with the actor-value list
    assert [round(r[0]) for r in st.skill_block] == [cur[n] for n in SKILL_NAMES]
    assert all(0 <= r[1] <= r[2] for r in st.skill_block)
    # inventory: gold and lockpicks, walked to the exact end of 38 entries
    assert len(st.inventory) == 38 and not st.inventory_is_partial
    assert st.gold() == 1157 and st.lockpicks() == 8
    assert stats["Most Gold Carried"] >= st.gold()
    assert sum(1 for i in st.inventory if i.worn) == 7
    assert len(st.perks) == 102 and all(r == 1 for _, r in st.perks)


@needs_sample
def test_sheet_content(parsed):
    text = build_sheet(parsed, "x.ess", NameBook())
    assert text.startswith("---\ntype: snapshot\narea: gaming\ncreated: 2026-11-13\n"
                           "character: Plays-With-Scales\nsave: x.ess\n---\n")
    assert "Snapshot of Plays-With-Scales from save 5, 2026-11-13. In-game: day 12, month 6, year 201" in text
    assert "| Race / Sex | ArgonianRace / Male |" in text
    assert "| Level | 6 (57 / 225 XP) |" in text and "| Location | Windhelm |" in text
    assert "| OneHanded | 15 | 21 |" in text
    assert "| Gold | 1157 |" in text and "| Lockpicks | 8 |" in text
    assert "289 quests" in text and "127 have a stage" in text
    assert ("| `Skyrim.esm:01DBFC` | 100 | 10, 20, 30, 40, 41, 42, 60, 70, 75, 80, 100 | save flag |"
            in text)
    assert "#### Completed (6)" in text and "#### Active (8)" in text
    assert "(waived: no names loaded)" in text
    assert "Adamant (`Adamant.esp`" in text and "Skyrim Unbound (`Skyrim Unbound.esp`" in text
    assert "31 full plugins and 45 light plugins (76 total)." in text
    assert text.count("<details>") == text.count("</details>") == 4
    assert "a names file exported with perk trees" in text and "All perks (102)" in text
    for sec in ("Who", "Skills", "Factions", "Gold and inventory", "Quests", "Activity",
                "Load order", "Not yet extracted"):
        assert f"### {sec}\n" in text


@needs_sample
def test_cli_sheet_stdout_out_and_names(tmp_path, capsys):
    save_dir = os.path.dirname(os.path.abspath(SAMPLES[0]))
    before = sorted(os.listdir(save_dir))
    assert main(["sheet", "--save", SAMPLES[0]]) == 0
    out = capsys.readouterr().out
    assert out.startswith("---\ntype: snapshot") and "`Skyrim.esm:01DBFC`" in out

    names = tmp_path / "names.json"
    names.write_text(json.dumps({"skyrim.esm:01dbfc": {"edid": "Q1", "name": "A Named Quest",
                                                       "type": "QUST"}}))
    dest = tmp_path / "sheet.md"
    assert main(["sheet", "--save", SAMPLES[0], "--out", str(dest), "--names", str(names)]) == 0
    assert capsys.readouterr().out == ""
    text = dest.read_text(encoding="utf-8")
    assert "| A Named Quest | 100 |" in text and "`Skyrim.esm:01DBFC`" not in text
    assert "#### Completed (1)" in text   # only the named quest passes the display-name rule
    assert sorted(os.listdir(save_dir)) == before   # nothing written next to the save


@needs_sample
def test_cli_sheet_bad_names_file(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("[]")
    assert main(["sheet", "--save", SAMPLES[0], "--names", str(bad)]) == 2
    assert "names file must be a JSON object" in capsys.readouterr().err


# ---- perk grouping and quest classification on synthetic data ------------------------------

def _body(plugins=("Skyrim.esm", "Mod.esp")):
    return SimpleNamespace(plugins=list(plugins), light_plugins=[])


def _perk_names(extra_trees=True):
    d = {"Skyrim.esm:000450": {"edid": "AVSmithing", "name": "Smithing", "type": "AVIF"},
         "Skyrim.esm:00044C": {"edid": "AVOneHanded", "name": "One-handed", "type": "AVIF"},
         "Skyrim.esm:000810": {"edid": "A1", "name": "Armsman", "type": "PERK",
                               "next": "Skyrim.esm:000811"},
         "Skyrim.esm:000811": {"edid": "A2", "name": "Armsman II", "type": "PERK",
                               "next": "Skyrim.esm:000812"},
         "Skyrim.esm:000812": {"edid": "A3", "name": "Armsman III", "type": "PERK"},
         "Skyrim.esm:000820": {"edid": "S1", "name": "Steel Smithing", "type": "PERK"},
         "Skyrim.esm:000830": {"edid": "Plumb", "name": "Stagger Controller Perk", "type": "PERK"},
         "Mod.esp:000800": {"edid": "M1", "name": "Mod Perk", "type": "PERK"}}
    if extra_trees:   # deliberately listed out of skill order; the cycle must not hang
        d["_perk_trees"] = {
            "Skyrim.esm:000450": {"skill": "AVSmithing", "skill_name": "Smithing",
                                  "perks": ["Skyrim.esm:000820", "Mod.esp:000800"]},
            "Skyrim.esm:00044C": {"skill": "AVOneHanded", "skill_name": "One-handed",
                                  "perks": ["Skyrim.esm:000810"]}}
        d["Skyrim.esm:000812"]["next"] = "Skyrim.esm:000810"      # cycle
    return d


def test_names_exposes_perk_trees_and_new_fields():
    nb = NameBook(_perk_names())
    assert nb.has_perk_trees and [t.skill for t in nb.perk_trees()] == ["AVSmithing", "AVOneHanded"]
    assert nb.entry("skyrim.esm:810").next == "Skyrim.esm:000811"
    assert not NameBook({"_meta": {"x": 1}}).has_perk_trees
    with pytest.raises(NamesFileError):
        NameBook({"_perk_trees": []})
    with pytest.raises(NamesFileError):
        NameBook({"a.esp:1": {"quest_type": "x"}})
    q = NameBook({"a.esp:1": {"edid": "Q", "quest_type": 8, "objectives": 2,
                              "complete_stages": [100], "fail_stages": []}}).entry("a.esp:1")
    assert (q.quest_type, q.objectives, q.complete_stages, q.fail_stages) == (8, 2, (100,), ())


def test_perk_section_groups_by_skill_and_ranks():
    # saved perks: rank 1 and 2 of Armsman, a smithing perk, a mod perk in a tree, plumbing
    perks = [(0x000811, 2), (0x000810, 1), (0x000820, 1), (0x01000800, 1), (0x000830, 1)]
    text = "\n".join(_perk_section(perks, _body(), NameBook(_perk_names())))
    rows = [ln for ln in text.splitlines() if ln.startswith("| ") and "Skill" not in ln]
    # One-handed first (skill order), Armsman shown once at its highest owned rank
    assert rows[0] == "| One-handed | Armsman II | 2 of 3 |"
    assert "| Smithing | Steel Smithing |  |" in rows and "| Smithing | Mod Perk |  |" in rows
    assert "Perks chosen in skill trees: 3" in text
    assert "Other perks (granted by mods, quests and abilities): 1" in text
    other = text.split("<details>")[1]
    assert "Stagger Controller Perk" in other and "Armsman" not in other


def test_perk_section_without_trees_and_with_unmatched_trees():
    perks = [(0x000830, 1), (0x000820, 1)]
    text = "\n".join(_perk_section(perks, _body(), NameBook(_perk_names(False))))
    assert "needed to tell chosen perks apart" in text and "<summary>All perks (2)" in text
    assert "Skill |" not in text
    nb = NameBook(_perk_names())
    text = "\n".join(_perk_section([(0x000830, 1)], _body(), nb))
    assert "None of the player's perks was found in the skill trees" in text


def _q(fid, stages, flags=None, objectives=()):
    return QuestProgress(fid, [(s, 1) for s in stages], flags, list(objectives))


def test_quest_section_with_exporter_fields():
    nb = NameBook({
        "Skyrim.esm:000801": {"edid": "Side", "name": "Side Quest A", "type": "QUST",
                              "quest_type": 8, "objectives": 3, "complete_stages": [100],
                              "fail_stages": [90]},
        "Skyrim.esm:000802": {"edid": "Main", "name": "Main Quest B", "type": "QUST",
                              "quest_type": 1, "objectives": 4, "complete_stages": [200],
                              "fail_stages": []},
        "Skyrim.esm:000803": {"edid": "Misc", "name": "Done by flag", "type": "QUST",
                              "quest_type": 6, "objectives": 1, "complete_stages": [],
                              "fail_stages": []},
        "Skyrim.esm:000804": {"edid": "Lost", "name": "Failed Quest", "type": "QUST",
                              "quest_type": 8, "objectives": 1, "complete_stages": [],
                              "fail_stages": [90]},
        "Skyrim.esm:000805": {"edid": "Dlg", "name": "Dialogue", "type": "QUST",
                              "quest_type": 0, "objectives": 0, "complete_stages": [],
                              "fail_stages": []},
        "Skyrim.esm:000806": {"edid": "Unstarted", "name": "Unstarted", "type": "QUST",
                              "quest_type": 8, "objectives": 2, "complete_stages": [],
                              "fail_stages": []}})
    quests = [_q(0x801, [10, 100]), _q(0x802, [5, 50]), _q(0x803, [10], flags=0x2),
              _q(0x804, [10, 90]), _q(0x805, [10]), _q(0x806, [])]
    text = "\n".join(_quest_section(quests, _body(), nb, []))
    assert "#### Completed (2)" in text and "#### Active (1)" in text and "#### Failed (1)" in text
    assert "| Side Quest A | Side Quest | 100 | 10, 100 | completing stage 100 |" in text
    assert "| Done by flag | Misc | 10 | 10 | save flag |" in text
    assert "| Main Quest B | Main Quest | 50 | 5, 50 |" in text
    assert "| Failed Quest | Side Quest | 90 | 10, 90 | failing stage 90 |" in text
    assert "Background and radiant quests (1)" in text and "| Dialogue |" in text
    assert "Unstarted" not in text                      # no progress, not listed
    assert "guessed" not in text


def test_quest_section_fallback_uses_flags_and_never_guesses_status():
    nb = NameBook({"Skyrim.esm:000801": {"name": "Named done"}, "Skyrim.esm:000802": {"name": "Named shown"},
                   "Skyrim.esm:000803": {"name": "Named, objectives only"},
                   "Skyrim.esm:000804": {"edid": "OnlyEdid"}, "Skyrim.esm:000805": {"name": "Plain"}})
    quests = [_q(0x801, [200], flags=0x2, objectives=[(10, 3)]),
              _q(0x802, [10], flags=0x2001, objectives=[(10, 1)]),
              _q(0x803, [200], flags=0x0, objectives=[(15, 3)]),
              _q(0x804, [10], flags=0x2000), _q(0x805, [10], flags=0x11),
              _q(0x806, [1], flags=0x42)]
    text = "\n".join(_quest_section(quests, _body(), nb, []))
    assert "#### Completed (1)" in text and "| Named done | 200 | 200 | save flag |" in text
    assert "#### Active (1)" in text and "| Named shown |" in text
    assert "#### Started, status unknown (1)" in text and "| Named, objectives only |" in text
    assert "guessed" in text and "Type" not in text
    assert "Background and radiant quests (3)" in text    # edid-only, plain, unnamed
    # failed flag lands in Failed once named
    nb2 = NameBook({"Skyrim.esm:000806": {"name": "Gone"}})
    text = "\n".join(_quest_section([_q(0x806, [1], flags=0x40)], _body(), nb2, []))
    assert "#### Failed (1)" in text and "| Gone | 1 | 1 | save flag |" in text


@needs_sample
def test_sample_flag_findings(parsed):
    """Quest flag bits established on the sample save (see parser/quests.py)."""
    qs = {q.form_id: q for q in parse_quests(parsed.body, parsed.header.compression_type)}
    done = {q.form_id for q in qs.values() if q.completed}
    assert 0x1DBFC in done and len(done) == 6                 # Rise in the East among them
    assert not any(q.failed for q in qs.values())             # 0x40 never set: unverified
    shown = {q.form_id for q in qs.values() if q.has_displayed_objective}
    assert len(shown) == 8 and not shown & done
    assert sum(1 for q in qs.values() for _, s in q.objectives if s == 3) == 16


@needs_sample
def test_sample_sheet_with_synthetic_perk_trees(parsed):
    from skyrim_journal.parser.playerstate import parse_player_state
    from skyrim_journal.parser.refs import describe_form_id
    h = parsed.header
    st = parse_player_state(parsed.body, h.compression_type, h.cur_exp, h.lvlup_exp)
    keys = [describe_form_id(f, parsed.body.plugins, parsed.body.light_plugins) for f, _ in st.perks]
    data = {"_perk_trees": {"Skyrim.esm:00044C": {"skill": "AVOneHanded",
                                                  "skill_name": "One-handed",
                                                  "perks": keys[:3]}}}
    text = build_sheet(parsed, "x.ess", NameBook(data))
    assert "Perks chosen in skill trees: 3" in text
    assert "Other perks (granted by mods, quests and abilities): 99" in text
    assert text.count("<details>") == text.count("</details>")
