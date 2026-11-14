# Skyrim Journal

An offline, read-only tool that turns a Skyrim Special Edition save file into a
factual character snapshot in Markdown: who the character is, how the
playthrough is set up, skills, chosen perks, inventory, and quests by status.

The longer-term plan is a parse, diff and narrate pipeline with a strictly
separated factual record and narrative. See [Status](#status) for what exists
today.

## Design principles

1. **Read-only.** Save files and plugin folders are never modified.
2. **Offline.** No running game, no SKSE plugin, no Mod Organizer integration.
3. **Factual.** Everything in the snapshot is extracted from the save or the
   plugin files. Nothing is inferred or invented; anything uncertain is labeled.
4. **Graceful degradation.** Unknown records and unresolved form ids produce
   clear messages and placeholders, not crashes.

## Requirements

- Python 3.11 or newer
- The `lz4` Python library
- Skyrim Special Edition or Anniversary Edition saves (`.ess`, save version 12)

On Debian, Ubuntu and Kubuntu, `pip install` into the system Python is blocked.
Install the one dependency from the distribution instead:

```bash
sudo apt install python3-lz4
```

On other systems, use a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

With a virtual environment, replace `python3` with `.venv/bin/python` in the
commands below.

## Usage

Run all commands from the repository root.

### Step 1: export the name table (once per mod list)

A save stores form ids, not names. This step reads your installed plugin files
and writes `names.json`, which maps form ids to item, perk, quest and location
names, perk trees, and quest objective text.

```bash
python3 -m skyrim_journal.plugins.export \
  --data "/path/to/Skyrim Special Edition/Data" \
  --data "/path/to/ModOrganizer/mods" \
  --save "/path/to/Saves/<save>.ess" \
  --out names.json 2> export.log
```

- `--data` is repeatable. Pass the game's `Data` folder, plus your mod
  manager's mods folder if it keeps plugins outside `Data` (Mod Organizer 2
  does: one subfolder per mod).
- `--save` restricts the export to the plugins that save lists, in the save's
  order. Use it, so that installed but inactive mods cannot override names or
  perk trees. `--load-order <plugins.txt>` is the alternative.
- `export.log` lists each plugin read, any that were skipped and why, and any
  plugin whose display names could not be found.

Rerun this step only when your mod list changes, or after updating this tool
when the release notes mention new name-table fields.

### Step 2: generate the snapshot (per save)

```bash
python3 -m skyrim_journal sheet \
  --save "/path/to/Saves/<save>.ess" \
  --names names.json \
  --out ~/character.md
```

Without `--out`, the snapshot is printed to the terminal. Without `--names`, it
still works but shows raw form ids such as `Skyrim.esm:01DBFC`.

To use the most recent save in a folder:

```bash
SAVES="/path/to/Saves"
python3 -m skyrim_journal sheet --save "$(ls -t "$SAVES"/*.ess | head -n 1)" \
  --names names.json --out ~/character.md
```

### Finding your saves

- **Windows:** `Documents\My Games\Skyrim Special Edition\Saves`
- **Linux (Steam Proton):**
  `<steam>/steamapps/compatdata/489830/pfx/drive_c/users/steamuser/Documents/My Games/Skyrim Special Edition/Saves`
- **Mod Organizer 2 with profile-specific saves:** `<MO2 instance>/profiles/<profile>/saves`

On Linux, this locates them wherever they are:

```bash
find ~ -name "*.ess" 2>/dev/null
```

### Inspecting a save

For debugging, `inspect` prints the save's structure: header, plugin list,
change-form counts by type, the player's records and the misc stats.

```bash
python3 -m skyrim_journal inspect --save "/path/to/Saves/<save>.ess"
```

Add `--json` for machine-readable output.

## What the snapshot contains

| Section | Contents |
|---|---|
| Who | Name, race, sex, level and XP, location, health, magicka, stamina |
| Playthrough setup | Dragons, shouts and survival mode switches from the save's global variables; detected perk overhaul and alternate start |
| Skills | Base and current level, and XP progress, for all 18 skills |
| Perks | Perks chosen in skill trees, grouped by skill; perks granted by mods collapsed |
| Factions | Player faction memberships |
| Gold and inventory | Every carried item with count and whether it is worn |
| Quests | Completed, active (with objective text), miscellaneous objectives, other started quests, background quests |
| Activity | The save's own statistics: kills, locations, crafting, crime |
| Load order | Full and light plugins |
| Not yet extracted | What the snapshot does not cover |

Not yet extracted: spells and shouts, tempering and enchantments on items,
armor rating, carry weight, and container contents.

## Tests

```bash
sudo apt install python3-pytest   # or: .venv/bin/pip install -e '.[dev]'
python3 -m pytest -q
```

Tests that need a real save or a real name table skip when `samples/*.ess` or
`names.json` is absent.

## Status

Working today: the save parser, the name-table exporter, and the `sheet` and
`inspect` commands. They have been verified against one real save (form
version 78, 76 plugins) and its plugin files. Legendary Edition saves and
other save versions are untested.

Planned, not built: diffing two saves into a change log, an append-only
journal, a user-written character profile, and an LLM narrative and advice
layer kept separate from the factual record.

## Documentation

These documents record the original research and design. They describe the
planned pipeline, and parts of them predate the implementation.

| Document | Contents |
|---|---|
| [`01-research-parsers.md`](01-research-parsers.md) | Existing parser survey, save format essentials, language choice |
| [`02-architecture.md`](02-architecture.md) | Pipeline design, stage contracts, error handling, testing |
| [`03-roleplay-and-mods.md`](03-roleplay-and-mods.md) | Roleplay profile manifest, mod incorporation, form id resolution |
| [`04-landscape-and-differentiation.md`](04-landscape-and-differentiation.md) | Existing tools, redundancy assessment, build-vs-adopt plan |
| [`05-value-strategy.md`](05-value-strategy.md) | Monetization findings, open-source strategy, career framing |
| [`06-sources.md`](06-sources.md) | Source index and verification status |

## License

Apache 2.0 (proposed; no license file has been added yet). See
`05-value-strategy.md` for the rationale.
