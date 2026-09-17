# R17 — the backend half: the server's own sentence

**Date:** 2026-09-17
**Branch:** `crv2-12-r17-backend-wording`, cut from `crv2-release-integration` at `8be2efa`
**Finding:** V2-064
**Scope:** wording only. No lock, status code, `code` field, retry behaviour or
engine path was touched.

---

## 1. What was wrong

`backend/core/utils/participant_messages.py:211` (`lifecycle_in_progress`) read:

> This round is being processed. Refresh shortly to see the results.
> 本回合正在处理。请稍后刷新查看结果。

The boundary that returns it — `CompetitionDecisionWriteMixin._lifecycle_busy_response`
in `backend/core/views/decisions.py:231-251` — fires whenever **any** exclusive
operator action holds the game lock: a deadline change, an event injection, a
team edit, as well as Phase-1 resolution. For most of those the sentence is
simply false. It also told the student to *refresh to see results* that do not
exist, and said nothing about the thing that actually mattered: their edit was
not saved.

R17 ruled the message "must stop claiming the round is being processed and must
describe what actually happened". The client half landed earlier today; this is
the server half.

## 2. The new wording

```python
'lifecycle_in_progress': {
    'en': 'An instructor is changing this round right now, so nothing was saved. Your entries are unchanged, and your edit will be sent again in a moment.',
    'zh-CN': '教师正在调整本回合，因此未保存任何内容。您的输入未被更改，稍后将自动重新提交。',
},
```

**EN:** An instructor is changing this round right now, so nothing was saved.
Your entries are unchanged, and your edit will be sent again in a moment.

**zh-CN:** 教师正在调整本回合，因此未保存任何内容。您的输入未被更改，稍后将自动重新提交。

### Why it meets the GSP-CRV2-12 standard

Against `evidence/player-language/AUTHORING_STANDARD.md`:

| Rule | How this sentence meets it |
| --- | --- |
| 1 — name the business object, never the column | No field name appears. Checked mechanically: A3 masks placeholders and scans for `SNAKE` tokens against the 836 names read from `backend/core/models`; this entry has no snake_case token at all. |
| 2 — never show an internal id | No id, no game/team/round number, no `code`. The `code` stays in the response body as the machine contract and out of the prose. |
| 3 — say what the rule is **and** what to do next | Two sentences, in the standard's own order: the cause ("an instructor is changing this round right now"), then what follows for the reader ("your entries are unchanged, and your edit will be sent again in a moment"). The reader is told not to retype anything. |
| 5 — warnings and refusals must read differently | It states **"nothing was saved"** in words, which is the standard's literal test for a refusal. The old sentence read like a status notice about an accepted action. |
| 7 — both languages, same values in each | Both present; neither interpolates, so the placeholder sets are trivially identical (A2). |
| 8 — money/percentages formatted by the caller | No interpolation, so nothing to format. |

It does **not** name which operator action is underway — deadline change,
event injection, team edit. The boundary refuses before any handler runs and
does not know which action holds the lock, so naming one would be a guess. It
names the actor and the fact, which is what is actually known.

### How it reads beside the client sentence

The frontend catalogue entry `decision_save.lifecycle_conflict` reads:

> An instructor is changing this round right now, so nothing was saved. Your
> edit is still on screen and will be sent again in a moment.
> 教师正在调整本回合，因此未保存任何内容。您的修改仍在屏幕上，稍后将自动重新提交。

The two now share their **first sentence verbatim** in both languages, and
agree on the second: nothing was saved, the work is not lost, it will be resent.
One rule, worded once in meaning (standard rule 6), from two places that cannot
import each other across the process boundary.

**They are not shown stacked.** `contexts/DecisionContext.js:classifyFailure`
returns `{ kind: 'lifecycle', messages: [] }` — deliberately empty — so
`DecisionSaveAlert` renders the client sentence and **no** server bullet beneath
it. Only the `validation` kind passes the server's own sentences through. So the
server sentence is not restated on top of the client one, and I did not change
that.

