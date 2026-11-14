"""Character snapshot ("sheet") rendered as Markdown. Only facts decoded from the save."""
from __future__ import annotations

import os
from collections import defaultdict

from .names import NameBook
from .parser import ParsedSave
from .parser.globaldata import (KNOWN_GLOBALS, parse_global_variables, parse_misc_stats,
                                parse_player_location)
from .parser.playerstate import SKILL_NAMES, PlayerState, parse_player_state
from .parser.quests import parse_quests
from .parser.refs import describe, describe_form_id

SEX = {0: "Male", 1: "Female"}
# Substring (lower-case) -> description, matched against plugin file names.
PERK_OVERHAULS = {"adamant": "Adamant", "ordinator": "Ordinator", "vokrii": "Vokrii",
                  "perkus maximus": "Perkus Maximus", "sperg": "SPERG"}
ALT_STARTS = {"skyrim unbound": "Skyrim Unbound", "live another life": "Live Another Life",
              "alternate start": "Alternate Start"}
CATEGORY_ORDER = ["General", "Quest", "Combat", "Magic", "Crafting", "Crime", "DLC"]
CATEGORY_TITLE = {"General": "General", "Quest": "Quest", "Combat": "Combat", "Magic": "Magic",
                  "Crafting": "Crafting", "Crime": "Crime", "DLC": "DLC"}


def _c(s: object) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def _num(v: float) -> str:
    return f"{v:g}" if abs(v - round(v)) > 1e-4 else str(int(round(v)))


def _table(head: list[str], rows: list[list[object]], align_right: set[int] = frozenset()) -> list[str]:
    out = ["| " + " | ".join(head) + " |",
           "|" + "|".join("---:" if i in align_right else "---" for i in range(len(head))) + "|"]
    out += ["| " + " | ".join(_c(x) for x in r) + " |" for r in rows]
    return out


def _detect(plugins: list[str], table: dict[str, str]) -> list[str]:
    """One entry per recognised mod, listing every matching plugin file (patches included)."""
    found: dict[str, list[str]] = {}
    for p in plugins:
        low = p.lower()
        for key, label in table.items():
            if key in low:
                found.setdefault(label, []).append(f"`{p}`")
    return [f"{label} ({', '.join(files)})" for label, files in found.items()]


