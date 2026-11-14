# Sources

This document records the sources behind each project document. It separates
**externally verified claims** from **design decisions** and flags
**time-sensitive figures** and **partially verified tool capabilities**.

## 1. Conventions

- **Access date:** 2026-11-11 unless otherwise noted.
- **Verification legend:**
  - ✅ — Directly supported by the cited source.
  - ◐ — Partially supported; the source confirms the general capability but not
    every detail stated in the document.
  - ○ — Design decision or synthesis; not externally sourced.
- **Citation style:** `【source_id†Lstart-Lend】` refers to the source index below.
- **Time-sensitive figures** (Patreon earnings, member counts) are snapshots and
  will drift. Re-check before publishing.

## 2. Source index

| ID | Source | URL | Type | Used in |
|---|---|---|---|---|
| S1 | UESP — Skyrim Mod:Save File Format (main) | http://ftp.uesp.net/wiki/Skyrim_Mod:Save_File_Format | Wiki specification | 01, 02, 03, 04 |
| S2 | UESP — Skyrim Mod:Save File Format (mirror) | https://content3.uesp.net/wiki/Skyrim_Mod:Save_File_Format | Wiki mirror | 01 |
| S3 | UESP — Save File Format revision / compression notes | https://en.uesp.net/wiki/Skyrim_Mod:Save_File_Format | Wiki revision | 01, 02 |
| S4 | UESP — Save File Format (mobile / version fields) | https://en.m.uesp.net/wiki/Skyrim_Mod:Save_File_Format | Wiki | 01, 02 |
| S5 | UESP — QUST Changeform | https://content2.uesp.net/wiki/Skyrim_Mod:Save_File_Format/QUST_Changeform | Wiki | 01, 03 |
| S6 | UESP — Verified Creator Program | https://ftp.uesp.net/wiki/Skyrim_Mod:Verified_Creator_Program | Wiki | 05 |
| S7 | Nexus Mods — Donation Options & Guidelines | https://help.nexusmods.com/ (article: Donation Options & Guidelines) | Platform policy | 05 |
| S8 | Nexus Mods — Donation Points FAQ | https://help.nexusmods.com/ (article: Donation Points FAQ) | Platform policy | 05 |
| S9 | Wabbajack — Monetization Policy | https://wiki.wabbajack.org/ (Monetization Policy) | Platform policy | 05 |
| S10 | GitHub Blog — $100 million for open source | https://github.blog/ ($100 million for open source) | Announcement | 05 |
| S11 | Konvoy — How Developer Tools Startups Monetize Open Source | https://www.konvoy.vc/ (open-source monetization) | Industry analysis | 05 |
| S12 | Dragonborn's Logbook — Nexus Mods | https://www.nexusmods.com/ (Dragonborn's Logbook for Mod Organizer 2) | Tool page | 04, README |
| S13 | ReSaver / FallrimTools — GitHub fork | https://github.com/AI-Underdog/FallrimTools-Re-Saver | Tool repository | 01, 02, 04 |
| S14 | Winged — `skyrim-save` Agent Skill | https://github.com/WingedGuardian/skyrimvr-claude-toolkit/tree/master/.claude/skills/skyrim-save | Tool repository | 01, 02, 04 |
| S15 | SkyrimNet — Patreon page | https://www.patreon.com/SkyrimNet | Creator page | 05 |
| S16 | SkyrimNet — Graphtreon statistics | https://graphtreon.com/creator/SkyrimNet | Earnings tracker | 05 |
| S17 | SkyrimNet — GitHub / Nexus pages | https://github.com/MinLL/SkyrimNet-GamePlugin | Tool repository | 04, 05 |
| S18 | Mantella — GitHub | https://github.com/art-from-the-machine/Mantella | Tool repository | 04 |
| S19 | CHIM — Nexus Mods | https://www.nexusmods.com/skyrimspecialedition/ (CHIM) | Tool page | 04 |
| S20 | SkyLink AI — Nexus Mods | https://www.nexusmods.com/skyrimspecialedition/ (SkyLink AI) | Tool page | 04 |
| S21 | savetracker — lib.rs | https://lib.rs/crates/savetracker-core | Tool registry | 04 |
| S22 | Savecraft — GitHub | https://github.com/joshsymonds/savecraft.gg | Tool repository | 04, 05 |
| S23 | Codifix — Skyrim playthrough chronicle | https://codifix.dev/ (Skyrim playthrough chronicle) | Tool recipe | 04 |
| S24 | Strange Labs — 100% Completion Tracker | https://www.strangelabs.io/ (Skyrim tracker) | Web tool | 04 |
| S25 | Arcanaeum — GitHub | https://github.com/divanvisagie/arcanaeum | Tool repository | 04 |
| S26 | Skyrim Unbound Reborn — Nexus Mods | https://www.nexusmods.com/skyrimspecialedition/ (Skyrim Unbound Reborn) | Mod page | 03 |
| S27 | UESP — Alternate Start: Live Another Life | https://content1.uesp.net/wiki/Skyrim_Mod:Alternate_Start_-_Live_Another_Life | Wiki | 03 |
| S28 | LorerimPlanner4 — GitHub | https://github.com/Allanss0n/LorerimPlanner4 | Build planner | 03 |
| S29 | Skyrim Builds — perk calculator | https://skyrimbuilds.com | Build planner | 03 |
| S30 | df-storyteller — PyPI | https://pypi.org/project/df-storyteller/ | Tool package | 04 |
| S31 | The Imagine Loop — GitHub | https://github.com/SimHacker/MicropolisCore/ (the-imagine-loop.md) | Tool design doc | 04 |
| S32 | SkyUI source-code release — Yahoo Tech | https://tech.yahoo.com/ (SkyUI returns after 9 years) | News article | 05 |
| S33 | AI portfolio / hiring signals — The AI Runtime | https://theairuntime.com/ (AIfolio) | Industry article | README, 02, 05 |
| S34 | Proton save path — GitHub issue / PCGamingWiki | https://www.pcgamingwiki.com/ (Skyrim SE save location) | Community docs | 02 |
| S35 | Steam AppID 489830 — SteamDB | https://steamdb.info/app/489830/ | App database | 02 |
| S36 | `@save-ward/save-parser-skyrim` — npm | https://www.npmjs.com/package/@save-ward/save-parser-skyrim | Parser package | 01 |
| S37 | `skyplug-core` — crates.io | https://crates.io/crates/skyplug-core | Parser crate | 01 |
| S38 | `bethesda-structs` — ReadTheDocs | https://bethesda-structs.readthedocs.io/ | Parser library | 01 |
| S39 | `tesvsavedump` — GitHub | https://github.com/OpenNingia/tesvsavedump | Parser script | 01 |
| S40 | SKSE Serialization — GitHub | https://github.com/ (SKSE Serialization docs) | API documentation | 03 |
| S41 | `bethkit` — PyPI | https://pypi.org/project/bethkit/ | Plugin library | 03 |
| S42 | `sse-plugin-interface` — GitHub | https://github.com/Cutleast/sse-plugin-interface | Plugin library | 03 |
| S43 | `esplugin` — GitHub | https://github.com/Ortham/esplugin | Plugin library | 03 |
| S44 | Nadroj-Mail/Skyrim-Save-Parser — GitHub | https://github.com/Nadroj-Mail/Skyrim-Save-Parser | Parser script | 01 |