Where the server sentence *does* still reach a student on its own is
`pages/FinancePage.js:129-133`, whose `saveErrorMessage` returns
`data.detail` raw into its own Alert. That page's `patchDecision` also matches
`isDecisionWrite`, so on the Finance page a contended save can show the client
alert and the Finance alert together. That is why the server sentence had to be
self-contained and non-contradicting rather than a fragment — it is read alone
there. Deduplicating those two surfaces is an interface change and is **not**
part of this wording-only branch; I am handing it over rather than doing it.

## 3. The test change

`backend/core/tests/test_competition_locks.py`. The assertion was not deleted —
it was moved from exact text onto the property R17 actually ruled on:

```python
detail = response.data['detail']
self.assertTrue(
    detail.strip(), 'a refused write must tell the student why')
self.assertIn('instructor', detail.lower(),
              'the refusal must name the instructor action that '
              'caused it')
self.assertIn('nothing was saved', detail.lower(),
              'a refusal must say the edit was not saved')
self.assertNotIn('being processed', detail.lower(),
                 'the round is not being processed for a deadline '
                 'change, an event injection or a team edit')
```

`self.assertEqual(response.data['code'], 'lifecycle_in_progress')` on the line
above is untouched, so the test still proves the refusal carries **both** a
message and a `code`. The surrounding proofs — 409, handler call count zero,
elapsed under 0.5s, uncontended write still executes exactly once — are
untouched.

Pinning meaning rather than the exact sentence is deliberate: the sentence is
participant copy and may be retuned by a UX review, while "names the instructor
action, and says nothing was saved" is the ruling and should break if reverted.

### Proof it fails against the old text

The old string was restored, the new test run unchanged, and the old string put
back:

```
FAIL: test_lifecycle_conflict_refuses_mutation_without_waiting_or_executing
  File ".../backend/core/tests/test_competition_locks.py", line 78
    self.assertIn('instructor', detail.lower(),
AssertionError: 'instructor' not found in 'this round is being processed.
refresh shortly to see the results.' : the refusal must name the instructor
action that caused it

Ran 1 test in 6.020s
FAILED (failures=1)
```

## 4. Other copies of the same claim

Swept with `grep -rn "being processed\|正在处理\|lifecycle_in_progress"` over the
tree, excluding `node_modules`.

**Fixed — one.** `participant_messages.py:211-213` is the only place the claim
is *authored*. There is no second catalogue entry and no duplicated sentence;
`cohort_messages.py` has no lifecycle entry.

**Left alone, with reasons:**

| Location | Why it stays |
| --- | --- |
| `backend/core/views/decisions.py:1070` — "Round N has already been processed" | A **different and true** claim: it is guarded by `rnd.status == 'processed'`, so the round really has been processed. Different code (`round_already_processed`), different condition. Changing it would introduce an error, not remove one. |
| `backend/core/engine/instructor_alerts.py:58`, `backend/core/engine/advance_round.py:697` | Internal docstring/comment about real round processing. Not participant copy, and out of bounds for this branch. |
| `contexts/DecisionContext.js:12-18` docstring | Describes the *ruling* ("R17 ruled that it must stop claiming the round is being processed") and explains why the client matches on `code`, not on the sentence. Still accurate, and still the right guidance. |
| `handoff_readiness_v2/OWNER_DECISIONS_PENDING_2026-09-16.md`, `OWNER_RULINGS_2026-09-12.md`, `V2_FINDINGS_REGISTER.md`, `completion/OPEN_INTERFACE_DEFECTS_2026-09-17.md` | Dated records that quote the old sentence as evidence of the defect. Rewriting them would destroy the record. Three of the four are also explicitly off-limits to me. |
| `evidence/open-interface-defects/{before,after}/browser-*.json` | Captured artifacts of browser runs that actually happened. `after/browser-en.json:186` genuinely recorded the old server sentence, because the client half shipped before this branch. Editing a captured run would be falsifying evidence. |
| `evidence/player-language/STATIC_STRING_INVENTORY.{md,json}` | See below — stale, but not by my hand. |

