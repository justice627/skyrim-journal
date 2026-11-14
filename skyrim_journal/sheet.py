"""Character snapshot ("sheet") rendered as Markdown. Only facts decoded from the save."""
from __future__ import annotations

import os
from collections import defaultdict

from .names import NameBook, NameEntry, normalize_key
from .parser import ParsedSave
from .parser.globaldata import (KNOWN_GLOBALS, parse_global_variables, parse_misc_stats,
                                parse_player_location)
from .parser.playerstate import SKILL_NAMES, PlayerState, parse_player_state
from .parser.quests import QuestProgress, parse_quests
from .parser.refs import describe, describe_form_id

SEX = {0: "Male", 1: "Female"}
# Substring (lower-case) -> description, matched against plugin file names.
PERK_OVERHAULS = {"adamant": "Adamant", "ordinator": "Ordinator", "vokrii": "Vokrii",
                  "perkus maximus": "Perkus Maximus", "sperg": "SPERG"}
ALT_STARTS = {"skyrim unbound": "Skyrim Unbound", "live another life": "Live Another Life",
              "alternate start": "Alternate Start"}
QUEST_TYPES = {0: "None", 1: "Main Quest", 2: "Mages Guild", 3: "Thieves Guild",
               4: "Dark Brotherhood", 5: "Companions", 6: "Misc", 7: "Daedric", 8: "Side Quest",
               9: "Civil War", 10: "Dawnguard", 11: "Dragonborn"}
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


def _skill_sort_key(tree) -> tuple[int, str]:
    edid = tree.skill[2:] if tree.skill.lower().startswith("av") else tree.skill
    edid = {"Mysticism": "Illusion"}.get(edid, edid)
    return (SKILL_NAMES.index(edid) if edid in SKILL_NAMES else len(SKILL_NAMES), tree.skill_name)


def _chains(names: NameBook, tree_perks: tuple[str, ...]) -> list[list[str]]:
    """Rank chains of one skill tree: each tree perk that is not the next rank of another tree
    perk starts a chain that follows the PERK ``next`` links (guarded against cycles)."""
    def nxt(k: str) -> str | None:
        e = names.entry(k)
        return e.next if e else None

    later = {normalize_key(n) for k in tree_perks if (n := nxt(k))}
    chains = []
    for k in tree_perks:
        if normalize_key(k) in later:
            continue
        chain, seen = [k], {normalize_key(k)}
        while (n := nxt(chain[-1])) and normalize_key(n) not in seen and len(chain) < 20:
            chain.append(n)
            seen.add(normalize_key(n))
        chains.append(chain)
    return chains


def _perk_section(perks: list[tuple[int, int]], b, names: NameBook) -> list[str]:
    label = names.label
    mine: dict[tuple, tuple[str, int]] = {}      # normalized key -> (described key, saved rank)
    by_plugin: dict[str, int] = defaultdict(int)
    for fid, rank in perks:
        d = describe_form_id(fid, b.plugins, b.light_plugins) or "?"
        by_plugin[d.rsplit(":", 1)[0]] += 1
        nk = normalize_key(d)
        if nk:
            mine[nk] = (d, rank)
    out = [f"A list of {len(perks)} (form, rank) entries was decoded from the player record. "
           "Its structure matches a perk list, but it includes entries added by mods, quests and "
           "abilities as well as the perks chosen in the skill trees."]
    claimed: set[tuple] = set()
    rows = []
    if names.has_perk_trees:
        for tree in sorted(names.perk_trees(), key=_skill_sort_key):
            skill = tree.skill_name or (names.entry(tree.key).label if names.entry(tree.key)
                                         else "") or tree.skill or tree.key
            for chain in _chains(names, tree.perks):
                keys = [normalize_key(k) for k in chain]
                owned = [i for i, k in enumerate(keys, 1) if k in mine and k not in claimed]
                if not owned:
                    continue
                top = max(owned)
                rank = max(top, mine[keys[top - 1]][1] if len(chain) > 1 else 1)
                claimed.update(k for k in keys if k in mine)
                rows.append([skill, label(chain[top - 1]),
                             f"{rank} of {len(chain)}" if len(chain) > 1 else ""])
        out += [f"Perks chosen in skill trees: {len(rows)}, matched against the skill trees "
                f"({len(names.perk_trees())} trees) in the names file. A perk counts as chosen "
                "when it is in a tree, directly or as a later rank of a tree perk.", ""]
        if rows:
            out += _table(["Skill", "Perk", "Rank"], rows)
        else:
            out.append("None of the player's perks was found in the skill trees. The names file "
                       "may have been exported from a different load order than this save.")
        out.append("")
    other = [(d, r) for nk, (d, r) in mine.items() if nk not in claimed]
    plugins = ", ".join(f"{p} {n}" for p, n in sorted(by_plugin.items(), key=lambda x: -x[1]))
    if names.has_perk_trees:
        title = f"Other perks (granted by mods, quests and abilities): {len(other)}"
    else:
        out += ["The perk list cannot be split into chosen and granted perks without skill "
                "trees: a names file exported with perk trees (exporter version 1.1 or later) "
                "is needed to tell chosen perks apart. Entries per plugin: " + plugins + ".", ""]
        title = f"All perks ({len(other)})"
    out += [f"<details><summary>{title}</summary>", ""]
    out += _table(["Perk", "Rank"], [[label(d), r] for d, r in other], {1})
    out += ["", "</details>", ""]
    return out