def build_sheet(parsed: ParsedSave, save_file_name: str, names: NameBook | None = None) -> str:
    names = names or NameBook()
    h, b = parsed.header, parsed.body
    ctype = h.compression_type
    stats = parse_misc_stats(b)
    stat = {s.name: s.value for s in stats}
    gv = parse_global_variables(b)
    gt = {n: gv[i] for i, n in KNOWN_GLOBALS.items() if i in gv}
    loc = parse_player_location(b)
    pinfo = parsed.player_info()
    state: PlayerState | None = parse_player_state(b, ctype, h.cur_exp, h.lvlup_exp)
    quests = parse_quests(b, ctype)

    save_date = (h.filetime_iso or "")[:10] or "unknown date"
    label = names.label
    L: list[str] = []

    # --- front matter and intro -------------------------------------------------------
    L += ["---", "type: snapshot", "area: gaming", f"created: {save_date}",
          f"character: {h.player_name}", f"save: {save_file_name}", "---"]
    intro = f"Snapshot of {h.player_name} from save {h.save_number}, {save_date}."
    if len(gt) >= 5:
        intro += (f" In-game: day {gt['GameDay']:g}, month {gt['GameMonth']:g}, year "
                  f"{gt['GameYear']:g}, {int(gt['GameHour']):02d}:"
                  f"{int((gt['GameHour'] % 1) * 60):02d}; {gt['GameDaysPassed']:.2f} days into "
                  f"the playthrough.")
    L += [intro, ""]

    # --- Who --------------------------------------------------------------------------
    race_ref = pinfo["race"] if pinfo else None
    race = h.player_race or "unknown"
    if race_ref and names.lookup(race_ref):
        race = f"{names.lookup(race_ref).label}"
    rows = [["Name", h.player_name],
            ["Race / Sex", f"{race} / {SEX.get(h.player_sex, h.player_sex)}"],
            ["Level", f"{h.player_level} ({_num(h.cur_exp)} / {_num(h.lvlup_exp)} XP)"],
            ["Location", h.player_location or "unknown"]]
    if loc is not None:
        ws = describe(b, loc.worldspace)
        rows.append(["Worldspace / cell",
                     f"{label(ws)}, cell ({loc.coord_x}, {loc.coord_y})"])
    if state and state.attributes:
        rows.append(["Health / Magicka / Stamina",
                     " / ".join(_num(state.attributes[k]) for k in ("Health", "Magicka", "Stamina")
                                if k in state.attributes) + " (saved base values)"])
    L += ["### Who", ""] + _table(["", ""], rows) + [""]

    # --- Skills -----------------------------------------------------------------------
    L += ["### Skills", ""]
    base = pinfo["skills"] if pinfo else {}
    cur = state.skills if state else {}
    if cur:
        total = sum(cur[n] - base[n] for n in SKILL_NAMES if n in base)
        L.append("Base is the value in the player's NPC_ record (15 plus racial bonus). Current "
                 "is the saved actor value, which includes level-ups"
                 + (f" (total gained {_num(total)}; the save's Skill Increases counter is "
                    f"{stat['Skill Increases']})" if "Skill Increases" in stat else "")
                 + ". XP is read as xp / threshold from the player skill block (layout inferred; "
                   "the block's levels match the Current column).")
        L.append("")
        blk = state.skill_block
        rows = []
        for i, n in enumerate(SKILL_NAMES):
            row = [n, _num(base[n]) if n in base else "?", _num(cur[n])]
            row.append(f"{blk[i][1]:.0f} / {blk[i][2]:.0f}" if blk else "not decoded")
            rows.append(row)
        L += _table(["Skill", "Base", "Current", "XP"], rows, {1, 2, 3})
    else:
        L.append("Current skill levels could not be decoded from this save; the values below are "
                 "the base values from the player's NPC_ record (race bonuses only).")
        L.append("")
        L += _table(["Skill", "Base"], [[n, _num(v)] for n, v in base.items()], {1})
    L.append("")

    # --- Perks ------------------------------------------------------------------------
    if state and state.perks is not None:
        L += ["### Perks", ""]
        by_plugin: dict[str, int] = defaultdict(int)
        rows = []
        for fid, rank in state.perks:
            d = describe_form_id(fid, b.plugins, b.light_plugins) or "?"
            by_plugin[d.rsplit(":", 1)[0]] += 1
            rows.append([label(d), rank])
        L.append(f"A list of {len(rows)} (form, rank) entries was decoded from the player record. "
                 "Its structure matches a perk list, but it includes entries added by mods and "
                 "DLC, and without names it cannot be told which were chosen by the player. "
                 "Entries per plugin: "
                 + ", ".join(f"{p} {n}" for p, n in sorted(by_plugin.items(), key=lambda x: -x[1]))
                 + ".")
        L += ["", "<details><summary>Full list</summary>", ""]
        L += _table(["Perk", "Rank"], rows, {1})
        L += ["", "</details>", ""]

    # --- Factions ---------------------------------------------------------------------
    L += ["### Factions", ""]
    if pinfo and pinfo["factions"]:
        L += _table(["Faction", "Rank"], [[label(f["faction"]), f["rank"]]
                                          for f in pinfo["factions"]], {1})
        L.append("")
        L.append("Faction membership is read from the player's NPC_ record.")
    else:
        L.append("Not decoded.")
    L.append("")

    # --- Gold and inventory -----------------------------------------------------------
    L += ["### Gold and inventory", ""]
    inv = state.inventory if state else None
    if inv is None:
        L += ["Inventory could not be decoded from this save.", ""]
    else:
        gold, picks = state.gold(), state.lockpicks()
        rows = [["Gold", gold if gold is not None else "none"],
                ["Lockpicks", picks if picks is not None else "none"]]
        if "Most Gold Carried" in stat:
            rows.append(["Most gold carried (stat)", stat["Most Gold Carried"]])
        L += _table(["", ""], rows) + [""]
        if state.inventory_is_partial:
            L += ["Only gold and lockpicks were recovered; the rest of the inventory could not be "
                  "walked reliably in this save.", ""]
        else:
            L += [f"Full inventory: {len(inv)} entries, {sum(i.count for i in inv)} items in total. "
                  "Worn is set for entries that carry extra-data flag 0x16, inferred to mean "
                  "worn.", ""]
            rows = []
            for it in inv:
                d = describe_form_id(it.form_id, b.plugins, b.light_plugins)
                rows.append([label(d), it.count, "yes" if it.worn else ""])
            L += ["<details><summary>Inventory</summary>", ""]
            L += _table(["Item", "Count", "Worn"], rows, {1})
            L += ["", "</details>", ""]

    # --- Quests -----------------------------------------------------------------------
    L += ["### Quests", ""]
    qstats = [s for s in stats if s.category_name == "Quest"]
    nonzero = [f"{s.name} {s.value}" for s in qstats if s.value]
    zero = [s.name for s in qstats if not s.value]
    L.append("Counters from the save's misc stats: " + ("; ".join(nonzero) if nonzero else "all 0")
             + (f". Zero: {', '.join(zero)}." if zero and nonzero else "."))
    progressed = [q for q in quests if q.reached_nonzero]
    L.append("")
    L.append(f"{len(quests)} quests have a stage list in the save; {len(progressed)} have a stage "
             "other than 0 flagged as reached (stage 0 is not listed). The save records stage "
             "progress only: this table does not say whether a quest is active, completed or "
             "ambient.")
    L.append("")
    rows = []
    for q in sorted(progressed, key=lambda q: (q.form_id or 0)):
        d = describe(b, q.form_id)
        rows.append([label(d), q.highest, ", ".join(str(s) for s in q.reached_nonzero)])
    L += _table(["Quest", "Highest stage", "Stages reached"], rows, {1})
    L.append("")

    # --- Activity ---------------------------------------------------------------------
    L += ["### Activity", ""]
    by_cat: dict[str, list[str]] = defaultdict(list)
    for s in stats:
        if s.value and not s.name.startswith("Favorite"):
            by_cat[s.category_name].append(f"{s.name} {s.value}")
    rows = [[CATEGORY_TITLE.get(c, c), "; ".join(by_cat[c])]
            for c in CATEGORY_ORDER + sorted(set(by_cat) - set(CATEGORY_ORDER)) if by_cat.get(c)]
    L += _table(["Category", "Non-zero stats"], rows)
    L += ["", "Stats with value 0 and the Favorite-* stats (ids, not counts) are left out.", ""]

    # --- Load order -------------------------------------------------------------------
    L += ["### Load order", ""]
    allp = b.plugins + b.light_plugins
    po, alt = _detect(allp, PERK_OVERHAULS), _detect(allp, ALT_STARTS)
    L.append("Perk overhaul detected from plugin names: " + (", ".join(po) if po else "none") + ".")
    L.append("Alternate start detected from plugin names: " + (", ".join(alt) if alt else "none") + ".")
    L += ["", f"{len(b.plugins)} full plugins and {len(b.light_plugins)} light plugins "
              f"({len(allp)} total).", "",
          "<details><summary>Full list</summary>", ""]
    L += [f"- [{i:02X}] {p}" for i, p in enumerate(b.plugins)]
    L += [f"- [FE:{i:03X}] {p}" for i, p in enumerate(b.light_plugins)]
    L += ["", "</details>", ""]

    # --- Not yet extracted ------------------------------------------------------------
    L += ["### Not yet extracted", ""]
    todo = ["Item, quest, perk and faction names: the save stores form ids only, so names appear "
            "only for ids listed in a `--names` file or the few built-in ids"
            + (f" ({names.user_entries} user entries loaded)" if names.user_entries else ""),
            "Which perks the player chose, and perk points available",
            "Quest status (active, completed, failed), objectives and journal entries",
            "Spells, shouts and dragon souls known; magic favorites",
            "Equipment slots, enchantments, tempering and weights of items",
            "Followers, houses, horses and map discovery",
            "State kept by mods (for example alternate-start backgrounds or perk-overhaul "
            "progress)"]
    if not (state and state.skills):
        todo.insert(1, "Current skill levels")
    L += [f"- {t}" for t in todo]
    return "\n".join(L) + "\n"


def default_save_name(path: str) -> str:
    return os.path.basename(path)