### A pre-existing finding: the CRV2-12 inventory is already stale

`generate_inventory.py --check` exits **1 before this branch touches anything**:

```
CRV2-12 inventory is stale; rerun generate_inventory.py     exit 1  (0.60s)
```

Regenerating on the unmodified tree rewrites **1,661 insertions / 1,287
deletions across the two inventory files** — drift from today's earlier work
(the new `decision_save.*` keys, the translated `instructor.*` keys), not from
this change. I regenerated only to measure that, then reverted both files; this
branch leaves them exactly as it found them. Rewriting 1,600 lines of another
builder's drift under a wording commit would bury it.

Two of those stale rows (`STATIC_STRING_INVENTORY.md:1107-1108`) quote the old
`lifecycle_in_progress` text, so my change adds to an already-stale file. **This
is unrepaired and is handed to you**: the refresh belongs with whoever settles
the rest of the drift, and it is not a gate this branch was asked to hold.

## 5. Commands, counts, durations

Run from the isolated worktree. Every test run used its own disposable
PostgreSQL container under `flock -w 1800 /tmp/globalstrat-backend-test.lock`.
The production database was never contacted and no systemd environment file was
read. No process was killed by pattern.

| Command | Result | Duration |
| --- | --- | --- |
| `./backend/scripts/check-participant-strings` (baseline, before edit) | **PASS** — 4,567 units, 0 findings, 0 suppressions | 0.178s |
| `./backend/scripts/check-participant-strings` (after edit) | **PASS** — 4,567 units, 0 findings, 0 suppressions | 0.185s |
| `./backend/scripts/check-participant-strings-selftest` | **PASS** — 34 ok, 0 failed | 0.760s |
| `backend/scripts/test-postgres core.tests.test_competition_locks --parallel 8` (new wording) | **OK** — ran 1 test | 16.563s (test 5.791s) |
| same, with the old string restored | **FAILED (failures=1)** — the proof above | 16.808s (test 6.020s) |
| `generate_inventory.py --check` (baseline, untouched tree) | **exit 1**, stale — pre-existing, see §4 | 0.598s |

`allow_unresolved_keys` is **still `{}`** and `allow_literals` is still `{}` —
`backend/scripts/participant-strings.config.json` is byte-for-byte untouched.
That property was not spent. `MANIFEST_SCHEMA_VERSION` stays **6**; no
migration; nothing under `backend/core/engine` was modified.

No full suite was run — that is the freeze candidate's gate, not this branch's.

## 6. Register wording for V2-064

> **2026-09-17 — backend half complete.** `lifecycle_in_progress` no longer
> claims the round is being processed. It now reads "An instructor is changing
> this round right now, so nothing was saved. Your entries are unchanged, and
> your edit will be sent again in a moment." / "教师正在调整本回合，因此未保存
> 任何内容。您的输入未被更改，稍后将自动重新提交。", sharing its first sentence
> verbatim with the client's `decision_save.lifecycle_conflict` and agreeing
> with it on the rest. `test_competition_locks` no longer pins the old text; it
> pins the ruling — the refusal carries a message **and** a `code`, the message
> names the instructor action, says nothing was saved, and does not claim the
> round is being processed. Proven to fail against the old string. Wording only:
> the lock, the 409, the `code` and the retry are unchanged.
> `check-participant-strings` passes at 4,567 units with `allow_unresolved_keys`
> still empty. **Still open on this finding:** `FinancePage.js:129-133` prints
> `data.detail` into its own Alert, so a contended save on that page can show
> the client notice and the server sentence at once — a deduplication that is an
> interface change, not a wording one. **Separately noted:** the CRV2-12 static
> string inventory was already stale before this branch (1,661/1,287 lines of
> drift from today's earlier work) and was deliberately left untouched.

## 7. What I am not claiming

No gate is closed by this branch. I ran one focused test, two string checks and
a selftest; I did not run the full suite, did not exercise a browser, and did
not verify the sentence on a rendered Finance page. The `FinancePage` double-
surface and the stale inventory are both open and both described above.
