import glob
import os

import pytest

from skyrim_journal.cli import main
from skyrim_journal.parser import parse_save
from skyrim_journal.parser.globaldata import (parse_global_variables, parse_misc_stats,
                                              parse_player_location, walk_tables)
from skyrim_journal.parser.player import parse_player_base
from skyrim_journal.parser.refs import describe_form_id

def _sample(prefix):
    found = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "samples", prefix + "*.ess")))
    return found[0] if found else None


SAVE5, SAVE6 = _sample("Save5_"), _sample("Save6_")
pytestmark = pytest.mark.skipif(SAVE5 is None, reason="no real sample save (Save5_*.ess) present")


@pytest.fixture(scope="module")
def parsed():
    with open(SAVE5, "rb") as f:
        return parse_save(f.read())


def test_player_npc(parsed):
    from skyrim_journal.parser.body import payload_decompress
    b = parsed.body
    cf = next(c for c in b.change_forms if c.form_type == 9 and c.form_id == 7)
    data, _, _ = payload_decompress(cf, parsed.header.compression_type)
    p = parse_player_base(data, cf.change_flags, b.form_id_array)
    assert (p.name, p.level, p.consumed, p.total) == ("Plays-With-Scales", 6, 143, 277)
    assert p.race_ref == 0x13740  # ArgonianRace, matches header race
    # Argonian racial bonuses on a base of 15
    assert p.skills["Lockpicking"] == 25
    for s in ("LightArmor", "Pickpocket", "Sneak", "Alteration", "Restoration"):
        assert p.skills[s] == 20
    assert p.skills["OneHanded"] == 15 and set(p.skill_offsets.values()) == {0}
    assert len(p.factions) == 6 and p.factions[0][0] == 0xDB1  # PlayerFaction


def test_global_tables_and_misc_stats(parsed):
    b = parsed.body
    entries = walk_tables(b)
    assert [sum(1 for e in entries if e.table == t) for t in (1, 2, 3)] == [9, 14, 5]
    stats = {s.name: s.value for s in parse_misc_stats(b)}
    assert len(stats) == 108
    assert stats["Gold Found"] == 2132 and stats["Books Read"] == 20
    assert stats["Days Passed"] == 6
    gv = parse_global_variables(b)
    assert len(gv) == 1631 and gv[0x35] == 201.0 and gv[0x3A] == 20.0
    loc = parse_player_location(b)
    assert loc.worldspace == 0x1691D and (loc.coord_x, loc.coord_y) == (33, 9)


def test_form_id_description():
    assert describe_form_id(0x00000DB1, ["Skyrim.esm"], []) == "Skyrim.esm:000DB1"
    assert describe_form_id(0xFE001ABC, [], ["a.esl", "b.esl"]) == "b.esl:ABC"
    assert describe_form_id(0xFF000001, [], []) == "created:000001"


def test_cli_sections(capsys):
    assert main(["inspect", "--save", SAVE5]) == 0
    out = capsys.readouterr().out
    assert "== Player ==" in out and "Plays-With-Scales" in out and "== Misc stats (108) ==" in out
