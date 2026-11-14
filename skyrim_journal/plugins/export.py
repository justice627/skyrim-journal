"""Export a form-id -> name table from installed Skyrim SE plugins.

Usage:
    python -m skyrim_journal.plugins.export --data "<Data dir>" \
        [--data <extra dir> ...] [--load-order plugins.txt | --save my.ess] --out names.json

``--save`` takes the load order from a save file's plugin list, so plugins that are installed
but were not active in that save (and could otherwise override names and perk trees) are left
out.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from ..parser import SaveParseError
from .reader import PluginError, scan_plugin
from .strings import DirIndex, StringsFinder

TOOL_VERSION = "1.3.0"
BASE_MASTERS = ["Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm",
                "Dragonborn.esm"]
PLUGIN_EXTS = (".esm", ".esp", ".esl")


def _is_plugin(name: str) -> bool:
    return name.lower().endswith(PLUGIN_EXTS)


def _plugins_in(d: str, idx: DirIndex) -> list[str]:
    out = []
    for low, real in sorted(idx.listing(d).items()):
        p = os.path.join(d, real)
        if _is_plugin(low) and os.path.isfile(p):
            out.append(p)
    return out


def discover(data_dirs: list[str]) -> tuple[dict[str, str], list[dict], list[str]]:
    """Return ({lower name: path}, skipped, search dirs actually containing plugins)."""
    idx = DirIndex()
    found: dict[str, str] = {}
    skipped = []
    plugin_dirs = []

    def add(paths, d):
        if paths:
            plugin_dirs.append(d)
        for p in paths:
            key = os.path.basename(p).lower()
            if key in found:
                skipped.append({"plugin": p, "reason": f"duplicate of {found[key]}"})
            else:
                found[key] = p

    for d in data_dirs:
        if not os.path.isdir(d):
            skipped.append({"plugin": d, "reason": "data directory not found"})
            continue
        direct = _plugins_in(d, idx)
        if direct:
            add(direct, d)
            continue
        for low, real in sorted(idx.listing(d).items()):
            sub = os.path.join(d, real)
            if os.path.isdir(sub):
                add(_plugins_in(sub, idx), sub)
    return found, skipped, plugin_dirs


def read_load_order(path: str) -> list[str]:
    with open(path, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    names = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        names.append(line.lstrip("*").strip())
    return names


def read_save_load_order(path: str) -> list[str]:
    """Plugin names from a save: regular plugins in order, then light plugins in order.

    This is an approximation of the true load order (light plugins are interleaved with
    regular ones in the real order, which a save does not record), good enough to decide
    which plugins were active and roughly who overrides whom.
    """
    from ..parser import parse_save
    with open(path, "rb") as f:
        parsed = parse_save(f.read())
    return list(parsed.body.plugins) + list(parsed.body.light_plugins)


def order_plugins(found: dict[str, str], load_order: list[str] | None):
    """Return (ordered keys, skipped entries for plugins left out)."""
    skipped = []
    ordered = [b.lower() for b in BASE_MASTERS if b.lower() in found]
    seen = set(ordered)
    if load_order is None:
        # .esm files before the rest (as the game loads masters first)
        rest = sorted((k for k in found if k not in seen),
                      key=lambda k: (not k.endswith(".esm"), k))
        ordered.extend(rest)
    else:
        for name in load_order:
            key = name.lower()
            if key in seen:
                continue
            if key in found:
                ordered.append(key)
                seen.add(key)
            else:
                skipped.append({"plugin": name, "reason": "listed in load order but not found"})
        for key in sorted(found):
            if key not in seen:
                skipped.append({"plugin": found[key], "reason": "not in load order"})
    return ordered, skipped


def build(data_dirs, load_order=None, language="english", log=None):
    log = log or (lambda m: None)
    found, skipped, plugin_dirs = discover(data_dirs)
    ordered, extra_skipped = order_plugins(found, load_order)
    skipped += extra_skipped
    canon = {k: os.path.basename(p) for k, p in found.items()}
    finder = StringsFinder(plugin_dirs + [d for d in data_dirs if d not in plugin_dirs], language)
    names: dict[str, dict] = {}
    perk_trees: dict[str, list[str]] = {}   # AVIF key -> perk keys, last non-empty tree wins
    light_by_plugin: dict[str, bool] = {}
    per_plugin: dict[str, dict] = {}
    no_strings: list[str] = []
    total = len(ordered)

    for n, key in enumerate(ordered, 1):
        path = found[key]
        pname = canon[key]
        try:
            scan = scan_plugin(path)
            table, source = None, None
            if scan.localized and any(
                    isinstance(r.full, int)
                    or any(isinstance(t, int) for t in r.extra.get("objective_text", {}).values())
                    for r in scan.records):
                hit = finder.find(path)
                if hit:
                    table, source = hit
                else:
                    no_strings.append(pname)
            masters = scan.masters

            def resolve(fid, masters=masters, scan=scan, pname=pname):
                idx = (fid >> 24) & 0xFF
                if idx < len(masters):
                    mkey = masters[idx].lower()
                    dname = canon.get(mkey, masters[idx])
                    dlight = light_by_plugin.get(mkey, mkey.endswith(".esl"))
                else:
                    dname, dlight = pname, scan.light
                return f"{dname}:{fid & (0xFFF if dlight else 0xFFFFFF):06X}"

            aux: dict[str, dict[int, str] | None] = {}

            def lookup_text(sid, table=table, path=path):
                """Id -> text: the STRINGS table, else the DLSTRINGS / ILSTRINGS tables."""
                if table and sid in table:
                    return table[sid]
                for kind in ("dlstrings", "ilstrings"):
                    if kind not in aux:
                        hit = finder.find(path, kind)
                        aux[kind] = hit[0] if hit else None
                    if aux[kind] and sid in aux[kind]:
                        return aux[kind][sid]
                return None

            local: dict[str, dict] = {}
            local_trees: dict[str, list[str]] = {}
            for r in scan.records:
                rkey = resolve(r.form_id)
                full = r.full
                if isinstance(full, int):
                    full = table.get(full) if table else None
                entry = {}
                if r.edid is not None:
                    entry["edid"] = r.edid
                if full:
                    entry["name"] = full
                if not entry:
                    continue
                entry["type"] = r.rtype
                ex = r.extra
                if r.rtype == "PERK":
                    for f in ("playable", "hidden"):
                        if f in ex:
                            entry[f] = ex[f]
                    if ex.get("next"):
                        entry["next"] = resolve(ex["next"])
                elif r.rtype == "QUST":
                    for f in ("quest_type", "objectives", "complete_stages", "fail_stages"):
                        if f in ex:
                            entry[f] = ex[f]
                    texts = {}
                    for idx, t in sorted(ex.get("objective_text", {}).items()):
                        t = lookup_text(t) if isinstance(t, int) else t
                        if t:
                            texts[str(idx)] = t
                    if texts:
                        entry["objective_text"] = texts
                    if ex.get("aliases"):
                        entry["aliases"] = {str(i): {"name": n, "kind": k}
                                            for i, (n, k) in sorted(ex["aliases"].items())}
                elif r.rtype == "AVIF" and ex.get("perks"):
                    local_trees[rkey] = list(dict.fromkeys(resolve(f) for f in ex["perks"]))
                local[rkey] = entry
        except (PluginError, OSError, ValueError, MemoryError) as e:
            skipped.append({"plugin": path, "reason": str(e) or type(e).__name__})
            log(f"[{n}/{total}] {pname}: SKIPPED ({e})")
            continue
        light_by_plugin[key] = scan.light
        names.update(local)
        perk_trees.update(local_trees)
        info = {"records": len(local), "light": scan.light, "localized": scan.localized}
        if scan.localized:
            info["strings"] = source or "missing"
        per_plugin[pname] = info
        log(f"[{n}/{total}] {pname}: {len(local)} records"
            + (f" (localized, strings: {info['strings']})" if scan.localized else ""))

    trees = {}
    for akey, perks in perk_trees.items():
        a = names.get(akey, {})
        trees[akey] = {"skill": a.get("edid", ""), "skill_name": a.get("name", ""),
                       "perks": perks}

    meta = {
        "tool_version": TOOL_VERSION,
        "language": language,
        "plugin_count": len(per_plugin),
        "total_names": len(names),
        "plugins": per_plugin,
        "skipped": skipped,
        "localized_plugins_without_strings": no_strings,
        "warnings": finder.warnings,
    }
    return {"_meta": meta, "_perk_trees": trees, **names}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m skyrim_journal.plugins.export",
                                 description="Export a Skyrim SE form id name table.")
    ap.add_argument("--data", action="append", required=True, help="Data directory (repeatable)")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--load-order", help="plugins.txt giving the load order")
    grp.add_argument("--save", help="save file (.ess) whose plugin list is used as the load "
                                    "order; plugins not in it are skipped")
    ap.add_argument("--language", default="english")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    def log(m):
        print(m, file=sys.stderr, flush=True)

    lo = None
    if args.load_order:
        try:
            lo = read_load_order(args.load_order)
        except OSError as e:
            log(f"cannot read load order: {e}")
            return 2
    elif args.save:
        try:
            lo = read_save_load_order(args.save)
        except (OSError, SaveParseError) as e:
            log(f"cannot read plugin list from save: {e}")
            return 2
        log(f"Load order from save: {len(lo)} plugins")
    result = build(args.data, lo, args.language, log)
    meta = result["_meta"]
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    log(f"Done: {meta['plugin_count']} plugins, {meta['total_names']} names, "
        f"{len(result['_perk_trees'])} perk trees, "
        f"{len(meta['skipped'])} skipped -> {args.out}")
    for s in meta["skipped"]:
        log(f"  skipped: {s['plugin']}: {s['reason']}")
    if meta["localized_plugins_without_strings"]:
        log("WARNING: no strings table found (names omitted, EDID only) for: "
            + ", ".join(meta["localized_plugins_without_strings"]))
    for w in meta["warnings"]:
        log(f"  warning: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
