# CC-6: globalstrat+ Pedagogical Design Note & Decision Register

**Project:** globalstrat+ (Chinese executive supply-chain-centered strategy simulation)
**Spec Type:** Foundation — design decisions, calibration register, authoring priorities
**Depends on:** `specs/CC-01-scenario-schema.md`, `specs/CC-02-decision-taxonomy.md`, `specs/CC-03-engine-logic.md`, `specs/CC-04-data-model.md`
**Observes:** `specs/STANDING-DISCIPLINE.md`
**Status:** Ready for Claude Code execution (with CC-04 Amendment A1 execution deferred until CC-4 merges)

---

## 1. Purpose

CC-6 closes the foundation layer of globalstrat+. Its job is threefold:

- Lock design decisions that have accumulated as open questions across CC-2, CC-3, and CC-4.
- Establish a living calibration register for questions that can't be answered until pilot data exists.
- Provide non-binding authoring priority guidance for v1 scope — where content effort should focus first given the BNBU Chinese-exec launch audience.

CC-6 is explicitly **not** an architectural spec. The SC architecture is settled by CC-1 through CC-4. The schema already supports multi-scenario, multi-home-country, instrument-gated-by-home-country, SC-layer-optional-per-scenario. CC-6 does not revisit those commitments. What it locks are the *pedagogical and content* decisions that shape what ships in v1.

---

## 2. Scope Discipline

**CC-6 decides:**
- Phase 2 narrative framing for v1 audience
- Instructor override policy on progressive disclosure
- Instructor override policy on resilience weights
- Supplier-origin-trust phase placement in the engine pipeline

**CC-6 defers via the calibration register:**
- Cognitive load pacing (needs pilot observation)
- Resilience weight numerical values (needs engine implementation)
- Recovery interpolation shape (needs engine + observation)
- Nested POST structure (needs CC-10 frontend experience)
- Multi-scenario simultaneous load (needs deployment context)
- Round 0 state seeding pattern (needs engine implementation)

**CC-6 does NOT:**
- Modify any prior CC spec (amendments handle that)
- Write engine or frontend code
- Lock scenario-specific content (authoring priorities are non-binding guidance, not scope contracts)

---

## 3. Part I — Decisions Locked

### 3.1 Chinese-firm-going-overseas framing for Phase 2 narratives (v1)

**Decision:** Phase 2 LLM prompts (per CC-3 §5.2) author narrative voices and framing assuming teams are Chinese firms expanding into foreign markets. This is a v1 content default, not an architectural lock — the engine and schema remain home-country-agnostic.

**Rationale:** The launch audience is BNBU Chinese executives with real work experience. Pedagogical specificity beats pedagogical generality for this cohort. A Sinosure officer speaking to "your firm" as a Chinese exporter lands with recognition; a German buyer discussing "your Chinese suppliers" activates mental models students carry in from their careers. Neutral framing loses this lift. The OEM→ODM→OBM progression, 走出去 ("going out") policy context, and BRI institutional apparatus are first-class narrative references rather than exotic asides.

Home-country mechanical gating (Sinosure, processing trade, rare earth licensing) is already in the schema via CC-1 §6.3 and CC-2 §6.2 — this decision does not affect that. It affects what the Phase 2 narratives *say* about a team's situation, not what the engine does.

**Implementation implications:**

- **CC-17 (Phase 2 LLM narratives):** prompt templates include a `team_home_context` variable. The v1 default variant hydrates this with Chinese-firm framing (institutional context, policy vocabulary, stakeholder relationships appropriate to a Chinese exporter). The template structure explicitly reserves an extension point for alternate framings — populated in v2 if and when a non-Chinese-audience adoption emerges.
- **CC-23 (EN/ZH translations):** Chinese-framed narrative content translates cleanly to ZH for Chinese-medium delivery. EN variant reads naturally to English-speaking Chinese executives (the audience often works in mixed-language settings).

**Extension point documented:** a future CC can introduce `team_home_context` variants for other audiences (European multinational, US firm, Global South SME) without touching engine, schema, or instrument gating. The cost is prompt authoring, nothing more.

### 3.2 Instructor override on progressive disclosure unlock schedule

**Decision:** Instructors can override the default progressive disclosure schedule per class. Individual fields can be unlocked earlier (or later) than the CC-2 §8 baseline, on a per-class basis.

