# CC-5 Amendment A1 — Promote Rule Relaxation

**Amends:** specs/CC-05-fork-audit.md §4.2 (Promote rules)
**Reason:** The original rule set required BOTH "a current or drafted CC spec references it by name" AND "its absence would block build pipeline work". Execution revealed this over-constrained Promote for live runtime dependencies — 35 ghosts are actively called by working code paths, but named at subsystem level (not individual model level) by prior specs. The conjunction blocked legitimate promotion.

**Revised rule:**
A ghost is promoted if ANY of:
1. A current or drafted CC spec references it by name, OR
2. Live engine/view/orchestration code calls the model at runtime (not merely dormant imports), AND its absence raises relation-does-not-exist at that call site.

Plus both of the original supplementary requirements:
- Its schema is sufficiently defined to be promoted without archaeology.
- Promotion doesn't require schema assumptions unreviewed by the spec author.

**Prune remains the default for everything else.** Dormant imports with no runtime call remain Prune candidates. The distribution target of ≥70% Prune in §7.2 is relaxed to "majority Prune" — the real pre-condition was that dormant scaffolding dominates the ghost set; post-execution we know live-infrastructure ghosts actually dominate this fork, and that's a finding to document, not fight.

**Authorization for execution:** Option A from promotion_questions.md — promote all 35, grouped in subsystem-aligned commits, per-migration inspection before apply, halt on any schema surprise.
