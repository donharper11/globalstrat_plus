# R47 — compliance investment charge: focused replay evidence

Subject: the R47 engine change (`funding_need.compliance_investment_total`
booked by `costs.calculate_operating_expenses`), inside the CRV2-01
determinism boundary. Manifest schema version **6** before and after.

Three runs on one disposable stack (`postgres:16-alpine` container
`globalstrat-r47-replay-pg`, databases `globalstrat_r47` and
`globalstrat_r47_control`, `COMPETITION_BACKUP_DIR` in the session scratchpad;
`harness_isolation.require_disposable_backup_dir` accepted it). The production
database at `192.168.50.38` was never contacted and no systemd environment
file was read. Phase 2 ran against an unreachable LLM endpoint
(`127.0.0.1:9`), as run C of the CRV2-01 evidence did; the RAG step reached
the Qdrant host `192.168.50.186` (read-only vector search, outside the
competitive hash).

| Run | Recorded at | Replayed at | Lever | Competitive hash | Result |
|---|---|---|---|---|---|
| 1 | `ee94c37` (R47) | `ee94c37` | used — `compliance_rows=5` ($400k, $400k, $200k, $0 across 4 teams) | `17f1f48d877b9273a7b561bc04eb25400da53cb68b1822bfe2dfd8de3e51db47` | **exact**, exit 0 |
| 2 (control) | `90b2dea` (base) | `ee94c37` (`--allow-source-mismatch`) | unused — `compliance_rows=0` | `763b827b089e161164f71b54346bc42b3433b1acb7bf17d8f825eb42bd8715aa` | **exact**, exit 0 |
| 3 (negative) | `ee94c37` | `90b2dea` (`--allow-source-mismatch`) | used (run 1's backup) | expected `17f1f48d…`, actual `2fcac81cdbdd112dee39e2242474dde75bb58ad868a25e7011bf56aabdb6105b` | **differs**, exit 3 |

Source tree digests: `861fafdf01f0e048b3b34b349c73b4b71ddf18ebde4398f61f3ec2d6489047c8`
(457 files, `ee94c37`) and `51725d6aafd2463e9cb6f9a061ad5f22c5e7ae9298e76ff500947ac7be9e2a3e`
(`90b2dea`, a `git archive` of the commit with `GIT_REVISION` set, no `.git`).
Run 1 verified the digest matched; runs 2 and 3 crossed it deliberately and
recorded the override in `source-identity.json`.

What the three runs show together:

- **Run 1:** a round that carries the charge replays byte-identically from
  its pre-resolution backup — the charge is a deterministic function of the
  hashed `compliance_investment` input rows.
- **Run 2:** with the lever unused, the R47 engine produces the same
  competitive hash as the base engine, so the change is byte-identical when no
  team invests — every stored replay for a round with no investment stands.
- **Run 3:** with the lever used, the base engine and the R47 engine differ,
  and the section diff in `run3-negative-charged-at-base/replay-report.json`
  is exactly the charge: `team.cash_on_hand` and `total_equity` differ by
  `400000` / `400000` / `200000` for the three investing teams and not at all
  for the fourth; `financials`, `market_revenue` (market profit),
  `performance`, `share_price`, `leaderboard`, `coherence` and `ai_investor_holding` move as a consequence (eight sections in all, listed in `section_diffs`).
  Replay evidence recorded before R47 for a round **with** an investment
  would therefore fail against this engine — by V2-137 there is no such
  round.

Each run directory holds `replay-report.json`, `source-identity.json`,
`input-verification.json`, the expected and replayed manifests and the
Phase-2 prose that was hashed (gzipped, as `--expected-manifest` reads them).

The same three runs were first taken at `3020eaa`, before a comment in
`views/decisions.py` was reworded and the fixture's return type fixed
(`ee94c37`, neither inside Phase 1). Every per-team figure in run 3's diff
(cash down by `400000` / `400000` / `200000`) was identical in both takes;
the hashes differ only because each recording is a fresh game with its own
name and team names in every natural-key token.
`*.fixture.log` is the fixture's per-round line for each recording. The
`*.sh` files are the exact scripts, with the scratchpad and worktree paths
replaced by `$SCRATCH` and `$REPO`.

`MANIFEST.sha256` lists every file; verify with `sha256sum -c MANIFEST.sha256`
from this directory.
