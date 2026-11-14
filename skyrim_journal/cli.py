from __future__ import annotations

import argparse
import json
import sys

from .parser import SaveParseError, parse_save


def _render(d: dict) -> str:
    h = d["header"]
    L = ["== Header =="]
    for k in ("version", "save_number", "player_name", "player_level", "player_location",
              "game_date", "player_race", "player_sex", "cur_exp", "lvlup_exp", "filetime_iso",
              "shot_width", "shot_height", "compression_type", "uncompressed_len",
              "compressed_len", "header_size", "header_includes_screenshot", "body_start",
              "data_start"):
        L.append(f"  {k}: {h[k]}")
    L.append(f"\n== Body ==\n  formVersion: {d['form_version']}  "
             f"pluginInfoSize: {d['plugin_info_size']}  offset base: {d['offset_base']}  "
             f"formIDArray entries: {d['form_id_array_count']}")
    L.append(f"\n== Plugins ({len(d['plugins'])}) ==")
    L += [f"  [{i:02X}] {p}" for i, p in enumerate(d["plugins"])]
    L.append(f"\n== Light plugins ({len(d['light_plugins'])}) ==")
    L += [f"  [FE:{i:03X}] {p}" for i, p in enumerate(d["light_plugins"])]
    L.append("\n== File location table ==")
    L += [f"  {k}: {v}" for k, v in d["file_location_table"].items()]
    L.append(f"\n== Change forms ({len(d['change_forms'])}) by type ==")
    L.append(f"  {'type':>4} {'name':<6} {'count':>7} {'bytes':>10}")
    for s in d["change_form_summary"]:
        L.append(f"  {s['type']:>4} {s['name']:<6} {s['count']:>7} {s['total_bytes']:>10}")
    L.append(f"\n== Player records ({len(d['player_records'])}) ==")
    if not d["player_records"]:
        L.append("  none found (ACHR 0x14 / NPC_ 0x7)")
    for p in d["player_records"]:
        L.append(f"  {p['role']} {p['form_id']} flags={p['change_flags']} version={p['version']} "
                 f"stored={p['length']} uncompressed={p['uncompressed_length']} "
                 f"payload_codec={p['payload_codec']} payload_size={p['payload_size']}")
        if p["payload_error"]:
            L.append(f"    payload error: {p['payload_error']}")
        L.append(f"    first bytes: {p['first_bytes_hex']}")
    if d["warnings"]:
        L.append("\n== Warnings ==")
        L += [f"  {w}" for w in d["warnings"]]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="skyrim_journal")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ins = sub.add_parser("inspect", help="Print the structure of a save (read-only)")
    ins.add_argument("--save", required=True, help="path to .ess file")
    ins.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    try:
        with open(args.save, "rb") as f:  # read-only
            data = f.read()
    except OSError as e:
        print(f"error: cannot read {args.save}: {e}", file=sys.stderr)
        return 2
    try:
        d = parse_save(data).to_dict()
    except SaveParseError as e:
        print(f"error ({type(e).__name__}): {e}", file=sys.stderr)
        return 1
    print(json.dumps(d, indent=2) if args.json else _render(d))
    return 0