**Rationale:** Progressive disclosure in CC-2 is designed for a 10-round semester with Chinese exec audience and moderate prior SC exposure. Real classes will vary — a compliance-intensive course may want Trade Finance depth from Round 2; a logistics-focused course may want Inventory & Resilience contingency plans from Round 3. Instructors know their cohort. The system should respect that knowledge rather than lock them into one schedule.

**Implementation implications:**

- **CC-4 Amendment A1 (deferred until CC-4 merges):** introduces `ClassProgressiveDisclosureOverride` model storing per-class, per-field unlock-round overrides. Write serializers consult this override before enforcing the CC-2 default.
- **CC-16 (instructor panel):** UI for viewing default schedule and overriding specific fields per class.
- **Default behavior:** no overrides means CC-2 §8 baseline applies exactly as specified. Instructors who don't touch the feature get the default experience.

**Guardrails:** overrides can shift unlock rounds forward (earlier) or backward (later), but not bypass validation rules or mechanically impossible configurations (e.g., unlocking Incoterms before a market is served).

### 3.3 Resilience weight override per class

**Decision:** Instructors can override the scenario-declared resilience score weights (CC-1 §6.6) per class. The sum-to-1.0 constraint is preserved; individual weights are adjustable.

**Rationale:** Resilience weights encode the relative importance of multi-sourcing, geographic diversity, buffer adequacy, modal flexibility, tier-2 visibility, and supplier financial health. Different pedagogical emphases warrant different weightings. A course on geopolitical risk may want geographic_diversity at 0.35; a compliance course may want tier_2_visibility at 0.30. Scenario defaults are calibrated for a general strategic-management course; instructors should have the scalpel to sharpen the emphasis.

**Implementation implications:**

- **CC-4 Amendment A1 (deferred until CC-4 merges):** introduces `ClassResilienceWeightOverride` model storing per-class weight overrides. CC-3's `compute_resilience_score` algorithm (§6.5) consults class overrides before scenario defaults.
- **CC-21 (resilience scoring surface):** instructor panel UI for viewing and adjusting weights, with sum-to-1.0 validation enforced at submission.
- **Default behavior:** no overrides means scenario defaults apply. Instructors who don't touch the feature get the scenario baseline.

**Guardrails:** weights must sum to 1.0 (±0.01 tolerance, same as scenario YAML validation per CC-1 §8). No single weight can exceed 0.6 (prevents degenerate single-component scoring). No weight can be negative or zero (every component must contribute some signal).

### 3.4 Supplier-origin-trust phase ordering — earlier fold

**Decision:** The supplier-origin-trust adjustment (CC-3 §6.6) folds into the segment preference initialization phase, not a standalone step between marketing-mix matching and Bass adoption. CC-3's Phase 1 step 11 is subsumed into the earlier preference-init step.

**Rationale:** Supplier-origin-trust is a foundational preference modifier, not a late-arriving adjustment. Treating it as a standalone step creates the wrong mental model — it implies supplier origin somehow modifies preferences *after* they're established, when pedagogically the truth is preferences are shaped *from the start* by what the buyer perceives about the upstream chain. Folding it earlier matches the actual causal model: a Chinese firm with Taiwanese suppliers selling to US buyers carries the trust composition into every subsequent evaluation, not as an adjustment layered on top.

Mechanically, this also simplifies the pipeline by removing one standalone step.

**Implementation implications:**

- **CC-03 Amendment A1 (applies immediately):** Phase 1 step 11 is removed as a standalone step. Preference initialization (which occurs before step 10 marketing-mix matching in the CC-3 sequence) is extended to include supplier-origin-trust computation as part of preference hydration.
- **CC-3 §6.6 algorithm unchanged:** the `apply_supplier_origin_trust` function still does the same work. Only the placement in the pipeline shifts.
- **Pipeline total step count:** CC-3 originally specified 29 Phase 1 steps; with this reordering it becomes 28.

---

## 4. Part II — Calibration Register (Living)

Questions that require pilot observation, engine implementation, or downstream context before they can be answered. Each entry records: the question, current default, constraints, options with tradeoffs, when to revisit, and who decides.

This section is a living document. Each entry's state updates as information arrives. New entries append as new calibration questions surface.

### 4.1 Cognitive load pacing of progressive disclosure

