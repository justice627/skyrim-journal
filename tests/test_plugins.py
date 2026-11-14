"""Tests for skyrim_journal.plugins against synthetic plugin files."""
import json
import struct
import zlib

import lz4.frame

from skyrim_journal.plugins import export


def sub(t, data, size=None):
    return t + struct.pack("<H", len(data) if size is None else size) + data


def z(s):
    return s.encode() + b"\x00"


def rec(t, fid, subs=b"", flags=0, compress=False):
    if compress:
        subs = struct.pack("<I", len(subs)) + zlib.compress(subs)
        flags |= 0x00040000
    return t + struct.pack("<IIIIHH", len(subs), flags, fid, 0, 44, 0) + subs


def grup(label, content, gtype=0):
    return b"GRUP" + struct.pack("<I", 24 + len(content)) + label + struct.pack("<iII", gtype, 0, 0) + content


def tes4(flags=0, masters=()):
    s = sub(b"HEDR", struct.pack("<fII", 1.7, 0, 0x800))
    for m in masters:
        s += sub(b"MAST", z(m)) + sub(b"DATA", b"\x00" * 8)
    return rec(b"TES4", 0, s, flags)


def write(path, data):
    path.write_bytes(data)
    return path


def run(tmp_path, args):
    out = tmp_path / "names.json"
    assert export.main(args + ["--out", str(out)]) == 0
    return json.loads(out.read_text(encoding="utf-8"))


def make_master(d):
    big = b"X" * 70000
    quest = rec(b"QUST", 0x000800, sub(b"EDID", z("MQ101")) + sub(b"FULL", z("Unbound")))
    weap = rec(b"WEAP", 0x000801, sub(b"EDID", z("IronSword")) + sub(b"FULL", z("Iron Sword")),
               compress=True)
    # oversized DESC before EDID/FULL forces XXXX handling
    armo = rec(b"ARMO", 0x000802,
               sub(b"XXXX", struct.pack("<I", len(big))) + sub(b"DESC", big, 0)
               + sub(b"EDID", z("ArmorX")) + sub(b"FULL", z("Caf\xe9".encode("cp1252").decode("latin1"))))
    junk = rec(b"REFR", 0x000900, b"garbage")
    data = tes4(0x1) + grup(b"QUST", quest) + grup(b"WEAP", weap) + grup(b"ARMO", armo) \
        + grup(b"REFR", junk)
    return write(d / "Master.esm", data)


def test_full_export(tmp_path):
    d = tmp_path / "Data"
    d.mkdir()
    make_master(d)
    # override of master record 0x800 (top byte 0) and a new record (top byte 1)
    write(d / "Child.esp", tes4(0, ["master.ESM"]) + grup(
        b"QUST", rec(b"QUST", 0x00000800, sub(b"EDID", z("MQ101")) + sub(b"FULL", z("Unbound II")))
        + rec(b"QUST", 0x01000801, sub(b"EDID", z("ChildQ")))))
    # light plugin: id 0x000ABC in a plugin with no masters (top byte 0)
    write(d / "Tiny.esl", tes4(0x200) + grup(
        b"MISC", rec(b"MISC", 0x00000ABC, sub(b"EDID", z("TinyMisc")) + sub(b"FULL", z("Gem")))))
    # localized plugin with loose strings (case-insensitive dir/file names)
    loc = grup(b"PERK", rec(b"PERK", 0x00000800, sub(b"EDID", z("LocPerk")) + sub(b"FULL", struct.pack("<I", 7))))
    write(d / "Loc.esp", tes4(0x80) + loc)
    (d / "STRINGS").mkdir()
    blob = z("Hello")
    strings = struct.pack("<II", 1, len(blob)) + struct.pack("<II", 7, 0) + blob
    write(d / "STRINGS" / "LOC_English.STRINGS", strings)
    # localized without strings
    write(d / "NoStr.esp", tes4(0x80) + grup(
        b"PERK", rec(b"PERK", 0x00000800, sub(b"EDID", z("Lost")) + sub(b"FULL", struct.pack("<I", 9)))))
    write(d / "Bad.esp", b"not a plugin at all, definitely")
    write(d / "Trunc.esp", tes4(0) + b"GRUP" + struct.pack("<I", 9999) + b"QUST" + b"\0" * 12)

    j = run(tmp_path, ["--data", str(d)])
    meta = j.pop("_meta")
    assert j["Master.esm:000800"] == {"edid": "MQ101", "name": "Unbound II", "type": "QUST"}  # overridden
    assert j["Master.esm:000801"] == {"edid": "IronSword", "name": "Iron Sword", "type": "WEAP"}
    assert j["Master.esm:000802"]["edid"] == "ArmorX"
    assert j["Master.esm:000802"]["name"] == "Caf\xe9"
    assert j["Child.esp:000801"] == {"edid": "ChildQ", "type": "QUST"}
    assert j["Tiny.esl:000ABC"]["name"] == "Gem"
    assert j["Loc.esp:000800"] == {"edid": "LocPerk", "name": "Hello", "type": "PERK"}
    assert j["NoStr.esp:000800"] == {"edid": "Lost", "type": "PERK"}
    assert not any(k.startswith("Bad.esp") for k in j)
    assert not any(v["type"] == "REFR" for v in j.values())
    skipped = {s["plugin"].rsplit("/", 1)[-1] for s in meta["skipped"]}
    assert skipped == {"Bad.esp", "Trunc.esp"}
    assert meta["localized_plugins_without_strings"] == ["NoStr.esp"]
    assert meta["plugins"]["Master.esm"]["records"] == 3
    assert meta["plugins"]["Loc.esp"]["strings"].startswith("loose:")
    assert meta["plugin_count"] == 5 and meta["tool_version"]


