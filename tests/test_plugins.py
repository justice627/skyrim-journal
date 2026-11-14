"""Tests for skyrim_journal.plugins against synthetic plugin files."""
import json
import struct
import zlib

import lz4.frame
import pytest

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
    assert j.pop("_perk_trees") == {} and meta["tool_version"] == "1.2.0"
    # overridden; QUST entries carry the quest fields (none of the subrecords exist here)
    assert j["Master.esm:000800"] == {"edid": "MQ101", "name": "Unbound II", "type": "QUST",
                                      "objectives": 0, "complete_stages": [], "fail_stages": []}
    assert j["Master.esm:000801"] == {"edid": "IronSword", "name": "Iron Sword", "type": "WEAP"}
    assert j["Master.esm:000802"]["edid"] == "ArmorX"
    assert j["Master.esm:000802"]["name"] == "Caf\xe9"
    assert j["Child.esp:000801"] == {"edid": "ChildQ", "type": "QUST", "objectives": 0,
                                     "complete_stages": [], "fail_stages": []}

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


def u32(*v):
    return struct.pack("<" + "I" * len(v), *v)


def avif(fid, edid, name, perks, extra_pnam_zero=True):
    """AVIF with a tree: one root group (PNAM 0) then one group per perk."""
    def group(perk, idx):
        return (sub(b"PNAM", u32(perk)) + sub(b"FNAM", u32(1)) + sub(b"XNAM", u32(2))
                + sub(b"YNAM", u32(3)) + sub(b"HNAM", struct.pack("<f", 0.5))
                + sub(b"VNAM", struct.pack("<f", 0.5)) + sub(b"SNAM", u32(fid))
                + sub(b"CNAM", u32(idx + 1)) + sub(b"INAM", u32(idx)))
    body = sub(b"EDID", z(edid)) + sub(b"FULL", z(name))
    groups = ([0] if extra_pnam_zero and perks else []) + list(perks)
    body += b"".join(group(p, i) for i, p in enumerate(groups))
    return rec(b"AVIF", fid, body)


def perk(fid, edid, name, nxt=0, data=(0, 0, 1, 1, 0)):
    body = sub(b"EDID", z(edid)) + sub(b"FULL", z(name)) + sub(b"DATA", bytes(data))
    if nxt:
        body += sub(b"NNAM", u32(nxt))
    return rec(b"PERK", fid, body)


def test_perk_trees_overrides_and_chains(tmp_path):
    d = tmp_path / "Data"
    d.mkdir()
    write(d / "Skyrim.esm", tes4(0x1) + grup(b"PERK", (
        perk(0x000810, "Armsman1", "Armsman", nxt=0x000811, data=(0, 0, 2, 1, 0))
        + perk(0x000811, "Armsman2", "Armsman", nxt=0x000812)
        + perk(0x000812, "Armsman3", "Armsman")
        + perk(0x000820, "Plumbing", "Plumbing", data=(0, 0, 1, 0, 1))))
        + grup(b"AVIF", avif(0x00044C, "AVOneHanded", "One-handed", [0x000810, 0x000810])))
    # overhaul: overrides the AVIF (perk ids relative to its masters: 0x00 = Skyrim.esm,
    # 0x01 = the overhaul itself) and adds a perk of its own
    write(d / "Overhaul.esp", tes4(0, ["Skyrim.esm"]) + grup(b"PERK", (
        perk(0x01000800, "OvPerk", "Overhaul Perk", nxt=0x01000801)
        + perk(0x01000801, "OvPerk2", "Overhaul Perk II")))
        + grup(b"AVIF", avif(0x0000044C, "AVOneHanded", "One-handed",
                             [0x01000800, 0x00000820])))
    # a later plugin overriding the AVIF with an empty tree must not wipe the tree
    write(d / "Cosmetic.esp", tes4(0, ["Skyrim.esm"]) + grup(
        b"AVIF", rec(b"AVIF", 0x0000044C, sub(b"EDID", z("AVOneHanded"))
                     + sub(b"FULL", z("One-Handed")))))
    j = run(tmp_path, ["--data", str(d), "--load-order", str(write(tmp_path / "lo.txt", b"Skyrim.esm\nOverhaul.esp\nCosmetic.esp\n"))])
    assert j["_perk_trees"] == {"Skyrim.esm:00044C": {
        "skill": "AVOneHanded", "skill_name": "One-Handed",
        "perks": ["Overhaul.esp:000800", "Skyrim.esm:000820"]}}
    assert j["Skyrim.esm:000810"] == {"edid": "Armsman1", "name": "Armsman", "type": "PERK",
                                      "playable": True, "hidden": False,
                                      "next": "Skyrim.esm:000811"}
    assert "next" not in j["Skyrim.esm:000812"]
    assert j["Skyrim.esm:000820"]["playable"] is False and j["Skyrim.esm:000820"]["hidden"] is True
    assert j["Overhaul.esp:000800"]["next"] == "Overhaul.esp:000801"

    # without the overhaul the vanilla tree (duplicate PNAM collapsed, root 0 ignored) is kept
    j = run(tmp_path, ["--data", str(d), "--load-order", str(write(tmp_path / "lo2.txt", b"Skyrim.esm\n"))])
    assert j["_perk_trees"]["Skyrim.esm:00044C"]["perks"] == ["Skyrim.esm:000810"]
    assert j["_perk_trees"]["Skyrim.esm:00044C"]["skill_name"] == "One-handed"