**Question:** Does the CC-2 §8 unlock schedule (Round 1 defaults hidden, Round 3 multi-sourcing + modal mix + buffers, Round 4 trade finance + Incoterms, Round 5 full stack) land at the right pace for BNBU Chinese execs with work experience?

**Current default:** As specified in CC-2 §8.

**Constraints:** 10-round semester total. Students need Round 5's full decision surface active for at least 5 rounds to meaningfully practice the complete system.

**Options:** (a) Keep as specified. (b) Accelerate — unlock everything by Round 4. (c) Slow down — push full-stack to Round 6. (d) Non-uniform: accelerate some tracks, slow others based on pedagogical priority.

**When to revisit:** After first pilot cohort completes Round 5. Instructor observation and student feedback drive adjustment. Decision 3.2 (instructor override) means this can be tuned per-class before a global default changes.

**Decider:** Don in consultation with the pilot instructor.

### 4.2 Resilience weight default values per scenario

**Question:** What are the correct numerical weights for `resilience_score_weights` in each scenario's YAML? CC-1 §6.6 shows sample weights (0.25 multi_sourcing, 0.20 geo_diversity, 0.15 buffer, 0.15 modal, 0.15 tier_2, 0.10 health) but these are placeholders, not calibrated values.

**Current default:** Sample values from CC-1 §6.6 as initial scenario baselines.

**Constraints:** Weights sum to 1.0. No single weight > 0.6. No weight ≤ 0.

**Options:** (a) Keep sample values. (b) Calibrate empirically after engine implementation by running test simulations and observing which components correlate with intuitive "resilient" and "fragile" team profiles. (c) Calibrate by scenario — Consumer Electronics may emphasize multi_sourcing (Taiwan exposure) while Clean Energy Tech may emphasize tier_2 (Xinjiang polysilicon).

**When to revisit:** After engine implementation (post-CC-4 build pipeline) but before first pilot cohort. Sanity check against a handful of manual test scenarios.

**Decider:** Don, informed by engine sanity testing.

### 4.3 Recovery interpolation shape

**Question:** CC-3 §7.3 uses linear interpolation from disrupted state back to baseline. Should this be linear, step function (instant recovery at round 0), exponential (fast early recovery tapering), or S-curve (slow start, fast middle, slow completion)?

**Current default:** Linear per CC-3 §7.3.

**Constraints:** Must be deterministic (per CC-3 §9). Must be monotonic (no oscillation). Must reach baseline by round `recovery_rounds_remaining = 0`.

**Options:** (a) Linear (current). (b) Exponential: `capacity = 1 - (1 - current) * exp(-k * rounds_elapsed)`. (c) S-curve. (d) Event-specific: each event template declares its recovery shape.

**When to revisit:** After integration testing (CC-22) when disruption events are firing and recovery patterns are observable.

**Decider:** Don, informed by observed realism vs. pedagogical clarity tradeoff.

### 4.4 Nested POST structure for SourcingDecision + SourcingAllocation

**Question:** CC-4 §6.2 chose flat-POST-then-materialize over DRF writable nested serializers. Should this persist, or does frontend experience (CC-10) suggest nested is cleaner?

**Current default:** Flat POST per CC-4 §6.2.

**Constraints:** API must support atomic submission (all allocations for a category submit together, not one-by-one).

**Options:** (a) Flat POST (current). (b) Writable nested serializers. (c) Hybrid: flat POST for single-allocation cases, nested for multi-allocation.

**When to revisit:** During CC-10 frontend implementation. If React form structure naturally produces nested payloads, flat-POST-then-split adds friction.

**Decider:** Frontend implementer in CC-10, with Don sign-off.

### 4.5 Multi-scenario simultaneous load

**Question:** Can the `load_scenario` loader handle two scenarios active in the DB simultaneously (e.g., both Consumer Electronics and Clean Energy Tech loaded, with a class assigned to one or the other)?

**Current default:** Single active scenario per installation assumed (inherited from GlobalStrat pattern).

**Constraints:** Scenario-content models are all FK'd to Scenario, so schema supports multi-scenario. The question is whether the loader and class-creation flow assume single-scenario.

**Options:** (a) Single active scenario (current default, lowest complexity). (b) Multi-scenario, class chooses at creation time. (c) Multi-scenario with scenario versioning (v1, v2 of same scenario coexist).

