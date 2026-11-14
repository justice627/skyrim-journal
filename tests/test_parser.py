import json
import struct

import pytest

from fixture_builder import PLAYER_PAYLOAD, build_save
from skyrim_journal.cli import main
from skyrim_journal.parser import (BadMagicError, DecompressionError, FormatError,
                                   TruncatedFileError, UnsupportedVersionError, parse_save)


@pytest.fixture
def save():
    return build_save()


def test_happy_path(save):
    p = parse_save(save)
    h, b = p.header, p.body
    assert (h.version, h.player_name, h.player_level, h.compression_name) == (12, "Dovahkiin", 17, "lz4")
    assert h.player_location == "Whiterun" and h.filetime_iso.startswith("2022")
    assert b.plugins == ["Skyrim.esm", "Update.esm"] and b.light_plugins == ["LightMod.esl"]
    assert b.form_version == 78 and b.table["changeFormCount"] == 5
    assert len(b.change_forms) == 5
    quest = b.change_forms[2]
    assert quest.form_type_name == "QUST" and quest.form_id == 0x02012345  # via formIDArray
    assert b.change_forms[3].form_id == 0xFF001234
    assert {s["name"]: s["count"] for s in p.type_summary()} == {"REFR": 2, "ACHR": 1, "NPC_": 1, "QUST": 1}


def test_player_records(save):
    recs = {r["role"]: r for r in parse_save(save).player_records()}
    achr = recs["ACHR"]
    assert achr["form_id"] == "0x00000014" and achr["change_flags"] == "0x08000074"
    assert achr["uncompressed_length"] == 400 and achr["payload_codec"] == "lz4"
    assert achr["first_bytes_hex"].split()[:3] == ["00", "01", "02"]
    assert len(achr["first_bytes_hex"].split()) == 64
    assert recs["NPC_"]["payload_codec"] == "none"


@pytest.mark.parametrize("base", ["screenshot", "block"])
@pytest.mark.parametrize("incl", [True, False])
def test_offset_base_and_header_size_variants(base, incl):
    p = parse_save(build_save(offset_base=base, header_includes_screenshot=incl))
    assert len(p.body.change_forms) == 5
    assert p.header.header_includes_screenshot is incl


def test_bad_magic():
    with pytest.raises(BadMagicError):
        parse_save(b"NOTASAVEFILE_AT_ALL" * 5)


def test_unsupported_version(save):
    bad = bytearray(save)
    bad[17:21] = struct.pack("<I", 99)
    with pytest.raises(UnsupportedVersionError, match="99"):
        parse_save(bytes(bad))


@pytest.mark.parametrize("cut", [5, 30, 60])
def test_truncated_header(save, cut):
    with pytest.raises(TruncatedFileError):
        parse_save(save[:cut])


def test_truncated_body(save):
    with pytest.raises(TruncatedFileError, match="compressed body"):
        parse_save(save[:-10])


def test_corrupt_lz4(save):
    h = parse_save(save).header
    bad = bytearray(save)
    for i in range(h.data_start, h.data_start + 40):
        bad[i] = 0xFF
    with pytest.raises(DecompressionError, match="lz4"):
        parse_save(bytes(bad))


def test_implausible_string_length(save):
    bad = bytearray(save)
    bad[25:27] = b"\xff\xff"  # playerName length
    with pytest.raises(FormatError, match="playerName"):
        parse_save(bytes(bad))


def test_cli_human_and_json(tmp_path, capsys, save):
    f = tmp_path / "s.ess"
    f.write_bytes(save)
    assert main(["inspect", "--save", str(f)]) == 0
    out = capsys.readouterr().out
    assert "Dovahkiin" in out and "LightMod.esl" in out and "QUST" in out
    assert main(["inspect", "--save", str(f), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["player_records"]
    assert f.read_bytes() == save


def test_cli_error_exit(tmp_path, capsys):
    f = tmp_path / "bad.ess"
    f.write_bytes(b"garbage garbage garbage")
    assert main(["inspect", "--save", str(f)]) == 1
    assert "BadMagicError" in capsys.readouterr().err
    assert main(["inspect", "--save", str(tmp_path / "nope")]) == 2