def _quest_status(q: QuestProgress, e: NameEntry | None) -> tuple[str, str]:
    """(status, basis). Save flag bits first, then the names file's stage lists."""
    if q.completed:
        return "completed", "save flag"
    if q.failed:
        return "failed", "save flag"
    reached = set(q.reached)
    if e and e.complete_stages and reached & set(e.complete_stages):
        return "completed", "completing stage " + str(max(reached & set(e.complete_stages)))
    if e and e.fail_stages and reached & set(e.fail_stages):
        return "failed", "failing stage " + str(max(reached & set(e.fail_stages)))
    return "active", ""


def _quest_section(quests: list[QuestProgress], b, names: NameBook, stats) -> list[str]:
    label = names.label
    out: list[str] = []
    qstats = [s for s in stats if s.category_name == "Quest"]
    nonzero = [f"{s.name} {s.value}" for s in qstats if s.value]
    zero = [s.name for s in qstats if not s.value]
    out.append("Counters from the save's misc stats: " + ("; ".join(nonzero) if nonzero else "all 0")
               + (f". Zero: {', '.join(zero)}." if zero and nonzero else "."))
    out.append("")
    out.append(f"{len(quests)} quests have a stage list in the save; "
               f"{sum(1 for q in quests if q.reached_nonzero)} have a stage other than 0 flagged "
               "as reached (stage 0 is not listed).")
    out.append("")

    def has_progress(q):
        return bool(q.reached_nonzero or q.objectives or q.completed or q.failed)

    groups: dict[str, list] = {"completed": [], "active": [], "failed": [], "unknown": [],
                               "background": []}
    n_names = n_guess = 0
    for q in sorted(quests, key=lambda q: (q.form_id or 0)):
        if not has_progress(q):
            continue
        d = describe(b, q.form_id)
        e = names.entry(d) if d else None
        if e is not None and (e.quest_type is not None or e.objectives is not None):
            n_names += 1
            journal = (e.objectives or 0) > 0 or (e.quest_type or 0) != 0
            status, basis = _quest_status(q, e) if journal else ("background", "")
        else:
            n_guess += 1
            named = bool(e and e.name) or not names.user_entries
            evidence = q.completed or q.failed or q.has_displayed_objective or bool(q.objectives)
            if not (named and evidence):
                status, basis = "background", ""
            elif q.completed or q.failed:
                status, basis = _quest_status(q, e)
            elif q.has_displayed_objective:
                status, basis = "active", ""
            else:
                status, basis = "unknown", ""
        groups[status].append((q, d, e, basis))

    if n_guess == 0:
        method = ("Journal quests are those the names file gives objectives or a quest type; "
                  "status comes from the save's quest flags (completed 0x2, failed 0x40) and then "
                  "from the completing and failing stages in the names file.")
    else:
        method = ("The names file has no quest types or objectives for "
                  + ("these quests" if not n_names else f"{n_guess} of the quests")
                  + " (exported by an older version, or no names file), so journal quests are "
                    "guessed: a quest with a display name"
                  + (" (waived: no names loaded)" if not names.user_entries else "")
                  + " and, in the save, a completed or failed flag, a recorded objective or a "
                    "displayed objective. Status comes from the save's quest flag bits "
                    "(0x2 completed, 0x40 failed) and displayed objectives; a quest with "
                    "recorded objectives but none of these shows as status unknown.")
        if n_names:
            method += (f" The other {n_names} used the names file's quest types and stages.")
    out += [method, ""]

    show_type = any(e and e.quest_type is not None for _, _, e, _ in sum(groups.values(), []))

    def qrows(items, basis=False, objective=False):
        head = ["Quest"] + (["Type"] if show_type else []) + ["Highest stage", "Stages reached"]
        rows = []
        for q, d, e, bs in items:
            r = [label(d)]
            if show_type:
                r.append(QUEST_TYPES.get(e.quest_type, e.quest_type) if e and e.quest_type
                         is not None else "")
            r += [q.highest if q.highest is not None else "",
                  ", ".join(str(x) for x in q.reached_nonzero)]
            if basis:
                r.append(bs)
            if objective:
                r.append("yes" if q.has_displayed_objective else "")
            rows.append(r)
        return head + (["Basis"] if basis else []) + (["Objective displayed"] if objective else []), rows

    def table(title, items, **kw):
        out.append(f"#### {title} ({len(items)})")
        out.append("")
        if not items:
            out.extend(["None.", ""])
            return
        head, rows = qrows(items, **kw)
        right = {head.index("Highest stage")}
        out.extend(_table(head, rows, right))
        out.append("")

    table("Completed", groups["completed"], basis=True)
    done = next((s.value for s in qstats if s.name == "Quests Completed"), None)
    if done is not None:
        out += [f"The misc stat Quests Completed is {done}; {len(groups['completed'])} quests "
                "above carry a completed flag or completing stage. The two need not agree "
                "(for example, quests completed by a mod's script, or kinds of quest the "
                "counter does not include).", ""]
    table("Active", groups["active"], objective=True)
    if groups["unknown"]:
        table("Started, status unknown", groups["unknown"])
    if groups["failed"]:
        table("Failed", groups["failed"], basis=True)
    bg = groups["background"]
    out.append(f"<details><summary>Background and radiant quests ({len(bg)})</summary>")
    out.append("")
    out.append("Quests with a stage other than 0 reached that are not journal quests by the "
               "rule above (dialogue, radiant, mod plumbing).")
    out.append("")
    head, rows = qrows(bg)
    out += _table(head, rows, {head.index("Highest stage")})
    out += ["", "</details>", ""]
    return out


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
        L += ["### Perks", ""] + _perk_section(state.perks, b, names)

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
    L += ["### Quests", ""] + _quest_section(quests, b, names, stats)

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
            "Perk points available" + ("" if names.has_perk_trees else
                                        "; which perks the player chose needs a names file "
                                        "with perk trees"),
            "Objective and journal entry text of quests",
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
