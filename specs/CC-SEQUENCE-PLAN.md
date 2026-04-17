# globalstrat+ CC Sequence Plan

**Project:** globalstrat+ (Chinese executive supply-chain-centered strategy simulation)
**Document status:** Living — updated as specs land and new bundles are scoped
**Last revised:** At CC-3 draft (CC-1 and CC-2 landed; CC-3 underway)
**Observes:** `specs/STANDING-DISCIPLINE.md`

---

## 1. Purpose

This document consolidates the planned CC (Claude Code handoff) bundle sequence for globalstrat+ in one place. It exists because the sequence was previously scattered across individual spec files, and the project needs a single navigable reference for:

- What bundles are planned, in what order, and why
- What each bundle depends on
- What's landed, what's underway, what's upcoming
- Non-CC work streams that run in parallel to the CC sequence
- The critical path to a shippable globalstrat+ v1

This document is maintained as a running reference. Each time a CC bundle is drafted, queued, executed, or merged, the status table is updated. When new bundles are scoped, they're added with a placeholder entry.

---

## 2. Current Status Snapshot

| Item | State |
|---|---|
| CC-1 (Scenario schema) | **Merged to main** (with Amendment A1) |
| CC-2 (Decision taxonomy) | **Merged to main** |
| CC-3 (Engine logic) | **Merged to main** (with CC-3.5 determinism + notification promotion, and CC-03 Amendment A1 step-ordering delta) |
| CC-4 (Data model) | **Merged to main** |
| CC-6 (Pedagogical design note) | **Merged to main** (with CC-03 Amendment A1; CC-04 Amendment A1 drafted, execution deferred pending post-CC-4 follow-up) |
| Standing discipline document | Established, at v1.1 (after Amendment A1 §1.8 and §1.9 additions) |
| GlobalStrat fork | Bootstrapped at `/home/ubuntu/projects/globalstrat+/`, DB `globalstrat_plus`, Qdrant `globalstrat_plus_articles` (empty) |
| Ghost model roster | Identified (40 ghosts), triage deferred to CC-5 |
| RAG source curation | Not yet started |
| Home market commitment | **Resolved in CC-6 §3.1:** v1 launches with Chinese-firm-going-overseas framing for Phase 2 narratives; schema and engine remain home-country-agnostic; alternate framings are extension-ready. |

---

## 3. Foundation Specs (CC-1 through CC-6)

The foundation layer establishes the conceptual contracts that all build-pipeline work references. Most are schema / taxonomy / algorithmic specification rather than implementation code.

