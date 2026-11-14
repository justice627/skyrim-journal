# Architecture: Parse → Diff → Narrate

The pipeline is split into three independently runnable stages. Each stage reads
and writes JSON files in a project data directory, so every stage can be
re-run, inspected, and retried in isolation.

## 1. Directory layout

```
skyrim-journal/
├── skyrim_journal/
│   ├── discovery.py       # locate saves, detect edition
│   ├── parser/
│   │   ├── header.py      # magic, version, player basics, plugin list
│   │   ├── compression.py # zlib / LZ4 dispatch
│   │   ├── global_data.py # skills, attributes, faction, etc.
│   │   ├── change_forms.py# REFR, ACHR, QUST, NPC_
│   │   └── resolve.py     # RefID → FormID → plugin / placeholder
│   ├── diff.py
│   ├── narrate.py
│   ├── journal.py         # append-only journal persistence
│   └── cli.py             # parse / diff / narrate / run
├── tests/
│   ├── fixtures/
│   ├── test_parser.py
│   └── test_diff.py
├── data/                  # git-ignored runtime data
│   ├── snapshots/         # one JSON per parse run
│   ├── diffs/             # one JSON per diff run
│   └── journal.md         # accumulated human-readable journal
└── README.md
```

## 2. Environment discovery

Do not assume Windows, Steam, or a fixed install path. Candidate locations:

- **Windows:** `Documents\My Games\Skyrim Special Edition\Saves` (SE/AE),
  `Documents\My Games\Skyrim\Saves` (LE).
- **Linux (Proton):** `~/.steam/steam/steamapps/compatdata/489830/pfx/drive_c/users/steamuser/Documents/My Games/Skyrim Special Edition/Saves`
  (AppID 489830 for SE); also `~/.local/share/Steam/...`.
- **macOS (CrossOver/Wine):** `~/Library/Application Support/CrossOver/Bottles/<bottle>/drive_c/users/<user>/Documents/My Games/...`.

Discovery procedure:

1. Scan candidate directories for `.ess` files.
2. Read the first bytes of each candidate to confirm `TESV_SAVEGAME` magic and
   detect the version (LE vs SE).
3. Match `.skse` co-save files by base name; record presence and size.
4. If no directory is found, fail with a clear message and require
   `--save-dir /path/to/Saves`.
5. **Never write to the save directory.** All output goes to `--data-dir`.

## 3. Stage 1 — Parse

**Input:** `.ess` path; optional `.skse` path.
**Output:** `data/snapshots/<timestamp>_<save_stem>.json`.

Sequence:

1. **Header validation:** check magic, read `headerSize`, `version`,
   `formVersion`, player name/level/location/race/sex/XP, game date, screenshot
   dims, compression type.
2. **Edition dispatch:** version 7–9 → LE path (zlib or uncompressed change
   forms); version 12 → SE/AE path (LZ4 block after screenshot).
3. **Plugin list:** parse `pluginCount` and names; parse light plugins for SE.
4. **File location table:** read offsets/counts for global data tables, change
   forms, FormID array, visited worldspaces.
5. **Global data tables:** extract player-level data — skills, attributes,
   faction membership, kills, discovered locations, game time, playtime.
6. **Change forms:** for each record, read `formID`, `changeFlags`, `type`,
   `version`, lengths; dispatch:
   - **ACHR (type 1):** player/NPC instances → inventory, equipped gear, spells,
     shouts, perks, skill modifiers, life state (death), position.
   - **QUST (type 8):** quest flags, stages (`sint16 stage` + status byte),
     objectives, run data; derive active/completed from stage status and flags.
   - **REFR (type 0):** world objects → ownership changes, moved objects,
     created/deleted objects.
   - **NPC_ (type 9):** base-record changes for death detection.
7. **FormID resolution:** for each RefID:
   - upper bits = 1 → `Skyrim.esm`; resolve against a bundled map of common
     vanilla FormIDs, or emit `Skyrim.esm:0xXXXXXX`.
   - upper bits = 0 → index into the save's FormID array; resolve via plugin list.
   - upper bits = 2 → created record (`plugin 0xFF`).
   - plugin not present → `Unknown [FormID: 0xXXXXXX, plugin index N]`; continue.
8. **Snapshot assembly:** merge player data, quest state, change-form summaries,
   discovered locations, faction/kill counts, game time, plugin list, and save
   metadata into one JSON object.

### Error handling

| Condition | Behavior |
|---|---|
| Magic mismatch / truncated header | Clear message: "Not a valid Skyrim save (magic mismatch)." |
| Unsupported `version` | "Save version X is not supported. Please report this file." |
| Zero-byte or very recent file (in-progress) | Warn; require `--force` to proceed; never modify the save. |
| LZ4 / zlib decompression failure | "Compressed section could not be decompressed; file may be corrupt or use an unsupported mode." Report compression type and offset. |
| Unresolved FormID | Log warning; emit structured placeholder; continue. |

### Snapshot schema sketch

