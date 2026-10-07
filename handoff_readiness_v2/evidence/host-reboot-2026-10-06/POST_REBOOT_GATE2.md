# Gate 2's read-only checks, after the 2026-10-06 22:02 reboot

Run 2026-10-07 04:26 UTC from the pinned production worktree
(`globalstrat-plus-candidate-f0cf/backend`) against the production database,
with `/etc/globalstrat-plus.env` read via `sudo` and piped into the
environment — never written to disk, never passed on a command line.

Both commands are read-only. They are what the reboot owed: a reboot does not
rewrite sealed rows, and nothing in the service journals suggested it had, but
that was the absence of a suspicion rather than a confirmation.

## `verify_audit_chain --json`

* **`ok: true`**, `problems: []`
* **1,179 entries**, head `377feedf5502be64d8e1a5c39ef9135c3cc750bd2a83a372abc96f6bcd7b20ac`
* **`unsealed_total: 0`** — zero across all six audited tables
  (`decision`, `operator`, `game_deletion`, `authorization_refusal`,
  `sensitive_read`, `resolution_manifest`)
* External anchor agrees: `entries_anchored`, `entries_now` and
  `entries_replayed` all **1,179**, with the anchored head equal to the live
  head

The entry count and head match what `RECOVERY_CHECKPOINT_2026-10-06.md` recorded
before the reboot: 1,179 entries, no problems, no unsealed entries, anchor
matched.

## `install_audit_guards --check`

> All append-only audit guards are installed and enabled.

`missing_guards: []` in the chain output says the same thing independently.

## What this closes

The last read-only item the unplanned reboot owed. Nothing was changed on
production to produce it.
