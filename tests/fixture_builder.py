"""Builds a synthetic Skyrim SE save (version 12) in memory."""
import struct

import lz4.block

W = lambda s: struct.pack("<H", len(s)) + s.encode("cp1252")  # noqa: E731

PLAYER_PAYLOAD = bytes(range(200)) * 2  # 400 bytes, compressible


def refid(source: int, value: int) -> bytes:
    return ((source << 22) | value).to_bytes(3, "big")


def change_form(ref: bytes, flags: int, ftype: int, ver: int, payload: bytes,
                uncompressed_len: int = 0, width: int = 0) -> bytes:
    code = "BHI"[width]
    return (ref + struct.pack("<I", flags) + bytes([(width << 6) | ftype, ver])
            + struct.pack("<" + code * 2, len(payload), uncompressed_len) + payload)


def build_save(*, offset_base: str = "screenshot", header_includes_screenshot: bool = True,
               shot=(2, 2)) -> bytes:
    """offset_base: file-table offsets relative to 'screenshot' end or 'block' start (+8)."""
    plugins = ["Skyrim.esm", "Update.esm"]
    light = ["LightMod.esl"]
    pinfo = bytes([len(plugins)]) + b"".join(W(p) for p in plugins)
    linfo = struct.pack("<H", len(light)) + b"".join(W(p) for p in light)

    quest_payload = b"\x01\x02\x03\x04"
    comp_payload = lz4.block.compress(PLAYER_PAYLOAD, store_size=False)
    forms = [
        change_form(refid(1, 0x14), 0x08000074, 1, 74, comp_payload, len(PLAYER_PAYLOAD), width=1),
        change_form(refid(1, 0x07), 0x00000042, 9, 74, b"\xaa" * 10),
        change_form(refid(0, 1), 0x00000002, 8, 74, quest_payload),     # formIDArray[0]
        change_form(refid(2, 0x1234), 0x00000001, 0, 74, b"\xbb" * 3),  # created REFR
        change_form(refid(1, 0x0F), 0x00000001, 0, 74, b"\xcc" * 5),
    ]
    form_ids = [0x00012345 | (2 << 24)]  # plugin index 2 -> light/regular mod record

    head = bytes([78]) + struct.pack("<I", len(pinfo) + len(linfo)) + pinfo + linfo
    table_len = 10 * 4 + 15 * 4
    cf_idx = len(head) + table_len
    fa_idx = cf_idx + sum(map(len, forms))
    # Offsets are absolute: body index + base.
    base = 0  # filled below once the header size is known
    shot_w, shot_h = shot
    screenshot = b"\x7f" * (shot_w * shot_h * 4)
    fields = (struct.pack("<II", 12, 7) + W("Dovahkiin") + struct.pack("<I", 17) + W("Whiterun")
              + W("123.45") + W("NordRace") + struct.pack("<Hff", 0, 12.5, 100.0)
              + struct.pack("<Q", 133_000_000_000_000_000) + struct.pack("<II", shot_w, shot_h)
              + struct.pack("<H", 2))
    header_size = len(fields) + (len(screenshot) if header_includes_screenshot else 0)
    body_start = 13 + 4 + len(fields) + len(screenshot)
    base = body_start if offset_base == "screenshot" else body_start + 8

    table = struct.pack("<10I", base + fa_idx, 0, 0, 0, base + cf_idx, 0, 0, 0, 0, len(forms))
    body = head + table + b"\0" * 60 + b"".join(forms) + struct.pack("<I", len(form_ids)) \
        + b"".join(struct.pack("<I", f) for f in form_ids)
    comp = lz4.block.compress(body, store_size=False)
    return (b"TESV_SAVEGAME" + struct.pack("<I", header_size) + fields + screenshot
            + struct.pack("<II", len(body), len(comp)) + comp)