| # | Bundle | Purpose | Depends on | Status |
|---|---|---|---|---|
| CC-1 | Scenario schema | Defines the scenario YAML schema — what's inherited from GlobalStrat, what's extended, what's new (suppliers, lanes, trade finance, compliance, SC events, resilience parameters, freight market) | — | ✅ Merged (+ Amendment A1) |
| CC-2 | Decision taxonomy | Every decision page, every field, validation, progressive disclosure schedule. INHERIT/EXTEND/NEW classification. Field inventory report of existing decision models. | CC-1 | ✅ Merged |
| CC-3 | Engine logic | Per-round pipeline changes. 28-step Phase 1 sequence (29 at original draft; reduced to 28 by CC-03 Amendment A1 folding supplier-origin-trust into preference initialization). INHERIT/EXTEND/NEW classification. Pseudocode for seven NEW and four EXTEND algorithms. Phase 2 LLM-narrative discipline. Event system integration. Engine inventory report of existing pipeline. | CC-1, CC-2 | ✅ Merged (+ Amendment A1) |
| CC-4 | Data model | Django model definitions for all NEW decision pages, EXTEND field additions, supporting state (SupplierState, LaneState, HedgePosition, etc.), migrations. Serializers and DRF API endpoints for decision submission and round outcomes. | CC-1, CC-2, CC-3 | ✅ Merged |
| CC-5 | Fork audit | KEEP / ADAPT / DISCARD / NEW classification against every module in the forked GlobalStrat codebase. Ghost model triage (prune / promote / document-as-dormant) for the 40 ghosts identified. Named triage targets surfaced so far: `financials.FinancialExpense` (dormant import at `preference_engine.py:22`, table missing — deferred here per CC-3 inventory and Halt #4 resolution in CC-3.5). Instructor panel fork pass. | CC-1 through CC-4 (can begin once CC-4 is drafted) | 📝 Not drafted |
| CC-6 | Pedagogical design note | Decisions locked: Chinese-firm-going-overseas framing for Phase 2 narratives (v1), instructor override on progressive disclosure schedule, instructor override on resilience weights, supplier-origin-trust earlier fold (→ CC-03 Amendment A1). Calibration register seeded with 7 open questions. Authoring priority tiers for v1 scenario roster. Companion: CC-04 Amendment A1 drafted with execution deferred pending CC-4 merge. | CC-1 through CC-4 (CC-5 not a hard prerequisite) | ✅ Merged (+ CC-03 Amendment A1) |

**Target completion:** foundation layer complete (CC-1 through CC-6 all merged) before build pipeline begins. CC-4 and CC-5 may be drafted in close succession; CC-6 is the gate to build work.

---

## 4. Build Pipeline (CC-7 onward)

The build pipeline implements what the foundation specifies. Bundles are sized at GlobalStrat's established granularity (one to a few focused deliverables per bundle).

### 4.1 Core Build (CC-7 through CC-15)

| # | Bundle | Purpose | Depends on | Status |
|---|---|---|---|---|
| CC-7 | Fork-and-clean execution | Django app renaming (if any), cleanup actions from CC-5 fork audit findings, ghost model pruning per CC-5 dispositions, final codebase hygiene pass | CC-5, CC-6 | 📝 Not drafted |
| CC-8 | Scenario seed data — Consumer Electronics | Full seed data for CE pilot: 20 suppliers across TW/KR/JP/CN/VN/MY/DE/US, 18 shipping lanes, 5 compliance regimes, 20 SC event templates, all trade finance instruments, BOM, realistic base prices and lead times | CC-1, CC-4 | 📝 Not drafted |
| CC-9 | Decision API endpoints | DRF endpoints for each new decision page submission and retrieval. Validation rule enforcement. Progressive disclosure gating. | CC-2, CC-4 | 📝 Not drafted |
| CC-10 | Frontend — Sourcing & Suppliers page | React page for supplier allocation, critical input categories table, multi-sourcing strategy, tier-2/3 visibility investment. Verify in browser: add supplier, set allocation, sum validation, submit | CC-9 | 📝 Not drafted |
| CC-11 | RAG content migration | Snapshot-restore `globalstrat_articles` → `globalstrat_plus_articles` with retroactive `payload.topic = "strategy"` tag. Ingest net-new SC corpus (80–120 articles) with `payload.topic` = supply_chain / trade_finance / compliance / logistics / resilience / chinese_institutional. Validation queries. | Curated corpus (from non-CC work stream), CC-1 §6 (Qdrant collection exists), CC-4 | 📝 Not drafted |
| CC-12 | Frontend — Logistics & Distribution page | React page for modal mix per lane, Incoterms per market, customs classification (CN teams), reverse logistics capacity. Verify in browser. | CC-9 | 📝 Not drafted |
| CC-13 | Frontend — Trade Finance & FX page | React page for buyer payment terms, Sinosure enrollment (CN teams), FX hedging positions. Verify in browser. | CC-9 | 📝 Not drafted |
| CC-14 | Frontend — Inventory & Resilience page | React page for buffer inventory policy, contingency plan triggers, narrative playbook. Verify in browser. | CC-9 | 📝 Not drafted |
| CC-15 | Supply Chain Dashboard (read-only) | Composite view: resilience score with component breakdown, single-source flags, geographic heatmap, supplier health summary, SC event log. Read-only; routes to decision pages for edits. Verify in browser. | CC-10 through CC-14 | 📝 Not drafted |

### 4.2 Instructor & Narrative Layer (CC-16 through CC-21)

| # | Bundle | Purpose | Depends on | Status |
|---|---|---|---|---|
| CC-16 | Instructor panel — SC extensions | Instructor views for: SC decision viewing per team, event injection UI, resilience score audit, compliance regime toggles per class, progressive disclosure override per class. Builds on 90% inherited GlobalStrat instructor panel. | CC-15, CC-5 (audit classification of existing instructor views) | 📝 Not drafted |
| CC-17 | Phase 2 LLM narratives | Prompt templates and orchestration for SC event narrative, Dashboard narrative, supplier persona updates, compliance warning notices, trade finance institution voices. Inference routing (persona-heavy → cloud Qwen-Max, structured → local Qwen 2.5). | CC-3, CC-11 | 📝 Not drafted |
| CC-18 | Compliance enforcement flow | End-to-end compliance enforcement: probability evaluation, shipment detention, market freeze, remediation cost, reputation impact feedback. Includes frontend surfacing of enforcement events. | CC-9, CC-17 | 📝 Not drafted |
| CC-19 | Multi-round event handling | Full implementation of `duration_rounds`, `recovery_rounds`, and recovery acceleration with alternatives. Tests against Taiwan earthquake, Red Sea disruption, and supplier financial distress scenarios. | CC-8, CC-17 | 📝 Not drafted |
| CC-20 | FX hedge lifecycle | Full hedge position lifecycle: open → mark-to-market per round → settle at maturity → book P&L. Currency pair expansion beyond USD/CNY if scenario demands. | CC-9 | 📝 Not drafted |
| CC-21 | Resilience scoring surface | Frontend display of resilience score with component breakdown on Dashboard and in round results. Instructor calibration UI (weights per class). | CC-15, CC-16 | 📝 Not drafted |

### 4.3 Validation and Content (CC-22 through CC-25)

| # | Bundle | Purpose | Depends on | Status |
|---|---|---|---|---|
| CC-22 | Integration test — 10-round simulation | End-to-end integration test across the full simulation: team setup, 10 rounds with automated decisions + event injection, expected outcome verification, reproducibility check. | CC-7 through CC-21 | 📝 Not drafted |
| CC-23 | Language support — EN/ZH translations | All new SC-related field labels, help text, validation messages, narrative prompt variants, Dashboard components, instructor panel additions. | CC-10 through CC-21 | 📝 Not drafted |
| CC-24 | Second scenario — Clean Energy Tech | Full seed data and validation for CETech scenario (solar, wind, batteries — with Xinjiang polysilicon exposure, cobalt/lithium geopolitics, CBAM). Tests scenario-swappability discipline. | CC-22 | 📝 Not drafted |
| CC-25 | Third scenario — Industrial Manufacturing | Full seed data for Industrial scenario per the existing GlobalStrat framing (OEM → ODM → OBM progression, aerospace/automotive certifications). | CC-22 | 📝 Not drafted |

### 4.4 Refinement and Polish (CC-26 through CC-38)

Reserved for refinement bundles surfaced during integration testing, usability feedback, and pilot deployment. Typical candidates: performance optimization, UI polish passes, bug fix rollups, additional scenario coverage, expanded event catalog, new analytical reports, documentation for instructors, onboarding flow for new classes, LMS integration, analytics export, certification issuance for completion, and similar concerns that the GlobalStrat sequence also accumulated in its later numbering.

Not pre-allocated — scoped as needed.

### 4.5 Actor Prompt Tuning (CC-39)

| # | Bundle | Purpose | Depends on | Status |
|---|---|---|---|---|
| CC-39 | Autonomous actor SC awareness | Prompt extensions for governments (customs/enforcement behavior), competitors (SC-aware strategies), partners (logistics partnerships), journalists/analysts (NGO reports, audit scores), investors (SC-risk lens). New actor classes: Suppliers (distinct from partners/competitors), Trade Finance Institutions (Sinosure as named actor, commercial banks, FX desks). | CC-17, CC-8 | 📝 Not drafted |

CC-39's numbering is deliberately late because actor prompt quality depends on having real simulation runs to tune against. Early-stage pilot feedback drives these prompts; doing them too early produces generic output that doesn't reflect actual gameplay dynamics.

---

## 5. Non-CC Work Streams

Work that happens in parallel to the CC sequence, not handled by Claude Code handoff specs.

### 5.1 RAG Source Curation (high priority, parallel to CC-1 through CC-10)

Assembly of the net-new SC content corpus that feeds CC-11. Six content buckets: foundational references (Incoterms, trade finance mechanics), regulatory compliance regimes (UFLPA, CBAM, BIS, Chinese export controls), logistics and modal economics, resilience and disruption case material, Chinese institutional context, academic theoretical grounding.

Target: 80–120 articles, matching GlobalStrat's 143-article depth for the strategy side. Quality-over-quantity discipline; copyright-compliant sourcing (primary government sources, open-access academic, freely-published executive summaries); consistent metadata intake template.

Output: curated article set in `/home/ubuntu/projects/globalstrat+/rag_sources/staging/` organized by bucket, ready for CC-11 to ingest.

A standalone RAG Source Curation Guide will formalize this when time permits (Candidate C from the parallel-tasks conversation).

### 5.2 Instructor Panel UX Design (moderate priority, parallel to CC-10 through CC-15)

UX design for SC-specific instructor panel additions: event injection interface, per-team resilience audit, compliance regime toggles, progressive disclosure overrides. Builds on 90% inherited GlobalStrat panel.

Output: wireframes or Figma-equivalent sketches that CC-16 implements against.

### 5.3 Deployment and Infrastructure (moderate priority, parallel to CC-20 onward)

Final domain commitment (currently placeholder "globalstrat-plus.camdani.com"). FRP tunnel configuration. ECS frontend hosting. Cloudflare DNS and SSL. Production database provisioning beyond the dev setup. Monitoring and logging.

Follows the same ECS → FRP → homelab pattern as GlobalStrat and other Camdani simulations.

### 5.4 Student-Facing Content (low priority until CC-22)

Consultant Handbook / Student Manual equivalent for globalstrat+. Demo PPTX for BNBU faculty workshop. Onboarding slides or video. Pedagogically-structured introduction to the SC decision layers.

Held until the simulation is demonstrably working end-to-end via CC-22.

### 5.5 Academic and Institutional Adoption (long-horizon)

BNBU faculty workshop (per prior commitment after positive reception from department head and Assistant Dean). Exec training pilot with the colleague teaching Strategic Management to Masters-level students. Potential publication of the sim's pedagogical design.

---

## 6. Critical Path and Parallelism

### 6.1 Critical path to shippable v1

CC-1 → CC-2 → CC-3 → CC-4 → CC-5 → CC-6 → CC-7 → CC-8 → CC-9 → CC-10 → CC-15 → CC-22

Approximately 12 bundles on the critical path. Everything else is either in parallel or in refinement downstream.

### 6.2 Parallelizable clusters

**Frontend decision pages** (CC-10, CC-12, CC-13, CC-14) can execute concurrently once CC-9 (Decision API endpoints) lands. Each is independent; they share only the common API contract.

**Instructor layer + narrative layer** (CC-16, CC-17) can execute concurrently once CC-15 (Dashboard) lands. CC-17's narrative prompts need the Dashboard as reference surface but don't depend on CC-16.

**Scenario expansion** (CC-24, CC-25) depends on CC-22 passing but can execute concurrently with each other.

### 6.3 Work streams decoupled from CC sequence

RAG source curation can proceed from today through CC-11. Instructor panel UX design can proceed from today through CC-16. Deployment planning can proceed from any point.

### 6.4 Soft-gated decisions

- **Home market commitment (CC-6).** Affects CC-8 (seed scope), CC-12 / CC-13 (UI conditional display logic), and CC-24 / CC-25 (scenario calibration for non-Chinese home teams if multi-home is chosen).
- **Ghost model dispositions (CC-5).** Affects CC-4 (which ghost models get promoted to real tables during model-definition work).
- **Resilience weight calibration (CC-6).** Affects CC-21 instructor UI depth; also affects CC-22 integration test expected outcomes.

---

## 7. Flagged Gaps

Items that have been referenced in specs but not yet given a named home:

- **Test infrastructure setup.** Unit test scaffolding, integration test harness, factory fixtures for scenario/team/round state. Could be its own CC bundle (CC-7.5 or rolled into CC-7) or inlined into each build bundle. Decision deferred to when CC-4 defines model structure.
- **Performance profiling.** Phase 1 determinism plus new SC algorithms could extend per-round computation time. Baseline profiling and optimization pass not yet scoped — typically handled in the CC-26+ refinement range.
- **Currency and FX rate source.** CC-3 pseudocode assumes `round_state.fx_rates` is populated. The source (static scenario YAML? external API? deterministic random walk from scenario baseline?) needs decision. Likely CC-4 or CC-6.
- **Inflation and working capital cost modeling.** GlobalStrat may handle this; if not, SC cash-conversion-cycle changes have nowhere to land. Verify in CC-3 inventory report, scope a bundle if needed.
- **Export pipeline for student performance records.** For issuing grades, certifications, or LMS export. Aligns with the Thornton HKICPA pattern but specifics unknown. Typically CC-26+ range.

These gaps are maintained in this section rather than silently dropped. When each is scoped into a named CC bundle, it moves from §7 to §4.

---

## 8. Revision Log

| Date / Milestone | Change |
|---|---|
| CC-1 merged + Amendment A1 | Initial sequence plan established. CC-1 through CC-6 foundation, CC-7 through CC-39 build pipeline sketch. |
| CC-2 merged | Status update only — no structural changes. |
| CC-3 drafted | Sequence plan created as standalone document. Gaps surfaced in §7. |
| CC-3 merged with halts surfaced | §3 CC-5 row amended to name `financials.FinancialExpense` as a specific ghost triage target, per CC-3 engine inventory Halt #4 and the CC-3.5 resolution scope (which explicitly defers FinancialExpense to CC-5). |
| CC-6 drafted + CC-03 Amendment A1 landing | Foundation layer closed. CC-6 locks four decisions: Chinese-firm-going-overseas framing for Phase 2 narratives (v1), instructor override on progressive disclosure unlock schedule, instructor override on resilience weights, supplier-origin-trust folded into preference initialization (reduces CC-3 Phase 1 step count from 29 to 28 via CC-03 Amendment A1). Seven calibration questions entered the living register. Authoring priority tiers (Consumer Electronics → Clean Energy Tech → Industrial Manufacturing → Media/Entertainment deliberately light) recorded as non-binding v1 guidance. CC-04 Amendment A1 drafted with execution deferred pending post-CC-4 follow-up bundle — introduces `ClassProgressiveDisclosureOverride` and `ClassResilienceWeightOverride`. §2 snapshot refreshed, §3 CC-3/CC-4/CC-6 rows updated. |

Future revisions append to this log as specs land and sequence evolves.

---

## 9. How to Use This Document

- **Drafting a new CC spec?** Check §3 or §4 for where it fits, note its dependencies, update the status column to 📝 Drafted when done.
- **Planning a parallel Claude Code session?** §5 (non-CC work streams) and §6.3 (decoupled work) identify candidate tasks that won't interfere with the active critical path work.
- **Onboarding a collaborator?** §2 (snapshot) and §6.1 (critical path) give the fastest orientation. Then read the foundation spec series (CC-1 through CC-3 as drafted; CC-4 onward as they land).
- **Writing a new amendment or pivot?** Update §8 (revision log) with a dated entry describing what changed and why.
- **Discovering a new gap?** Add it to §7. When it's scoped into a bundle, move it to §4.