def test_quest_fields(tmp_path):
    d = tmp_path / "Data"
    d.mkdir()

    def qust(fid, edid, dnam, stages=(), objectives=0):
        body = sub(b"EDID", z(edid)) + sub(b"FULL", z(edid)) + sub(b"DNAM", dnam)
        for idx, qsdt in stages:
            body += sub(b"INDX", struct.pack("<HBB", idx, 0, 0))
            for fl in qsdt:
                body += sub(b"QSDT", bytes([fl])) + sub(b"CNAM", z("log text"))
        for i in range(objectives):
            body += sub(b"QOBJ", struct.pack("<H", i)) + sub(b"NNAM", z("do it"))
        return rec(b"QUST", fid, body)

    dnam12 = struct.pack("<HBB", 1, 50, 5) + u32(0) + u32(8)          # Side Quest
    dnam8 = struct.pack("<HBB", 1, 50, 5) + u32(1)                   # Main Quest (short form)
    bad = struct.pack("<HBB", 1, 50, 5) + u32(0) + u32(99)           # implausible type
    write(d / "Q.esp", tes4(0) + grup(b"QUST", (
        qust(0x800, "SideQ", dnam12, [(10, [0]), (20, [0, 2]), (100, [1])], objectives=3)
        + qust(0x801, "MainQ", dnam8, [(5, [])])
        + qust(0x802, "OddQ", bad)
        + qust(0x803, "NoDnam", b"")  # empty DNAM: no type
    )))
    j = run(tmp_path, ["--data", str(d)])
    assert j["Q.esp:000800"] == {"edid": "SideQ", "name": "SideQ", "type": "QUST",
                                 "quest_type": 8, "objectives": 3,
                                 "complete_stages": [100], "fail_stages": [20],
                                 "objective_text": {"0": "do it", "1": "do it", "2": "do it"}}
    assert j["Q.esp:000801"]["quest_type"] == 1 and j["Q.esp:000801"]["objectives"] == 0
    assert "quest_type" not in j["Q.esp:000802"] and "quest_type" not in j["Q.esp:000803"]


