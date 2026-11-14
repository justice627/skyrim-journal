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
from skyrim_journal.sheet import build_sheet

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
    assert "| `Skyrim.esm:01DBFC` | 100 | 10, 20, 30, 40, 41, 42, 60, 70, 75, 80, 100 |" in text
    assert "Adamant (`Adamant.esp`" in text and "Skyrim Unbound (`Skyrim Unbound.esp`" in text
    assert "31 full plugins and 45 light plugins (76 total)." in text
    assert text.count("<details>") == text.count("</details>") == 3
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
    assert sorted(os.listdir(save_dir)) == before   # nothing written next to the save


@needs_sample
def test_cli_sheet_bad_names_file(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("[]")
    assert main(["sheet", "--save", SAMPLES[0], "--names", str(bad)]) == 2
    assert "names file must be a JSON object" in capsys.readouterr().err