> **Note on URLs:** Some platform articles (Nexus help pages, Wabbajack wiki,
> Nexus mod pages) use slugs that change or are not exposed in search snippets.
> The table gives the stable domain and article title; resolve the exact slug
> before publication. Wiki pages are cited by their canonical UESP paths.

---

## 3. Per-document source maps

### 3.1 `README.md`

| Claim / section | Source(s) | Verification | Notes |
|---|---|---|---|
| Parse `.ess` for LE and SE/AE | S1, S4 | ✅ | UESP documents magic, `version` 7–9 (LE) / 12 (SE), `formVersion` 74. |
| Read-only; never write to save directory | — | ○ | Design constraint. |
| No running game, SKSE plugin, or MO2 required | S12, S20, S23 | ✅ | DBL is MO2-centric; SkyLink requires a running game; Codifix uses a bridge and memory service. |
| Agent-native CLI with re-runnable stages | S33 | ◐ | Hiring guidance supports agentic pipelines with tool use and state management; the specific CLI contract is design. |
| Factual/narrative separation | S33 | ◐ | Grounding and evaluation are cited hiring signals; the separation mechanism is design. |
| Graceful degradation for unresolved FormIDs | S1, S13 | ✅ | UESP defines RefID types; ReSaver handles save analysis/repair. |
| Apache 2.0 license | S22 | ✅ | Savecraft's local client is Apache 2.0. |

