# Master sequence: launch readiness, then the advisory and macro builds

**Status:** Draft sequence, 2026-09-16. Not a CC spec, and not a ruling.
**Purpose:** one ordered list, so that competition readiness and the two proposed
builds stop competing for the same days and nothing falls between them.
**Companion:** `specs/PLAN-advisory-layer-and-macro-2026-09-16.md` holds the
technical design for the advisory and macro work. This document does not repeat
it; it says when each part may start, what it must prove, and what blocks it.

**The standing goal:** GlobalStrat+ runs an inter-university competition. Every
sequencing call below follows from that and from one rule — *a change that can
alter a stored result must not land between the last dress rehearsal and the
last round of the competition.*

---

## 0. Where things stand, 2026-09-16

Verified today unless stated. Corrections to the companion plan's "verified
starting state" are marked **[corrected]**.

| Item | State |
|---|---|
| Live database | Current: 19 pending migrations applied today; `showmigrations` reports none outstanding. |
| Services | `globalstrat-backend`, `globalstrat-narratives` (installed for the first time today), `globalstrat-frpc`, backup-monitor timer: all active. |
| Frontend | Deployed from current code, including the CRV2-13 repairs. |
| Model routing **[corrected]** | Every model call goes to the LiteLLM fleet gateway (`da8631e`). No provider SDK, no provider endpoint, no `DASHSCOPE_*` setting anywhere in the backend; `backend/.env` and `/etc/globalstrat-plus.env` carry `LLM_GATEWAY_URL`/`LLM_GATEWAY_KEY` only. The companion plan's "Bypasses" row and its `.env` note describe the state before that commit. |
| Guards | 21 source-scanning tests fail the build if a provider call returns; they run in CI and in the deploy gate, which has an attributable override (`MODEL_GUARD_OVERRIDE="<who>: <why>"`, recorded to a deploy log on the serving host). |
| Tests | Full backend suite 1013 passing. |
| Branch | `crv2-release-integration` = `main` = `3c99d74`, pushed. |
| Corpus | `globalstrat_plus_articles`: 475 chunks, **26 of 149** catalogued documents, MiniLM 384-dim. All 149 files resolve on disk, so this is a re-run, not a recovery. |
| Personas | The five in `persona_engine.PERSONAS` are BECSR's CSR cast, carried over in the fork. |
| Macro | Absent, as the companion plan describes. |

**In flight right now (four agents, dispatched 2026-09-16):** the V2-072
least-privilege database role; consolidation of the parked register branches;
an owner decision briefing; and the GSP-CRV2-09 GO/NO-GO re-audit. Phase 1 below
absorbs their results; nothing in Phase 2 or 3 may start on top of unverified
agent output.

---

## Phase 1 — Launch readiness. Nothing else starts until this closes.

Everything here either blocks a competition or decides how one is marked.

| # | Item | Owner | Done when |
|---|---|---|---|
| 1.1 | **V2-072**, the open P0: the app's database role can `SET ROLE postgres`. | Agent in flight, then DBA/operations to authorise production cutover | A restricted role runs the full suite and provably cannot escalate; cutover executed on the competition host; register updated with the evidence |
| 1.2 | **Credential state.** The Sep 4 rotation was reverted during the crash recovery, so the password that sits in BECSR's Git history is live again on the shared `donwh` role. | Owner decision, then `ops/rotate-db-credential.sh` | Either rotated (all three consumers updated and verified) or recorded as a dated, attributed acceptance. Silence is not a disposition. |
| 1.3 | **GlobalStrat v1's cron** still holds the rotated password; ~24,000 failures, 32 MB log. | Operations | Either repointed at the live credential or retired with its cron entry removed |
| 1.4 | **Owner rulings** on the findings that are blocked on a decision, including V2-117 (the communication-scoring scale). | Owner / PI | Each recorded in an `OWNER_RULINGS_<date>.md`, dated and attributed. V2-117 must be answered **before any cohort submits**: scored submissions cannot be rescored consistently afterwards. |
| 1.5 | **Register consolidation**, so the release branch's register is single-source. | Agent in flight | Merged, no ID collisions, suite green |
| 1.6 | **GSP-CRV2-09 GO/NO-GO re-audit.** | Agent in flight | Verdict recorded; every blocking item either closed or explicitly excepted by the owner |
| 1.7 | **Corpus re-ingest** — see Phase 1a. It is here, not in Phase 2, because students pay cash for briefs drawn from it. | Build | New collection verified, cut over, rollback proven |
| 1.8 | **Dress rehearsal**: a full multi-round game on the competition host with the competition scenario and 8 teams. | Operations | Completed with no P0/P1 findings |

**Exit gate.** Phase 1 closes when 1.1–1.8 are done and the re-audit says GO.
From that moment to the end of the competition, the branch is frozen to
defect repairs. No feature work lands in that window — that is what this whole
document exists to protect.

### Phase 1a — Corpus (may start immediately, in parallel; no engine risk)

The one Phase 1 item that is pure build work and touches no engine code.

1. Merge the richer metadata from the staging catalogue into
   `/home/ubuntu/projects/articles/catalog.json`; retire the staging folder once
   each of its 27 files is confirmed present in the articles repo (confirm by
   content hash, not by filename).