**When to revisit:** When a real deployment need emerges — typically when a second course or institution wants a different scenario while the first course is still running.

**Decider:** Don based on adoption context.

### 4.6 Round 0 state seeding pattern

**Question:** CC-3 assumes `SupplierState` and `LaneState` rows exist at round-advance time. Are they seeded eagerly when a class is created (Round 0 rows materialized upfront), or lazily on first round advance (rows created as needed)?

**Current default:** Implementation-time choice, not yet locked.

**Constraints:** Eager seeding adds complexity at class creation but guarantees rows exist. Lazy seeding keeps class creation simple but requires engine code to handle absent-row cases.

**Options:** (a) Eager at Round 0. (b) Lazy on first reference. (c) Hybrid: critical state eager (suppliers), auxiliary lazy (lanes).

**When to revisit:** During engine build-pipeline CC execution. Decide when first actual engine code is written.

**Decider:** Implementer, with Don sign-off.

### 4.7 Phase 2 prompt tone calibration

**Question:** Beyond the Chinese-firm framing decision (§3.1), what's the right register for Phase 2 narrative voices? Professional/dry, mentorship-flavored, journalistic, consultancy-polished?

**Current default:** Not set. Phase 2 prompts are authored in CC-17.

**Constraints:** Consistency within a given voice (a Sinosure officer's voice stays consistent across events). Audience-appropriate formality (Chinese exec audience expects professional, substantive tone — not casual).

**Options:** Various combinations of formality, warmth, and density. Best determined by authoring a few variants and testing against Don's judgment plus pilot instructor feedback.

**When to revisit:** During CC-17 prompt authoring. Likely iterates through pilot.

**Decider:** Don in consultation with CC-17 content authors.

---

## 5. Part III — Authoring Priority Recommendations (Non-Binding)

Guidance for where CC-8 (seed data), CC-11 (RAG ingestion), CC-17 (Phase 2 prompts), and CC-23 (translations) focus their effort. Not scope contracts — the schema supports any scenario mix at any authoring depth. These are recommendations for v1 launch window based on the Chinese-exec audience and the Decision 3.1 framing commitment.

### 5.1 Scenario authoring tiers

**Tier 1 — Full authoring for v1 launch:**
- **Consumer Electronics.** Pilot scenario. Fully populated supplier roster, shipping lanes, compliance regimes, events, trade finance instruments. The reference scenario every other CC spec tests against.

**Tier 2 — Strong v1 candidate if capacity permits:**
- **Clean Energy Tech.** Exceptionally strong SC fit for Chinese-exec audience. Xinjiang polysilicon (UFLPA textbook case), battery minerals (cobalt, lithium — geopolitical), CBAM (solar/wind hit hardest). Every SC mechanic lands with real-world anchoring. If v1 ships with two fully-authored scenarios, this is the second.

**Tier 3 — v2 candidate:**
- **Industrial Manufacturing.** Strong SC fit (OEM→ODM→OBM progression, certification unlocks). Substantial authoring effort required — precision components, aerospace/automotive supplier ecosystems, certification taxonomies. Worth doing, but not at the cost of Tier 1 or 2 depth.

**Tier 4 — Deliberately light:**
- **Media/Entertainment.** Thin SC surface (content licensing, streaming rights). Scenario YAML can leave `suppliers`, `shipping_lanes`, `compliance_regimes` sparse or empty. SC layer effectively off for this scenario. Still a valid GlobalStrat-style scenario for marketing, financing, and strategy layers; just not a globalstrat+ SC teaching vehicle.

### 5.2 RAG corpus authoring priority

Follows the same tier structure. For CC-11 ingestion:

- **First wave:** inherited GlobalStrat strategy content (snapshot-restore), plus Consumer Electronics SC content (semiconductors, electronics supply chains, Taiwan exposure, UFLPA on electronics).
- **Second wave:** Clean Energy Tech SC content (polysilicon supply chains, CBAM on solar/wind, battery minerals geopolitics).
- **Third wave:** Industrial Manufacturing content (certification ecosystems, tier-1 OEM relationships, industrial policy).
- **Not prioritized:** Media/Entertainment SC content.

Target volumes per tier as sketched earlier: ~30-40 articles Tier 1, ~20-30 Tier 2, ~15-20 Tier 3.

### 5.3 Phase 2 prompt authoring priority

For CC-17:

- **First wave:** Supply Chain Dashboard narrative (read-only team posture summary). SC event narratives for the 8-10 most likely events in Consumer Electronics (Taiwan earthquake, Red Sea disruption, UFLPA detention, container rate shock, supplier financial distress, BRI port expansion, LC rejection, CNY appreciation).
- **Second wave:** Supplier persona updates (Chinese, Taiwanese, Korean, Japanese, German supplier voices). Compliance warning notices (UFLPA, CBAM, BIS Entity List).
- **Third wave:** Trade finance institution voices (Sinosure officer, commercial banker, FX desk). Buyer voices by market.
- **Extension-ready:** all prompts structured with `team_home_context` variable. v1 variant populated for Chinese-home. Alternate variants deferred.

---

## 6. Companion Amendments

CC-6 ships with two companion amendments that translate Decisions 3.2, 3.3, and 3.4 into concrete spec changes.

### 6.1 CC-03 Amendment A1 — Supplier-origin-trust phase reordering

Applies immediately. Documentation-only change to CC-3's Phase 1 pipeline. Step 11 (supplier-origin-trust) is removed as a standalone step; preference initialization step is documented as including supplier-origin-trust computation. Pipeline total drops from 29 to 28 steps.

Full amendment document: `specs/CC-03-amendment-A1.md`.

### 6.2 CC-04 Amendment A1 — Instructor override models

Execution **deferred** until CC-4 merges. Introduces two new models (`ClassProgressiveDisclosureOverride`, `ClassResilienceWeightOverride`), their migrations, serializers, and endpoints. Modifies CC-4's write-serializer progressive disclosure enforcement logic to consult the override table.

Full amendment document: `specs/CC-04-amendment-A1.md`.

---

## 7. What This Spec Does NOT Cover

| Concern | Spec |
|---|---|
| Engine implementation of override consultation logic | Build pipeline CC after CC-4 Amendment A1 executes |
| Instructor panel UI for overrides | **CC-16** |
| Actual scenario seed content | **CC-8** |
| Actual Phase 2 prompt authoring | **CC-17** |
| Actual RAG corpus curation | Non-CC work stream (RAG Source Curation Guide) feeding **CC-11** |
| Fork audit classification of existing instructor panel views | **CC-5** |

---

## 8. Acceptance Criteria

CC-6 is complete when:

1. `specs/CC-06-pedagogical-design-note.md` exists (this file) and is committed to main.
2. `specs/CC-03-amendment-A1.md` exists and is committed. CC-3's step ordering is reflected in the sequence plan's foundation spec table notes.
3. `specs/CC-04-amendment-A1.md` exists and is committed, with execution status marked "deferred pending CC-4 merge."
4. `specs/CC-SEQUENCE-PLAN.md` revision log §8 has an entry for the CC-6 decisions landing.
5. Branch `cc-06-pedagogical-design-note` merged to main after verification.
6. No engine code, model code, or migration code is written in CC-6. CC-6 is documentation only.

**Report back with:** `git log --oneline` for the branch, list of the three spec files added, and explicit confirmation that CC-04 Amendment A1 is marked deferred and not yet executed.

---

## 9. Post-Foundation Sequence

With CC-6 merged, the foundation layer is complete. CC-1 through CC-6 (plus CC-01 Amendment A1, CC-03 Amendment A1, and CC-3.5) constitute the full contract that the build pipeline implements against.

Next in sequence:

- **CC-04 Amendment A1 execution** once CC-4 is merged. Small bundle — adds two models, migrations, serializers, endpoints.
- **CC-5 (fork audit)** — classifies existing GlobalStrat code as KEEP/ADAPT/DISCARD/NEW, triages the 40 ghost models (including the named `financials.FinancialExpense` target from the sequence plan), assesses instructor panel for extensions.
- **CC-7 onward** — build pipeline per the sequence plan §4.

---

## 10. Revision Log

| Date / Milestone | Change |
|---|---|
| CC-6 drafted | Initial decision register and calibration register established. Four decisions locked (Chinese-home framing, instructor override on progressive disclosure, instructor override on resilience weights, supplier-origin-trust earlier fold). Seven calibration questions tracked. |

Future revisions to the calibration register (Part II) or to scenario authoring priorities (Part III) append to this log.