### 3.2 `docs/01-research-parsers.md`

#### Parser survey rows

| Parser | Source | Verification | Notes |
|---|---|---|---|
| `@save-ward/save-parser-skyrim` | S36 | ✅ | npm listing describes it as a metadata parser for SaveWard. |
| `Nadroj-Mail/Skyrim-Save-Parser` | S44 | ◐ | Repository claims SE support and JSON output; depth of change-form parsing not verified. |
| `skyrim-save` (Winged) | S14 | ✅ | Decompresses and scans `.ess`; requires Python + `lz4`; outputs JSON. |
| `skyplug-core` | S37 | ✅ | Parses SE install, `Plugins.txt`, and `.ess` saves. |
| `bethesda-structs` | S38 | ✅ | Parses Bethesda plugin/archive formats; not a save parser. |
| `ReSaver` / `ReSaverPP` | S13 | ✅ | Save management, analysis, repair; C++ port exists. |
| `tesvsavedump` | S39 | ✅ | Python 2.7 save dump. |

#### Format facts

| Claim | Source(s) | Verification | Notes |
|---|---|---|---|
| Save magic is `TESV_SAVEGAME` | S1 | ✅ | [reference:0] |
| `formVersion` is 74 as of LE 1.9 / SE 1.5.97 | S1, S4 | ✅ | [reference:1] |
| Save `version` 7–9 for LE, 12 for SE | S1, S4 | ✅ |  |
| SE uses LZ4 block compression by default | S3 | ✅ | `compressionType` 2 = LZ4 block; INI `uiCompression` can be 0/1/2 [reference:5] |
| RefID is 3 bytes; upper 2 bits = type, lower 22 = form ID | S1 | ✅ | [reference:7] |
| Type 0 = save FormID array, 1 = Skyrim.esm, 2 = created | S1 | ✅ | [reference:8] |
| QUST flags include `CHANGE_QUEST_STAGES` (0x80000000), `CHANGE_QUEST_OBJECTIVES` (0x20000000), `CHANGE_QUEST_SCRIPT` (0x40000000) | S5 | ✅ | [reference:9] |
| Plugin list and light plugins are in the header | S1 | ✅ | [reference:10] |
| Global data tables and `fileLocationTable` locate player data | S1 | ✅ | [reference:11] |
| Removed plugins leave placeholder records | S1, S13 | ◐ | UESP defines plugin list and FormID types; ReSaver handles save repair/placeholders. Exact `#0` behavior is implementation detail. |

#### Language and build-vs-adopt

| Claim | Source(s) | Verification | Notes |
|---|---|---|---|
| Python + `lz4` is a viable stack for `.ess` scanning | S14 | ✅ | Winged's skill requires Python with `lz4`. |
| Rust (`skyplug-core`) covers header/plugin parsing but not full change forms | S37 | ✅ | Scope from crate description. |
| Vendor LZ4/header primitives rather than reimplement | S14, S12 | ✅ | Existing tools solve decompression and header reading. |
| Build typed semantic model | — | ○ | No existing offline, agent-ready artifact. |

### 3.3 `docs/02-architecture.md`

| Claim / section | Source(s) | Verification | Notes |
|---|---|---|---|
| Windows save path (`Documents\My Games\Skyrim Special Edition\Saves`) | S34 | ✅ | PCGamingWiki lists the Steam path. |
| Linux/Proton path with `compatdata/489830` | S34, S35 | ✅ | AppID 489830 is Skyrim SE; `compatdata/489830/pfx/...` is the Proton prefix [reference:12][reference:13]. |
| macOS CrossOver/Wine path | — | ○ | Platform convention; not independently verified in this review. |
| `.skse` co-save matching by base name | S40 | ◐ | SKSE serialization writes to co-save; base-name matching is design. |
| Header validation (magic, version, formVersion) | S1, S4 | ✅ | [reference:14] |
| Edition dispatch (LE zlib/uncompressed; SE LZ4) | S1, S3 | ✅ |  |
| Plugin list / light plugin list parsing | S1 | ✅ | [reference:16] |
| File location table and global data tables | S1 | ✅ | [reference:17] |
| Change-form dispatch for ACHR/QUST/REFR/NPC_ | S1, S5 | ✅ | UESP documents change forms and QUST flags. |
| FormID resolution (type 0/1/2, plugin index, placeholder) | S1 | ✅ | [reference:18] |
| Error handling for corrupt/unsupported/in-progress saves | S1, S3 | ◐ | UESP documents version/compression; specific messages and `--force` policy are design. |
| Snapshot schema | — | ○ | Design. |
| Diff rules and provenance | — | ○ | Design. |
| Factual/narrative separation | S33 | ◐ | Grounding is a cited hiring signal; the mechanism is design. |
| Append-only journal | — | ○ | Design. |
| CLI contract | — | ○ | Design. |
| Testing strategy | — | ○ | Design. |