def test_save_load_order(tmp_path, capsys):
    from fixture_builder import build_save
    d = tmp_path / "Data"
    d.mkdir()

    def q(edid):
        return grup(b"QUST", rec(b"QUST", 0x000800, sub(b"EDID", z(edid)) + sub(b"FULL", z(edid))))
    write(d / "Skyrim.esm", tes4(0x1) + q("Base"))
    write(d / "Update.esm", tes4(0x1, ["Skyrim.esm"]) + q("Updated"))
    write(d / "lightmod.ESL", tes4(0x200) + grup(
        b"MISC", rec(b"MISC", 0x000ABC, sub(b"EDID", z("Gem")))))
    write(d / "Inactive.esp", tes4(0, ["Skyrim.esm"]) + q("FromInactiveMod"))
    ess = tmp_path / "s.ess"
    ess.write_bytes(build_save())
    j = run(tmp_path, ["--data", str(d), "--save", str(ess)])
    assert j["Skyrim.esm:000800"]["edid"] == "Updated"            # not clobbered by Inactive.esp
    assert j["lightmod.ESL:000ABC"]["edid"] == "Gem"              # matched case-insensitively
    skipped = {s["plugin"].rsplit("/", 1)[-1]: s["reason"] for s in j["_meta"]["skipped"]}
    assert skipped == {"Inactive.esp": "not in load order"}
    assert j["_meta"]["plugin_count"] == 3

    # without --save the inactive plugin wins the override
    assert run(tmp_path, ["--data", str(d)])["Skyrim.esm:000800"]["edid"] == "FromInactiveMod"
    # --save and --load-order are mutually exclusive; unreadable saves are reported
    lo = write(tmp_path / "lo.txt", b"Skyrim.esm\n")
    with pytest.raises(SystemExit):
        export.main(["--data", str(d), "--save", str(ess), "--load-order", str(lo),
                     "--out", str(tmp_path / "x.json")])
    bad = write(tmp_path / "bad.ess", b"nope")
    assert export.main(["--data", str(d), "--save", str(bad), "--out", str(tmp_path / "x.json")]) == 2


def test_objective_text_localized_with_fallback_tables(tmp_path):
    d = tmp_path / "Data"
    d.mkdir()

    def qobj(i, text):
        return sub(b"QOBJ", struct.pack("<H", i)) + sub(b"FNAM", u32(0)) + sub(b"NNAM", text)

    body = (sub(b"EDID", z("LQ")) + sub(b"FULL", u32(1))
            + sub(b"INDX", struct.pack("<HBB", 10, 0, 0)) + sub(b"CNAM", u32(99))   # stage log, no NNAM
            + qobj(10, u32(2)) + qobj(20, u32(3)) + qobj(30, u32(404)) + qobj(40, b"\x01\x02"))
    write(d / "Loc.esp", tes4(0x80) + grup(b"QUST", rec(b"QUST", 0x800, body)))
    (d / "Strings").mkdir()

    def table(entries, prefixed):
        blob, offs = b"", []
        for sid, t in entries:
            offs.append((sid, len(blob)))
            blob += (struct.pack("<I", len(t) + 1) if prefixed else b"") + z(t)
        return (struct.pack("<II", len(entries), len(blob))
                + b"".join(struct.pack("<II", *o) for o in offs) + blob)

    write(d / "Strings" / "Loc_english.STRINGS", table([(1, "Quest"), (2, "Find it")], False))
    write(d / "Strings" / "Loc_english.DLSTRINGS", table([(3, "Bring it back")], True))
    j = run(tmp_path, ["--data", str(d)])
    q = j["Loc.esp:000800"]
    assert q["name"] == "Quest" and q["objectives"] == 4
    # 10 from STRINGS, 20 from DLSTRINGS, 30 unresolvable and 40 (bad length) left out
    assert q["objective_text"] == {"10": "Find it", "20": "Bring it back"}
    assert j["_meta"]["localized_plugins_without_strings"] == []

    # a localized plugin without any strings table: names stay absent, nothing crashes
    (d / "Strings" / "Loc_english.STRINGS").unlink()
    (d / "Strings" / "Loc_english.DLSTRINGS").unlink()
    j = run(tmp_path, ["--data", str(d)])
    assert "objective_text" not in j["Loc.esp:000800"]
    assert j["_meta"]["localized_plugins_without_strings"] == ["Loc.esp"]
