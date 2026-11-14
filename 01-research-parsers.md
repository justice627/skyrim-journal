# Research: Existing Parsers and Save Format Essentials

This document records the parser survey, the save-format facts the project
depends on, and the language/stack decision.

## 1. Existing parser survey

| Parser | Language / Platform | Coverage | Limitations for this project |
|---|---|---|---|
| `@save-ward/save-parser-skyrim` | Node.js | Header metadata (player name, level, location, XP, game date, screenshot, plugin list) | Does not support Special Edition; no change forms, quests, inventory, skills, or perks |
| `Nadroj-Mail/Skyrim-Save-Parser` | Python | Claims SE support, outputs JSON | Early-stage; unclear depth of change-form parsing; not a modular pipeline |
| `skyrim-save` (Winged toolkit) | Python + `lz4` | Decompress, scan strings/FormIDs/hex; output JSON | Search/scan tool, not a structured parser; no semantic models |
| `skyplug-core` (Rust crate) | Rust | Header, plugin list, load-order approximation, LZ4/uncompressed saves | Header and plugin list only; no global data, change forms, or quests |
| `bethesda-structs` | Python | Plugin/archive formats | Not a save-file parser |
| `ReSaver` / `ReSaverPP` | Java / C++ | Full save inspection: change forms, quests, actors, inventories | Heavy GUI/CLI tools; not a lightweight library |
| `tesvsavedump` | Python 2.7 | Raw save dump | Ancient, Python 2, incomplete; unmaintainable |

**Conclusion.** No existing open-source parser provides the complete structured
extraction this project needs (player stats, skills, perks, quest stages, change
forms, inventory, faction/kill/location state) as a pipeline-ready artifact.
A focused parser is justified. The UESP wiki provides the authoritative format
specification.

## 2. Save format essentials

The UESP wiki is the authoritative community specification. Key points:

- **Edition detection.** The header `version` field distinguishes LE (7–9) from
  SE/AE (12). `formVersion` is 74 as of LE 1.9 and SE 1.5.97.
- **Compression.** SE saves use LZ4 block format (`compressionType = 2`) for
  everything after screenshot data. LE saves may use zlib or no compression for
  change forms. The parser must handle uncompressed, LZ4, and zlib paths.
- **Form IDs.** In change forms, FormIDs are stored as 3-byte `RefID` values:
  - upper 2 bits = source type (0 = index into the save's FormID array,
    1 = Skyrim.esm default, 2 = created / plugin index 0xFF, 3 = unknown)
  - lower 22 bits = the form ID
  Mod-added records arrive as type-0 RefIDs and require the save's plugin list
  (and light-plugin list for SE) to resolve.
- **Change forms.** `changeFormCount` records, each with a `type` byte that
  selects the sub-parser and length-field width. Subpages document REFR, ACHR,
  and QUST layouts, including inventory, quest stages, and quest run data.
- **Plugin list.** The header records the load order at save time; SE saves also
  record light plugins (ESL).
- **Global data tables.** Player-level data (skills, attributes, etc.) lives in
  global data tables 1–3, located via the `fileLocationTable` offsets and counts.
- **Load-order changes.** FormIDs are remapped in the save when plugin order
  changes; removed plugins leave placeholder records (`#0`) rather than crashing
  the game. The parser must mirror this graceful degradation.

## 3. Language and stack

**Recommendation: Python 3.11+.**

| Requirement | Python fit |
|---|---|
| Binary parsing with variable-length fields | `struct`, `int.from_bytes`; `construct` optional |
| LZ4 decompression | `lz4` package (block format supported) |
| JSON snapshots and diffs | stdlib `json`, `dataclasses` |
| CLI | `click` or `argparse` |
| Testing | `pytest` with synthetic byte fixtures |
| Agent integration | Easy to invoke from Claude Code; easy to iterate |
| Open-source shareability | No compilation step; low barrier |

Rust (`skyplug-core`) is faster and already handles header/plugin parsing, but it
does not cover change forms or quests, and binary reverse-engineering iterates
more slowly. Node.js is viable, but its existing Skyrim parser is LE-only and
binary parsing is less ergonomic. Python gives the best correctness-to-time
ratio for this scope.

**Stack:** Python 3.11+, `lz4`, `pytest`, `click`, `anthropic` (narration stage),
stdlib for the rest.

## 4. Build vs adopt at the parser level

- **Adopt or vendor:** LZ4 block decompression and header parsing. Solved by
  Winged's `skyrim-save` skill and by DBL's bundled LZ4 extension.
- **Adopt or vendor, with cross-checks:** plugin-list handling and FormID
  resolution. DBL and ReSaver already encode the graceful-degradation behavior.
- **Build:** the **typed semantic model** (player, quests, change forms as
  structured JSON) that the diff and narration stages depend on. No existing
  tool exposes this as a clean, offline artifact for agents.