### 3.4 `docs/03-roleplay-and-mods.md`

| Claim / section | Source(s) | Verification | Notes |
|---|---|---|---|
| Save contains actual state, not intended backstory/build | S12, S28, S29 | ✅ | DBL records character history; build planners represent builds as external plans. |
| Build planners use skill trees, perks, racial/deity modifiers | S28, S29 | ✅ | LorerimPlanner4 includes skill trees, perks, racial bonuses, deities, birthsigns; Skyrim Builds supports vanilla and Ordinator calculators. |
| Roleplay profile manifest | — | ○ | Design. |
| Contradiction warnings (grounded) | — | ○ | Design; uses extracted data + declared targets. |
| Skyrim Unbound Reborn supports non-Dragonborn, no main quest/shouts | S26 | ✅ | [reference:19] |
| Alternate Start bypasses Helgen | S27 | ✅ | [reference:20] |
| RefID/FormID resolution through plugin list | S1 | ✅ | [reference:21][reference:22] |
| Mod QUST records parse like vanilla QUST | S5 | ✅ | [reference:23] |
| Perk overhaul detection via plugin list (e.g., Ordinator) | S29 | ◐ | Skyrim Builds supports Ordinator; exact plugin-name detection is design. |
| SKSE co-save uses 4-character signatures | S40 | ✅ | Serialization interface uses unique 4-character IDs [reference:24]. |
| Plugin enrichment via `bethkit`, `sse-plugin-interface`, `esplugin` | S41, S42, S43 | ✅ | All three read `.esp/.esm/.esl`. |
| Plugin-list changes as factual events | S1, S13 | ◐ | UESP records plugin list; save editors handle load-order changes. |

### 3.5 `docs/04-landscape-and-differentiation.md`

| Tool / claim | Source(s) | Verification | Notes |
|---|---|---|---|
| Dragonborn's Logbook: MO2 plugin, Chronicle, character sheet | S12 | ✅ | [reference:25] |
| DBL Save Inspector with LZ4 SE/AE and Save Comparison | S12 | ◐ | Chronicle/character sheet confirmed; LZ4 and comparison details not in snippet. |
| ReSaver: save management, analysis, repair | S13 | ✅ | [reference:26] |
| ReSaver quest pages and "Compare to another save" | S13 | ◐ | General analysis/repair confirmed; quest/compare specifics not in snippet. |
| Strange Labs: parses `.ess` for quest progress/stages | S24 | ✅ | [reference:27] |
| Strange Labs alpha-limited to vanilla quests | — | ◐ | Not confirmed in retrieved snippet. |
| Winged: scanner, not structured parser | S14 | ✅ | [reference:28] |
| Arcanaeum: determines mods used in a save | S25 | ✅ | [reference:29] |
| Codifix: bridge watches saves, checkpoint memory, citations | S23 | ✅ | [reference:30] |
| Codifix: Papyrus mod polls every 10 seconds | S23 | ◐ | Not confirmed in retrieved snippet. |
| SkyrimNet: LLM NPCs, memory, voice, diary creation | S17, S15 | ◐ | Memory/voice/will confirmed; diary creation not independently verified. |
| SkyrimNet: ~1,649 Patreon members, ~$845/month | S15, S16 | ✅ | Patreon: 1,655 members, $854/month, 136 paid; Graphtreon: 124 paid, $773/month, 1,608 total. See §4. |
| Mantella: NPC memory, awareness, actions | S18 | ✅ | [reference:31] |
| CHIM: AI NPC framework, quests, memories, diaries | S19 | ◐ | AI framework confirmed; diary/quest tracking specifics not in snippet. |
| SkyLink AI: MCP server, 74 tools, SKSE plugin | S20 | ✅ | [reference:32] |
| savetracker: watches saves, snapshots, diffs, LLM description | S21 | ✅ | [reference:33] |
| Savecraft: open-source MCP server, Apache 2.0 local client | S22 | ✅ | [reference:34] |
| Savecraft: hosted product proprietary | S22 | ◐ | Open local client and Apache 2.0 confirmed; proprietary hosted layer inferred from development note. |
| df-storyteller: LLM narratives grounded in gameplay | S30 | ✅ | [reference:35] |
| The Imagine Loop: LLM narrative companion for Sims | S31 | ✅ | [reference:36] |
| Redundancy conclusion (no tool combines offline + diff + factual/narrative + agent CLI) | S12–S23 | ○ | Synthesis of the above; not a single-source claim. |
| Build-vs-adopt table | S14, S12, S13, S20, S22, S23 | ✅/◐ | Individual rows as above. |
| Phased plan | — | ○ | Design. |