def test_light_master_override_and_order(tmp_path):
    d = tmp_path / "Data"
    d.mkdir()
    write(d / "Tiny.esl", tes4(0x200) + grup(
        b"GLOB", rec(b"GLOB", 0x00000801, sub(b"EDID", z("G1")))))
    # override of a light master's record; upper bits beyond 12 ignored
    write(d / "A.esp", tes4(0, ["Tiny.esl"]) + grup(
        b"GLOB", rec(b"GLOB", 0x00000801, sub(b"EDID", z("G1b")))))
    lo = tmp_path / "plugins.txt"
    lo.write_text("# c\n*Tiny.esl\n*A.esp\nMissing.esp\n")
    j = run(tmp_path, ["--data", str(d), "--load-order", str(lo)])
    assert j["Tiny.esl:000801"]["edid"] == "G1b"
    assert any(s["plugin"] == "Missing.esp" for s in j["_meta"]["skipped"])


def test_mods_folder_one_level(tmp_path):
    mods = tmp_path / "mods"
    (mods / "ModA").mkdir(parents=True)
    make_master(mods / "ModA")
    j = run(tmp_path, ["--data", str(mods)])
    assert "Master.esm:000800" in j


def test_bsa_strings(tmp_path):
    d = tmp_path / "Data"
    d.mkdir()
    write(d / "Loc.esp", tes4(0x80) + grup(
        b"PERK", rec(b"PERK", 0x00000800, sub(b"EDID", z("P")) + sub(b"FULL", struct.pack("<I", 3)))))
    blob = z("From BSA")
    payload = struct.pack("<II", 1, len(blob)) + struct.pack("<II", 3, 0) + blob
    write(d / "Skyrim - Interface.bsa", build_bsa("strings", "loc_english.strings", payload, True))
    j = run(tmp_path, ["--data", str(d)])
    assert j["Loc.esp:000800"]["name"] == "From BSA"
    assert j["_meta"]["plugins"]["Loc.esp"]["strings"] == "bsa:Skyrim - Interface.bsa"


def build_bsa(folder, fname, payload, compressed):
    """Single-file v105 archive with embedded names and a toggled compression bit."""
    full = f"{folder}\\{fname}".encode()
    body = bytes([len(full)]) + full
    if compressed:
        body += struct.pack("<I", len(payload)) + lz4.frame.compress(payload)
    else:
        body += payload
    flags = 0x1 | 0x2 | 0x100 | (0x4 if compressed else 0)
    fn_blob = z(fname)
    fold = z(folder)
    folder_rec_size = 24
    block_off = 36 + folder_rec_size
    data_off = block_off + 1 + len(fold) + 16 + len(fn_blob)
    out = b"BSA\x00" + struct.pack("<IIIIIIIHH", 105, 36, flags, 1, 1, len(fold), len(fn_blob), 0, 0)
    out += struct.pack("<QIIQ", 0, 1, 0, block_off + len(fn_blob))
    out += bytes([len(fold)]) + fold + struct.pack("<QII", 0, len(body), data_off) + fn_blob
    return out + body
