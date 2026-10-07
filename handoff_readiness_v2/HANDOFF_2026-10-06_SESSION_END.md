# Handoff — 2026-10-06, pause point

Picks up from `RECOVERY_CHECKPOINT_2026-10-06.md`. Read that first for the
production-host and Gate 2 state, which this session did not change.

## The candidate moved. Use `a0631e5d`.

`crv2-release-integration` tip is `a0631e5d`. The line from the previous
checkpoint's candidate:

| commit | what | product code? |
|---|---|---|
| `f0cf7be4` | previous candidate; what the production services ran until the 2026-10-07 cutover | — |
| `e171a8b6` | instructor language preference restored on fresh login | yes (pre-existing) |
| `e55b6193` | deadline scheduler unit + timer | no, `deploy/` only |
| `9646faf9` | load sampler: refuse an under-sampled connection measurement | no, harness only |
| `f3ebfd4f` | load profile: attribute a latency breach before reporting one | no, harness only |
| `a0631e5d` | instructor console game selection ordered | **yes** |

**Why the candidate advanced past `f0cf7be4`:** that commit does not contain
`e171a8b6`'s language repair, and `e55b6193`'s deadline units were already
installed on the host from a commit outside the candidate. Gate 1's automated
half had already been run at `e171a8b6` by an earlier session; those artifacts
were volatile in `/tmp` and are now preserved at
`evidence/gate1-2026-10-06-e171/` with `SHA256SUMS`.

**SUPERSEDED 2026-10-07:** production was cut over to `f62fc720`; see
`evidence/cutover-2026-10-07/README.md`. As of this 2026-10-06 handoff,
**the production services still run `f0cf7be4`** from
`/home/ubuntu/projects/globalstrat-plus-candidate-f0cf`. Nothing in this
session changed production, any service, or any production data. Cutting over
to `a0631e5d` is a Gate 2 action and has **not** been done.

## Done this session

**Gate 1 at the candidate.**
* Backend suite at `e55b6193`: 1,869 tests, OK, clean tree.
* Backend suite with the `a0631e5d` change: **1,873 tests, OK, rc=0**, 478.6 s.
* Frontend evidence carries by tree identity: the `frontend` tree object is
  `12f3067b…` at `f0cf7be4`, `e171a8b6`, `e55b6193` and `a0631e5d`, and a
  build from the candidate worktree produced asset hashes byte-identical to
  the Gate 1 build.

**Gate 3's long-open combined-load item — closed at field size.**
`COMBINED_RESOLUTION_LOAD_REPORT_2026-10-06.md`,
`evidence/load-failure/combined-resolution-2026-10-06/`. 96 sessions, client
p95 901.4 ms / server p95 669.2 ms against a 2000 ms threshold, 0 5xx, 0
transport failures, resolution 200 in 26.2 s, peak 33 of 100 connections,
0 deadlocks, 7,227 acknowledged writes reconciling exactly. The 3× margin
profile is recorded **inadmissible, not passed** and is its own open
checklist line.

**Three findings registered (V2-138, V2-139, V2-140).** The first two are
harness defects that had been *passing gates on measurements that never
happened*; the third is a product defect. All three are repaired. See
`V2_FINDINGS_REGISTER.md`.

**Browser walkthrough, rounds 1–3 of 10 — interim.**
`BROWSER_WALKTHROUGH_CANDIDATE_2026-10-06.md`,
`evidence/gate1-browser-2026-10-06-candidate/`. Round 1 is clean: four teams
through every decision screen with one entirely in zh-CN, 0 failed steps,
first-attempt console resolution with no intervention, and every financial
identity at $0.00 residual for all eight teams. Round 2 resolved with the
instructor console in zh-CN.

## Start here

**1. The fixture opens rounds whose deadline has already passed.** Rounds
2–10 carry fixed late-September dates, so every round after the first opened
already closed and the product correctly refused every write. That is the
whole of the 183 failed steps in rounds 2–3 and **none of it is a product
defect**. Before any further rounds, set each round's deadline relative to the
open — through the console's Extend Deadline control, so the path is exercised
rather than bypassed. Until then rounds 2+ measure only the deadline refusal.

**2. Finish the walkthrough** from round 2 with corrected deadlines: student
results and leaderboard screens in zh-CN after resolution, and a dispute
lookup. Then Gate 4 on the serving host.

**3. V2-140's operational half.** The console now opens on the instructor's
*lowest-id* active course, which is deterministic but means a shared account
lands on the **rehearsal** heat. Give the rehearsal its own instructor
account, or deactivate its course before the event. It is on the checklist.

**4. Still open and untouched by this session:** 3× combined load (needs a
generator host separate from the stack); the CRV2-07 sign-in storm (PBKDF2 at
Django's default work factor, owner: deployment); the remaining Gate 3 drills
and alert delivery; Gates 4 and 5; and everything the launch checklist still
carries unticked.

## Live state on this host, as left

* **Disposable walkthrough stack is still up** and is *not* production:
  backend `127.0.0.1:42229`, app `127.0.0.1:50011`, PIDs in
  `…/gate1-browser-2026-10-06-candidate/harness/runtime/stack.pids`, Docker
  container `globalstrat-gate1-browser-20261006-candidate-pg`. Game 1,
  "CE 2026 Heat A", 8 teams, rounds 1–3 processed, round 4 open. Tear it down
  with the pids and `docker rm -f` when it is no longer wanted.
* Docker container `globalstrat-gate1-e55b-pg` holds the backend-suite
  database; also disposable.
* Candidate worktrees added this session:
  `globalstrat-plus-candidate-{e55b,9646,f3eb,a063}`. `a063` is the one with
  the built frontend and the walkthrough harness.
* `walk-ce4-round-stoppers` (`63ad8a21`) is **stale**: its two P0 repairs
  reached the candidate by another route and its regression tests are in the
  suite. It can be removed; nothing depends on it.
* The VM `sudo` credential should still be rotated — `RECOVERY_CHECKPOINT`
  explains why. Not done here.