### 3.6 `docs/05-value-strategy.md`

| Claim / section | Source(s) | Verification | Notes |
|---|---|---|---|
| Nexus: paid modding conflicts with mission; cannot charge for files/updates/support | S7 | ✅ | [reference:37] |
| Nexus Donation Points: 1,000 DP = $1 | S8 | ✅ | [reference:38] |
| Wabbajack: no paywalled modlists, no paywalled support, donations allowed | S9 | ✅ | [reference:39] |
| Bethesda Verified Creator Program pays royalties for Creations | S6 | ✅ | [reference:40] |
| SkyrimNet Patreon figures | S15, S16 | ✅ | Time-sensitive; see §4. |
| Open-core: free core, paid team/enterprise features | S11 | ✅ | [reference:41] |
| Savecraft: local client Apache 2.0, hosted product separate | S22 | ✅/◐ | Apache 2.0 confirmed; hosted proprietary inferred. |
| GitHub Sponsors has moved >$100M to maintainers | S10 | ✅ | [reference:42] |
| SkyUI returned after 9 years with full source release | S32 | ✅ | [reference:43] |
| Agentic hiring signals: tool/MCP integration, memory, evaluation, state management | S33 | ✅ | [reference:44] |
| Career framing ("agentic data pipeline for undocumented binary format") | S33 | ◐ | Framing is a synthesis of cited signals; wording is original. |
| Monetization expectations ($0–$500/month) | S15, S16 | ○ | Order-of-magnitude estimate based on SkyrimNet figures; not a guarantee. |
| What to avoid (Verified Creator Program for external tools; paywalled support) | S6, S7, S9 | ✅ | Platform rules cited above. |

---

## 4. Discrepancies and time-sensitive figures

### 4.1 SkyrimNet Patreon figures

The two sources disagree because they are different snapshots:

| Source | Paid members | All members | Earnings/month |
|---|---|---|---|
| Patreon page (S15) | 136 | 1,655 | $854 |
| Graphtreon (S16) | 124 | 1,608 | $773 |

`docs/05` uses **~1,649 members and ~$845/month** as a rounded midpoint. Replace
with a dated snapshot before publication.

### 4.2 Nexus Donation Points

The official FAQ (S8) states **1,000 DP = $1** [reference:45]. One secondary source
(S24, line 40) states "1 DP ≈ $0.0001," which is off by an order of magnitude.
Treat the official FAQ as authoritative.

### 4.3 Tool capability claims that need re-verification before release

The following statements in `docs/04` are **partially supported** and should be
checked against the tools themselves before the landscape document is published:

- DBL Save Inspector's LZ4 SE/AE support and Save Comparison feature (S12).
- ReSaver's quest pages and "Compare to another save" (S13).
- Strange Labs' alpha limitation to vanilla quests (S24).
- Codifix's 10-second Papyrus polling (S23).
- SkyrimNet's diary-creation feature (S17).
- CHIM's diary and quest tracking specifics (S19).
- Savecraft's proprietary hosted layer (S22).
- The exact `#0` placeholder behavior for removed plugins (S1, S13).

### 4.4 Claims that are design, not research

These are intentionally not sourced because they are project decisions:

- Snapshot/diff schemas.
- CLI command names and flags.
- Error message wording and `--force` policy.
- Append-only journal format.
- Roleplay profile manifest schema.
- Phased plan.
- Monetization estimate ($0–$500/month).

---

## 5. Maintenance

- Re-check all URLs and time-sensitive figures before any public release.
- When a document changes materially, update the corresponding table in §3 and
  add a dated note.
- When a new external source is introduced, add it to §2 and cite it in the
  relevant per-document table.
- Keep the verification legend honest: if a capability is inferred rather than
  confirmed, mark it ◐.