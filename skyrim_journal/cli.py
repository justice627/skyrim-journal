from __future__ import annotations

import argparse
import json
import os
import sys

from .names import NameBook, NamesFileError
from .parser import SaveParseError, parse_save
from .sheet import build_sheet


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
    pl = d.get("player")
    L.append("\n== Player ==")
    if not pl:
        L.append("  not decoded")
    else:
        L.append(f"  {pl['name']}  level {pl['level']}  race {pl['race']}")
        L.append(f"  base health/magicka/stamina: {pl['base_health']}/{pl['base_magicka']}"
                 f"/{pl['base_stamina']}  (NPC_ base values, not current)")
        L.append("  base skills (NPC_ record): " + ", ".join(f"{k} {v}" for k, v in pl["skills"].items()))
        L.append(f"  factions: " + ", ".join(f"{f['faction']}({f['rank']})" for f in pl["factions"]))
        L.append(f"  undecoded trailing bytes (face data): {pl['undecoded_bytes']}")
    loc, gt = d.get("player_location"), d.get("game_time")
    if loc:
        L.append(f"  location: {loc['worldspace']} cell ({loc['cell_x']},{loc['cell_y']}) "
                 f"pos {', '.join(f'{x:.0f}' for x in loc['pos'])}")
    if gt:
        L.append(f"  game time: year {gt.get('GameYear'):g} month {gt.get('GameMonth'):g} day "
                 f"{gt.get('GameDay'):g} hour {gt.get('GameHour'):.2f}; days passed "
                 f"{gt.get('GameDaysPassed'):.2f}" if len(gt) >= 5 else f"  game time: {gt}")
    stats = d.get("misc_stats") or []
    L.append(f"\n== Misc stats ({len(stats)}) ==")
    cat = None
    for s in stats:
        if s["category"] != cat:
            cat = s["category"]
            L.append(f"  [{cat}]")
        L.append(f"    {s['name']}: {s['value']}")
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
    sh = sub.add_parser("sheet", help="Write a Markdown character snapshot (read-only on the save)")
    sh.add_argument("--save", required=True, help="path to .ess file")
    sh.add_argument("--out", help="write the Markdown here instead of stdout")
    sh.add_argument("--names", help="JSON file mapping '<Plugin>:<hex id>' to "
                                    "{edid, name, type}")
    args = ap.parse_args(argv)
    try:
        with open(args.save, "rb") as f:  # read-only
            data = f.read()
    except OSError as e:
        print(f"error: cannot read {args.save}: {e}", file=sys.stderr)
        return 2
    try:
        parsed = parse_save(data)
        d = parsed.to_dict() if args.cmd == "inspect" else None
    except SaveParseError as e:
        print(f"error ({type(e).__name__}): {e}", file=sys.stderr)
        return 1
    if args.cmd == "sheet":
        return _sheet(args, parsed)
    print(json.dumps(d, indent=2) if args.json else _render(d))
    return 0


def _sheet(args, parsed) -> int:
    try:
        names = NameBook.load(args.names)
    except NamesFileError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    text = build_sheet(parsed, os.path.basename(args.save), names)
    if not args.out:
        sys.stdout.write(text)
        return 0
    try:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    except OSError as e:
        print(f"error: cannot write {args.out}: {e}", file=sys.stderr)
        return 2
    return 0
