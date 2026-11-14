# Skyrim Journal

An offline, read-only, agent-native pipeline that turns Skyrim save files into a
continuously updated, chronological playthrough log — with a strictly separated
factual record and narrative story.

## What it is

- **Parse** a `.ess` save file (LE or SE/AE) into structured JSON.
- **Diff** the current save against the previous run's snapshot.
- **Narrate** the changes into a factual log and a clearly flagged narrative.

Each stage is independently runnable. The tool never modifies or writes into the
save directory. It writes only to a separate data directory.

## Design principles

1. **Read-only.** Save files are treated as immutable inputs.
2. **Offline.** No running game, no SKSE plugin, no Mod Organizer 2 required.
3. **Agent-native.** A CLI-first pipeline that Claude Code (or any agent) can
   orchestrate and re-run, with persistent snapshots and an append-only journal.
4. **Factual/narrative separation.** The factual log is generated
   programmatically from extracted data. The narrative is LLM-generated and
   explicitly flagged as interpretation.
5. **Graceful degradation.** Corrupt saves, unsupported versions, and unresolved
   FormIDs produce clear messages and structured placeholders — never crashes.

## Quick start

```bash
pip install -e .
python -m skyrim_journal run --save-dir "/path/to/Saves" --data-dir ./data
```

Individual stages:

```bash
python -m skyrim_journal parse   --save "/path/to/save.ess" --out data/snapshots/
python -m skyrim_journal diff    --current data/snapshots/current.json \
                                 --previous data/snapshots/previous.json
python -m skyrim_journal narrate --snapshot data/snapshots/current.json \
                                 --diff data/diffs/latest.json
```

## Documentation

| Document | Contents |
|---|---|
| [`docs/01-research-parsers.md`](docs/01-research-parsers.md) | Existing parser survey, save format essentials, language choice |
| [`docs/02-architecture.md`](docs/02-architecture.md) | Pipeline design, stage contracts, error handling, testing |
| [`docs/03-roleplay-and-mods.md`](docs/03-roleplay-and-mods.md) | Roleplay profile manifest, mod incorporation, FormID resolution |
| [`docs/04-landscape-and-differentiation.md`](docs/04-landscape-and-differentiation.md) | Literature review, redundancy assessment, build-vs-adopt plan |
| [`docs/05-value-strategy.md`](docs/05-value-strategy.md) | Monetization findings, open-source strategy, career framing |

## Status

Planning / early development. See the documents above for the research basis.

## License

Apache 2.0 (proposed). See `docs/05-value-strategy.md` for the rationale.