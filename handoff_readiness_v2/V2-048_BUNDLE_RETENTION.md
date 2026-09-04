# V2-048 — pre-rewrite bundle retention

**These two files are the only remaining copies of the pre-rewrite history.
They contain the revoked credential. Do not publish, copy off-host, or attach
them to a ticket.**

The credential they carry was rotated and revoked on 2026-09-04 and is
confirmed refused, so these are a rollback asset rather than a live exposure.
They are still handled as secret-bearing.

## Held

| | Bundle A (made for the rewrite) | Bundle B (pre-existing backup) |
|---|---|---|
| Path | `/home/ubuntu/v2-048-pre-rewrite/globalstrat-plus-full-20260904T013929Z.bundle` | `/home/ubuntu/projects/globalstrat_backup/globalstrat-plus-20260904T011324Z.bundle` |
| SHA-256 | `38c085f807ee75cae6c3a6904285490da7ddd07dfc301f72d58944170d6a98e2` | `ffa50a5d9751701409252999f61e73b84ff6c3775d06601a4871afcee6623f0e` |
| Bytes | 33798962 | 33827390 |
| Mode / owner | 0600 ubuntu:ubuntu | 0600 ubuntu:ubuntu |
| Refs | 70 | 70 |
| Credential-bearing commits | 15 | 15 |
| `git bundle verify` | complete history | complete history |

Bundle A also carries the Stage 3B checkpoint commits (`22878b3`, and the
rewritten `192b6e1`'s predecessors); Bundle B was taken at 01:13:24Z and stops
short of them. **Bundle A is the more complete preservation**; Bundle B is kept
because it independently contains the same pre-rewrite history and would
otherwise be an unrecorded copy of the credential.

Bundle A's directory (`~/v2-048-pre-rewrite`) is mode 0700.

## Retention

- **Held until: 2026-09-18** (14 days from 2026-09-04).
- The window exists because origin has already been force-pushed, so these are
  the only recovery path if the rewrite is later found to have dropped
  something. Anyone holding a stale clone will hit the divergence and can speak
  up within it.
- **Do not delete early.**

## Deletion, on or after 2026-09-18

```sh
for B in "/home/ubuntu/v2-048-pre-rewrite/globalstrat-plus-full-20260904T013929Z.bundle" \
         "/home/ubuntu/projects/globalstrat_backup/globalstrat-plus-20260904T011324Z.bundle"; do
  [ -n "$B" ] && [ -f "$B" ] || { echo "skip: $B"; continue; }
  shred -u "$B" && echo "shredded $B"
done
rmdir "/home/ubuntu/v2-048-pre-rewrite" 2>/dev/null || true
```

Guarded on each path being non-empty and a real file, and naming each file
explicitly rather than globbing — an empty variable in a globbed `rm` reaches
outside the intended directory, which is how this step goes wrong.

Verify afterwards that neither path exists, and that
`git log --all -S<credential>` in the working repository still returns zero.

## Already destroyed

Shredded 2026-09-04; none held recovery value.

- The `--replace-text` rule and the extracted literal used to drive the
  rewrite, both in the session scratchpad.
- **The config-rewrite drill's copies of three live secrets files.** Validating
  the rotation script's key-rewriting on copies meant copying
  `~/projects/BECSR/.becsr-secrets.env` and `~/.globalstrat-secrets.env` into
  the scratchpad. That file carries more than the database password, and a
  sweep found **three values still live**: `BECSR_SECRET_KEY`,
  `BECSR_JWT_SECRET_KEY` and `BECSR_CF_TOKEN`/`BECSR_CF_ZONE`. Only
  `BECSR_DB_PASSWORD` had been rotated since.

  The copies never left the host, stayed mode 0600 under the same owner as the
  originals, and are now shredded; a follow-up sweep of the whole session
  directory finds no live secret value. **Rotating those three is therefore a
  judgement call for the owner, not a necessity** — but it is recorded rather
  than left unsaid, because "the drill copied a live secrets file somewhere
  else" is exactly the kind of step that goes unmentioned.

  The lesson for the next drill: validate a rewrite against a *synthetic*
  fixture with the same key names, not against a copy of the real file. The
  database-password half of that drill did use a synthetic file; the other two
  did not.
