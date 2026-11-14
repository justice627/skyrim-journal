# Roleplay and Mod Incorporation

Two distinct problems:

- **Roleplay** is an *interpretive* problem: the save contains actual state, not
  intended build, backstory, or quest pathway.
- **Mods** are a *parsing and resolution* problem: mod records are present in
  the save, but their meaning depends on plugins that may or may not be present.

## 1. Roleplay

### 1.1 What the save can and cannot tell you

The save contains actual state: skills, perks, quest stages, inventory,
location, change forms. It does not contain the player's intended archetype,
backstory, moral alignment, or planned quest pathway. Roleplay must be
**declared externally** and used as a lens for diffing and narration.

Existing tools confirm this split. Dragonborn's Logbook frames itself as
recording "who you became," relying on a character sheet plus event capture.
Build planners such as LorerimPlanner4 and Skyrim Builds represent a build as a
structured plan — skill trees, perk selections, racial/deity modifiers, and a
narrative concept — not something recoverable from the save.

### 1.2 Roleplay profile manifest

A YAML/JSON file supplied once per character:

```yaml
identity:
  name: "..."
  race: "Nord"
  archetype: "skald"
  backstory: >
    Short prose used only for narrative framing.
build:
  perk_system: "vanilla" | "ordinator" | "vokrii" | "adamant"
  skill_targets: {destruction: 70, speech: 80}
  attribute_targets: {magicka: 200, health: 300}
  planned_perks: ["..."]
quest_pathway:
  dragonborn: false
  main_quest: "avoid" | "pursue" | "unspecified"
  factions_in_scope: ["Companions", "Thieves Guild"]
```

### 1.3 How the profile is used

The profile must **not** contaminate the factual log.

- **Diff annotation (grounded).** When a change matches a declared target, the
  diff can tag it factually:
  `Skill increased: Destruction 68 → 69 (target: 70; not yet reached)`.
  This compares two extracted numbers and a user-declared target — still
  strictly grounded.
- **Narrative framing (interpretive).** The narrative stage uses the backstory
  and pathway constraints to situate changes within the intended roleplay. If
  the profile says "non-Dragonborn" and the diff shows the Companions arc
  advancing, the narrative can frame it as a mercenary's journey. The factual
  log is unchanged; the narrative is flagged as interpretation.
- **Contradiction warnings (grounded).** If the profile says "no shouts" but the
  save contains shout records, or "main quest avoided" but a main-quest stage
  advanced, emit a factual warning — not a narrative judgment.

### 1.4 Alternate starts

Skyrim Unbound Reborn allows a non-Dragonborn start with no main quest, no
shouts, and no dragon-soul absorption, with configurable dragon timing.
Alternate Start – Live Another Life bypasses Helgen and lets the main quest wait
indefinitely. A "non-Dragonborn, main quest avoided" profile is therefore not a
fiction — it corresponds to a detectable state: absence of main-quest stages,
absence of shouts, presence of an alternate-start plugin in the load order.

## 2. Mods

### 2.1 FormID resolution (the core problem)

Change-form FormIDs are 3-byte `RefID` values:

- upper 2 bits = source type (0 = save FormID array, 1 = Skyrim.esm,
  2 = created / plugin index 0xFF, 3 = unknown)
- lower 22 bits = form ID

Mod-added records arrive as type-0 RefIDs; resolution requires the save's plugin
list (and light-plugin list for SE). Load order can change between saves; the
game remaps FormIDs, and removed plugins leave placeholder records (`#0`). The
parser must mirror this graceful degradation and emit structured placeholders
rather than drop changes.

### 2.2 Mod-added quests

Mod QUST change forms are structurally identical to vanilla QUST records. The
QUST flags include `CHANGE_QUEST_STAGES` (`0x80000000`),
`CHANGE_QUEST_OBJECTIVES` (`0x20000000`), and `CHANGE_QUEST_SCRIPT`
(`0x40000000`), so stage progress parses the same way. The challenge is naming:
the human-readable name lives in the plugin file, not the save.

### 2.3 Mod-added perks and perk overhauls

Perks are form references baked into the save; removing an overhaul
mid-playthrough leaves references to perks that no longer exist. The parser
extracts perk FormIDs and detects the active overhaul from the plugin list
(e.g., `Ordinator - Perks of Skyrim.esp`). With the overhaul present, use its
perk-ID-to-name mapping; otherwise fall back to vanilla or a placeholder. Perk
planners already maintain structured trees for vanilla and Ordinator; similar
data can be sourced from plugin parsing.

### 2.4 SKSE co-save

Mods using SKSE's serialization interface write custom data to the `.skse`
co-save under 4-character signatures (`'PLGN'`, `'NUM_'`, etc.). Most
roleplay-relevant state lives in `.ess`, so co-save parsing is not required for
v1. Record presence and size as mod-footprint metadata; leave a clean extension
point for deeper parsing.

### 2.5 Plugin enrichment

If plugin files are on disk, parse their headers/records to resolve FormIDs to
EditorIDs and FULL names. Candidate libraries: `bethkit` (typed SE record
models), `sse-plugin-interface` (pure-Python `.esp/.esm/.esl` reader),
`esplugin` (Rust). Enrichment is optional; the core parser must work from the
save alone. Missing plugins keep the placeholder.

### 2.6 Plugin-list changes as events

Each snapshot records the plugin list and light-plugin list. Plugin-list changes
between runs are factual journal events: a mod was added, removed, or reordered.
This matters for roleplay continuity, because a changed plugin list may leave
unresolved or remapped FormIDs, and the journal should explain why a name
suddenly became a placeholder.

## 3. Summary

| Concern | Design implication |
|---|---|
| Roleplay backstory | Not save-extractable. User-supplied profile manifest; narrative-only. |
| Build goals | Targets in profile; diff compares actual vs. target factually. |
| Non-Dragonborn / pathway | Detect alternate-start plugins and absence of main-quest stages; warn on contradictions. |
| Mod quests | Parse QUST normally; resolve via plugin list; placeholders for missing plugins. |
| Mod perks | Extract FormIDs; detect overhaul; use overhaul mappings when available. |
| SKSE co-save | Record presence/size; deep parsing is a future extension. |
| Plugin enrichment | Optional EditorID/FULL resolution from on-disk plugins. |
| Load-order changes | Journal plugin-list changes as factual events. |