2. Deduplicate, and record what was dropped and why.
3. Re-embed **all 149** with bge-m3 through the gateway into a **new** collection,
   page numbers in the payload so citations can be built later.
4. **Conditions, because this is not as free as it looks.** bge-m3 is 1024-dim,
   so it needs a new collection *and* `EMBEDDING_MODEL` / `EMBEDDING_DIMENSION`
   changed. That activates `core/rag/embeddings._remote_embedding`, which is
   dormant today and has **no test coverage**: it needs tests and a verified
   failure path before it serves students. Keep `globalstrat_plus_articles`
   untouched until the new collection is verified, so rollback is a config
   change and not a re-ingest.
5. Verify by count and by retrieval: 149 documents present, and a set of real
   student questions returns better-grounded briefs than the 26-document
   collection. Record the comparison.

---

## Phase 2 — Advisory layer (proposed CC-40). Starts after the Phase 1 exit gate.

Design: companion plan, workstreams 1 and 3. Sequencing notes only here.

- **Depends on Phase 1a.** Advisors that cite pages need the page numbers the
  re-ingest adds.
- **Priced consults are a rules change, not a feature toggle.** They spend cash,
  so they sit inside the competitive hash exactly as analyst purchases do. Price
  and per-round cap need an owner ruling before implementation, not a default
  chosen by a builder.
- **The three constraints are the point, not the trimming.** Advisors must
  compute unlock rounds per decision field and coach only toward levers that are
  open; advisor output stays advisory, with `communication_eval` documented as
  the only route from prose to a grade; instructor steering rides the existing
  per-market tag field plus the scenario config keys.
- **Capacity is a real constraint, measured.** `tutor` answers in about 7s and
  `analyst` in about 45s on the shared GPU, at `MAX_CONCURRENT = 4`. Thirty teams
  consulting at once will queue past any sane request timeout, so consults use
  `tutor`, are paced by the same semaphore, and degrade visibly rather than
  hanging. Load-test before a cohort sees it.
- **Persona cast is authoring**, and the cast is the owner's call. The current
  five are BECSR's.

---

## Phase 3 — Macro layer (proposed CC-41). Built after Phase 2 lands; enabled after the competition.

**This is the recommendation the rest of the document exists to support.**

The macro layer is the right idea: per-market growth, inflation, policy rate,
exchange rate, country risk and a cost index as a seeded, deterministic walk
with drift, feeding market conditions, interest, COGS, segment growth and the
capital-markets valuation. It uses `exchange_rate_volatility`, authored and never
read. It would make the sim markedly more real.

It is also **the highest-risk change available to us**, because it runs inside
Phase 1 resolution and changes what teams are scored on. `macro_enabled=false`
reduces that risk; it does not remove it, because the code still executes in the
resolution path and a bug there is a wrong result, not a wrong sentence.

Therefore:

1. **Do not enable it for the competition.** Build it, prove it, ship it dark.
2. **Registration in `manifest_sections` is mandatory** — `test_manifest_determinism`
   failing on an unregistered table is the guardrail working, not an obstacle.
3. **The proof obligation is byte-identity, not test-passing.** With
   `macro_enabled=false`, a full replay of every shipped scenario must produce
   identical `output_sha256` for every round against a pre-change baseline. That
   evidence is the gate, and it is the CRV2-01 replay harness's job.
4. **Enable per scenario, for a teaching cohort first**, and only once a full game
   has been played end to end with it on.

---

## Decisions this plan needs from the owner

Not decisions — the list of them. Each belongs in an `OWNER_RULINGS_<date>.md`,
dated and attributed. The in-flight decision briefing
(`OWNER_DECISIONS_PENDING_2026-09-16.md`, being drafted) covers the register's
open questions; these are the ones this sequence adds.

1. **Credential** (1.2): rotate again, or record a dated acceptance.
2. **V2-117** (1.4): rubric, weight, or accept the new marking scale.
3. **Advisor roster**: the cast, and whether v1 ships fewer than nine.
4. **Consult pricing**: cash cost and per-round cap, or free.
5. **Quotation policy**: paraphrase with title and page, or verbatim quotation —
   a licensing question as much as a design one for HBR, McKinsey, Economist and
   Springer material.
6. **Macro pilot**: which scenario first, and confirmation that the competition
   runs with `macro_enabled=false`.
7. **Spec numbers**: CC-40 and CC-41, and whether CC-41 supersedes anything in
   the CC-26–CC-38 sequence.

---

## Risks this sequence is built to avoid

- **Feature work landing during a competition.** The freeze after the Phase 1
  exit gate is the mitigation, and the reason Phase 3 is last.
- **A determinism regression reaching a stored result.** Manifest registration
  plus byte-identical replay evidence, before the macro code is trusted.
- **A grade changing under a cohort.** V2-117 answered before any submission is
  scored, because scored submissions cannot be rescored consistently.
- **A silent retrieval regression.** The old collection stays until the new one
  is verified; cutover and rollback are both config changes.
- **Queueing under class load.** Consults paced and load-tested before students
  see them.
- **Work landing on unverified agent output.** Every agent result in Phase 1 is
  re-verified by a second party before anything is built on it.
