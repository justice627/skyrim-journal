# Value Strategy: Monetization, Open Source, Career

The honest assessment: **direct monetization is the weakest path, open-source
contribution is moderate but legally constrained, and career development as an
AI-engineering artifact is the strongest and most actionable.**

## 1. Monetization

### 1.1 Platform rules constrain paywalling

- **Nexus Mods** donation guidelines state that "paid modding is in direct
  conflict" with their mission and that "direct monetisation of mod content
  violates the EULAs" in most cases. Modders may accept donations (PayPal,
  Patreon, Ko-Fi) and earn Donation Points (1,000 DP = $1 USD), but cannot
  charge for files, updates, or support.
- **Wabbajack** mirrors this: donations allowed, modlists cannot be paywalled,
  support cannot be tiered behind payment.
- **Bethesda Verified Creator Program** pays royalties for in-game Creations
  sold via the Creations platform — this is game content, not external tools.

### 1.2 What AI-enhanced Skyrim tools earn

- **SkyrimNet** has ~1,649 Patreon members at roughly $845/month (reported).
  Meaningful supplemental income, but far from a primary revenue stream, and it
  comes from a runtime in-game experience with broad appeal.
- The general developer-tooling pattern is **open-core**: free core, paid team
  features, SSO, security, or hosted scale. Open-core works when there is an
  enterprise/team buyer; a personal Skyrim journal has neither.

### 1.3 Realistic narrow path: hosted convenience

**Savecraft** split its codebase at a trust boundary: the local client
(daemon, parsers, in-game mods) is Apache 2.0 open source, while the hosted
product (API, web app) is proprietary. Applying the same model:

- Open-source CLI and parser (free, permissive license).
- Optional paid hosted dashboard ingesting snapshots, rendering the journal,
  sending notifications — a separate service, not a mod file or support tier.
- **Donations / GitHub Sponsors** as a low-friction supplement. GitHub Sponsors
  has moved over $100 million to maintainers, but most individual projects
  remain underfunded.

**Verdict:** do not build *for* money. Build it well; if adoption is meaningful,
add a hosted convenience layer or donation link. Expect $0–$500/month at
realistic adoption.

## 2. Open source

### 2.1 Community rewards longevity

SkyUI's return after nine years came with a **full source-code release**,
explicitly so the community could maintain it "for many years to come." The
Skyrim modding community has learned that closed tools die with their authors.
An open-source save-journal pipeline would be welcomed — especially if it is
read-only, cross-platform, and does not require MO2 or a running game.

### 2.2 Legal/platform positioning

Nexus and Wabbajack rules govern mod files and modlists, not standalone CLI
tools. A standalone Python package distributed via GitHub and PyPI sits outside
those rules. If promoted *through* Nexus mod pages, it must comply with donation
and anti-solicitation rules. Safest positioning: **a developer tool on
GitHub/PyPI**, optionally listed on Nexus as a "tool" with donation links only.

### 2.3 Adjacent tools exist but the niche is open

`savetracker` is general-purpose and lacks Skyrim semantic extraction.
`Savecraft` serves structured state to assistants but does not produce a
factual/narrative journal, and its hosted product is proprietary. The niche —
Skyrim-specific semantic extraction + typed diff + strictly separated
factual/narrative journal + agent-native CLI — is narrow enough to be a genuine
contribution and narrow enough that general-purpose tools will not absorb it.

**Verdict:** open-source by default. Treat it as a durable portfolio artifact
and public good, not as a major community project overnight.

## 3. Career development (strongest path)

### 3.1 What agentic AI hiring managers screen for

Research is consistent: hiring managers want **agents that work in
production-like conditions**, not chatbot demos — tool use, error handling,
evaluation, state management. Valuable portfolio projects show structured
outputs with validation, retry logic, confidence scoring, and end-to-end tests.
Recruiters distinguish **capability** (followed a tutorial) from **readiness**
(can ship autonomous workflows).

### 3.2 Signal mapping

| Hiring signal | How this project demonstrates it |
|---|---|
| Tool use / MCP integration | CLI orchestrated by Claude Code; stages independently callable. |
| Error handling under uncertainty | Corrupt/unsupported/in-progress saves; unresolved FormIDs with graceful degradation. |
| Structured outputs with validation | Typed JSON snapshots and diffs; programmatic factual log. |
| State management | Snapshot persistence, append-only journal, diff against previous run. |
| Evaluation | Parser tests on synthetic and real fixtures; diff tests with known mutations. |
| Grounding / anti-hallucination | Factual/narrative separation as a concrete guardrail pattern. |
| Domain depth | Binary format parsing, LZ4, FormID resolution — parsing under ambiguity. |

### 3.3 Framing

The strongest AI engineer profiles are framed around domain-specific agentic
systems — legal agents, insurance claims, production evaluation pipelines.
"Skyrim save parser" sounds niche, but the engineering problem is general:
parse a proprietary binary format, reconstruct semantic state, diff against a
prior state, and generate grounded narrative under strict separation.

**Frame it as:** "An agentic data pipeline for an undocumented binary format,
with typed state reconstruction, diff-based change detection, and a grounded
narrative layer." That is the language of AI engineering, not modding.

## 4. Other value

- **Learning vehicle with personal utility.** Solves a real problem for you;
  reduces pressure to monetize.
- **Foundation for a broader "game state → narrative" pattern.** The
  parse/diff/narrate architecture generalizes to other stateful systems
  (`df-storyteller`, `The Imagine Loop`, `savetracker` are adjacent precedents).
- **Consulting/freelance credibility.** A public, working agentic pipeline with
  tests, error handling, and a clear README is more convincing than a
  certificate and more specific than "I build LLM apps."

## 5. Recommended sequencing

1. **Primary — career development.** Build as a reference-quality agentic
   pipeline. Document architecture decisions (typed diffs, factual/narrative
   separation, unresolved-FormID handling). Write short engineering notes that
   frame the project in AI-engineering terms.
2. **Secondary — open source.** Release parser + CLI under Apache 2.0 or MIT via
   GitHub and PyPI. Position as a read-only developer tool, not a mod. Accept
   donations; do not gate features.
3. **Tertiary — monetization, only if adoption justifies.** Consider a hosted
   dashboard (Savecraft-style split) or paid commissions. Do not paywall the
   core tool.

### What to avoid

- Bethesda Verified Creator Program (in-game Creations only, not external tools).
- Paywalled support or early builds if promoting via Nexus or Wabbajack.
- Monetization infrastructure before demonstrated demand.

## 6. Bottom line

The project is not redundant — savetracker and Savecraft are adjacent but
general-purpose, and none combines Skyrim-specific semantic extraction with a
strictly separated factual/narrative journal and an agent-native CLI. But the
business opportunity is **not in selling the tool**. It is in using the tool as
a credible, public demonstration of agentic engineering — parsing under
uncertainty, typed state, diffing, grounding, error handling — which is what
the AI engineering market is hiring for. Monetization is a distant third.