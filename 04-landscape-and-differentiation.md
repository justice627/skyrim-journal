# Landscape and Differentiation

The Skyrim tooling ecosystem is segmented by purpose. This document surveys the
existing tools, assesses redundancy, and sets the build-vs-adopt plan.

## 1. Existing tools

### Save parsers, inspectors, completion trackers

- **Dragonborn's Logbook (DBL)** — MO2 plugin plus optional SKSE component;
  per-character Chronicle grouped by in-game day; character sheet, Save
  Inspector with LZ4 SE/AE support, Save Comparison, Markdown/HTML export.
  MO2/GUI-centric.
- **ReSaver Plus Plus / FallrimTools ReSaver** — full save editor; quest pages
  (running/completed/failed with stages), player editor, "Compare to another
  save." Editor/debugging focus.
- **Strange Labs 100% Completion Tracker** — web app parsing uploaded `.ess`
  files for quest completion and stages; alpha-limited to vanilla quests.
- **Winged's `skyrim-save` Agent Skill** — Python + LZ4; decompress and scan
  `.ess`, JSON output, save info/plugin list/string/FormID/hex search.
  Read-only, agent-oriented, but a **scanner**, not a structured parser.
- **Arcanaeum** — analyses saves to determine which mods were used; mod-footprint
  detection only.

### Playthrough chronicles and agentic memory

- **Codifix's "Skyrim playthrough chronicle"** — bridge daemon watches `Saves/`,
  converts each save to a checkpoint memory, a Papyrus mod traces events, the
  bridge tails the log and stores events in a memory service with citations.
  Tied to a specific memory backend; Linux/Proton-oriented; no factual/narrative
  separation.

### LLM narrative and companion frameworks

- **SkyrimNet** — multiple specialized LLMs for dialogue, memory, profiles,
  actions, combat evaluation, and diary creation from in-game events; memories
  persist as personal narrative.
- **Mantella / Mantella Living World** — per-NPC memory, bios, "what NPCs know
  about you" (fame, bounty, quest outcomes).
- **CHIM** — AI-ifies NPCs; tracks combat, quests, player stats, items,
  equipment, memories, diaries.
- **Varkos** — real-time AI companion perceiving world state.
- **SkyLink AI** — MCP server with 74 tools for reading/modifying runtime state
  via an SKSE plugin; requires the game running.

These are runtime, in-game, NPC-centric. They do not produce an offline,
chronological, factual playthrough log grounded in save diffs, and they do not
enforce factual/narrative separation.

### Adjacent general-purpose tools

- **savetracker** (Rust crate) — watches save directories, snapshots, diffs,
  optional LLM description across providers. General-purpose, no Skyrim
  semantic extraction.
- **Savecraft** — open-source MCP server parsing game saves for AI assistants;
  hosted product proprietary. No factual/narrative journal.
- **df-storyteller** (Dwarf Fortress), **The Imagine Loop** (The Sims) — LLM
  game journals in adjacent games; not Skyrim-specific.

## 2. Is the tool redundant?

**Partially, but not fatally — provided scope is sharpened.**

- The factual-log/chronicle layer overlaps heavily with **DBL**. If the goal were
  just "a readable record," a from-scratch build would be largely redundant.
- The agentic-memory layer overlaps with **Codifix**.
- The LLM narrative layer overlaps with **SkyrimNet** and **Mantella**.

No existing tool combines all of:

1. Offline, read-only save parsing with no in-game mod, SKSE plugin, MO2, or
   running game required.
2. Structured diffing between arbitrary saves as a first-class, independently
   runnable stage.
3. Strict separation between a programmatic factual log and a flagged narrative.
4. An agent-native, CLI-first pipeline with snapshot persistence and an
   append-only journal.
5. Cross-platform discovery (Windows, Linux/Proton, macOS/Wine) without assuming
   an install layout.

**Verdict:** not redundant as a category, but redundant as a generic save
chronicle. Differentiation must come from **agentic orchestration,
factual/narrative separation, and offline reproducibility**.

## 3. Build vs adopt

| Layer | Recommendation | Rationale |
|---|---|---|
| LZ4 decompression and header parsing | **Adopt / vendor** | Solved; reimplementing adds risk without differentiation. |
| Plugin list and FormID resolution | **Adopt / vendor**, cross-check with ReSaver/DBL behavior | Graceful degradation is already encoded. |
| Structured semantic extraction (typed JSON) | **Build** | No existing tool exposes this offline for agents. |
| Diff engine | **Build** | Existing comparison is debugging-oriented. |
| Factual log generation | **Build** | Must be programmatic and grounded. |
| LLM narrative layer | **Build** | In-game diaries are not offline journal narratives with inference flags. |
| Snapshot persistence and append-only journal | **Build** | File-based, portable; DBL is MO2-bound, Codifix is service-bound. |
| Agentic CLI orchestration | **Build** | Winged is a scanner; SkyLink is runtime-only. |
| Roleplay profile manifest | **Build** | Not covered by existing tools; low complexity, high differentiation. |
| Runtime enrichment | **Adopt** (SkyLink MCP adapter) | Ready-made runtime access. |

## 4. Phased plan

**Phase 1 — MVP (prove the pipeline).**
One edition (SE/AE first). Extract player basics, skills, quest stages, inventory
highlights, plugin list. Programmatic factual log, no LLM. Persist snapshots,
append to `journal.md`. Synthetic fixtures + real save if available.

**Phase 2 — Narrative and roleplay profile.**
Profile manifest; LLM narration with explicit inference flags; build-target
annotations; contradiction warnings. Harden error handling.

**Phase 3 — Agentic hardening and ecosystem.**
Per-stage CLI commands, JSON schema validation, agent contract docs. Optional
SkyLink adapter, DBL-compatible Markdown/HTML export. Open-source release with a
clear "what this is not" section (not a save editor, not an in-game mod, not a
replacement for DBL).

## 5. Bottom line

The landscape is crowded but segmented. DBL owns the GUI/MO2 chronicle; ReSaver
owns editing/debugging; Codifix owns agentic memory with a live bridge;
SkyrimNet/Mantella own runtime LLM narrative. **None owns the offline,
read-only, agent-native, factual-vs-narrative save-diff journal.** That is the
narrow but real gap.