```json
{
  "meta": {
    "save_path": "...",
    "save_mtime": "...",
    "version": 12,
    "form_version": 74,
    "compression": "lz4",
    "plugin_list": ["Skyrim.esm", "..."],
    "light_plugin_list": ["..."],
    "skse_cosave": {"present": true, "size": 123456}
  },
  "player": {
    "name": "...", "race": "...", "sex": "...", "level": 24,
    "location": "...", "game_date": "...", "playtime_seconds": 0,
    "attributes": {"health": 0, "magicka": 0, "stamina": 0},
    "skills": {"destruction": 68, "...": 0},
    "perks": [{"form_id": "...", "resolved": "...", "plugin": "..."}],
    "spells": [],
    "shouts": [],
    "equipped": [],
    "inventory_highlights": [],
    "gold": 4120,
    "factions": [],
    "kills": 0,
    "discovered_locations": []
  },
  "quests": [
    {"form_id": "...", "resolved": "...", "plugin": "...",
     "state": "active|completed", "stages": [{"stage": 10, "status": "done"}]}
  ],
  "change_forms": {
    "refr": [], "achr": [], "qust": [], "npc_": []
  },
  "unresolved_form_ids": [
    {"ref_id": "0x...", "plugin_index": 5, "plugin": "MissingMod.esp"}
  ]
}
```

## 4. Stage 2 — Diff

**Input:** current snapshot + previous snapshot (or none).
**Output:** `data/diffs/<timestamp>_diff.json`.

Diff categories:

- **Player:** level gained, XP delta, attribute/skill increases, new perks,
  new spells/shouts, equipment changes, inventory added/removed, gold delta.
- **Quests:** started (new active), completed (stage status or flags changed),
  stage progress per quest.
- **World:** new locations discovered, NPC deaths (ACHR life-state changes),
  created/deleted world objects, ownership changes.
- **Meta:** playtime and game-date delta, plugin-list changes (mod added/removed).

Rules:

- Strict field comparison only; no inference.
- If a field is absent in one snapshot, emit `"unknown_change"` rather than guess.
- Every change entry carries **provenance**: which save field, which FormID,
  which plugin index.

Change entry sketch:

```json
{"category": "quest", "type": "completed",
 "quest": "Dragon Rising", "form_id": "0x...", "plugin": "Skyrim.esm",
 "stages": [10, 20, 30, 40, 50]}
```

First-run behavior: no previous snapshot → emit a full snapshot summary under a
`first_run` key, not an error.

## 5. Stage 3 — Narrate

**Input:** current snapshot + diff JSON; optional roleplay profile (see
`docs/03-roleplay-and-mods.md`).
**Output:** an appended entry in `data/journal.md` (Markdown) with two clearly
separated sections.

### Factual log (programmatic)

Generated **only** from the diff, never by the LLM. Example:

```
**Factual Log — 2026-11-11 14:32**
- Level: 24 → 25
- Skill increased: Destruction 68 → 69
- Quest started: The Way of the Voice
- Quest completed: Dragon Rising (stages 10,20,30,40,50 done)
- Location discovered: High Hrothgar
- Gold: 4,120 → 4,850
- Inventory added: Ebony Bow, Grand Soul Gem (Grand)
- NPC death: Bandit Chief (FormID 0xFF0012A3, plugin index 2)
```

Unresolved FormIDs appear as placeholders in the factual log. They are never
replaced with invented names.

### Narrative (LLM)

Generated with the factual log + snapshot + profile as context. Any sentence
that goes beyond extracted data is **explicitly flagged** (e.g., wrapped in an
`> *Interpretation:*` block or prefixed with a marker). The narrative may say
"a fallen foe" for an unresolved FormID; it must not invent a specific name.

### Journal persistence

- Append-only. Each run appends a timestamped entry with save-file metadata.
- The tool never overwrites prior entries.
- A later run diffs against the most recent snapshot and appends a new entry.

## 6. CLI contract

```
skyrim-journal run     --save-dir <path> [--data-dir <path>] [--profile <path>]
skyrim-journal parse   --save <path> --out <dir>
skyrim-journal diff    --current <path> --previous <path> --out <dir>
skyrim-journal narrate --snapshot <path> --diff <path> [--profile <path>] --out <path>
skyrim-journal discover
```

All commands exit non-zero with a typed message on error. `--force` is required
for in-progress or very recent saves.

## 7. Testing strategy

**Parser:**
- Synthetic LE fixture (version 9, uncompressed change forms, one player ACHR,
  one QUST).
- Synthetic SE fixture (version 12, LZ4-compressed body via
  `lz4.block.compress`, one player ACHR, one QUST).
- Real-save fixture if the user has one: assert non-empty player data and at
  least one quest; skip with a clear message otherwise.
- Error fixtures: truncated header, invalid magic, unsupported version, corrupt
  LZ4 → typed error, no crash.

**Diff:**
- Mutate a base snapshot (level up, quest completed, item added, location
  discovered) and assert exact change entries.
- Assert first-run diff returns a summary, not an error.

## 8. Open questions

- Which SE change-form subtypes are required for a useful first release?
- How much of the `.skse` co-save should be scanned in v1 (presence only, or
  signature list)?
- Should narration be pluggable across LLM providers, or Anthropic-only in v1?