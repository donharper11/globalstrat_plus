# Bilingual re-drive on the merged candidate — 2026-10-07

The one claim the ten-round pass could not carry over. That pass certified
`a0631e5d`, whose frontend built to `main.81b42bcc.js`; the repairs for V2-145,
V2-146 and V2-148 change frontend and backend files, so the merged tip builds
to `main.3ba3e3e1.js` and **the repaired screens had not been seen in a
browser**. This is that drive.

**Stack:** the merged tip `f62fc720` (confirmed from the running process's
`GIT_REVISION`), its own build, a disposable PostgreSQL
(`globalstrat_redrive`), `GLOBALSTRAT_ENV=production`, every LLM URL
unreachable. **A fresh database seeded from the merged scenario YAML**, which is
the point: the 150 translations only reach a game through `load_scenario`.

## The translations reached the database

| | loaded | carrying Chinese |
|---|---:|---:|
| Alliance-partner preferences | 105 | **105** |
| Memo evaluation criteria | 24 | **24** |
| Event templates | 38 | **38** |
| Governance amplifiers | 1 | **1** |

`instructor_setup` passed **28 of 28** — including the bulk-password step, which
was the single setup failure in the ten-round pass and is now polled rather than
read two seconds into a 10.57 s route.

## Every string the repairs targeted is gone

Measured by searching the leak scans of both passes for the exact strings.

| targeted | ten-round pass | merged tip |
|---|---|---|
| Government prose (V2-148) | **167 screens** | **gone** |
| Tax audit-risk sentence (V2-146) | 7 screens | gone |
| Alliance preference question (V2-145) | 4 screens | gone |
| Reasoning Analysis panel (V2-146) | 4 screens | gone |
| Event narrative (V2-145) | 1 screen | gone |

The FX-hedge panel, the export-credit panel and the memo criteria were never
reached by the earlier tour, so for those the repair rests on the serving tests
rather than on a screen. Said plainly rather than counted as a win.

## The aggregate metric did not move, and could not have

The pass reported *"4 leaky screens of 75 for an English reader, 74 of 75 for a
Chinese one"* and this report had promised to watch it. It came back **9 of 80
and 79 of 80** — essentially unchanged. **That metric was the wrong one**, and
the fault is this harness's, not the product's. It counts any screen carrying
any Latin text, and three things dominate it:

1. team, person and product names, which are legitimately Latin;
2. **an artifact of this harness** — one screenshot is taken *during* the
   in-game language switch and catches the English interface mid-replacement.
   28 of the flagged items come from that single screen;
3. content revealed for the first time by the every-tab sweep, on tabs no
   previous bilingual walkthrough had opened.

## What actually remains, adjudicated

Excluding proper nouns and the switch artifact: **37 distinct English items, in
five places.**

| screen | items | example |
|---|---:|---|
| Industry news | **17** | *"Euro weakening slightly against dollar"* |
| Financial Reports tabs | 12 | *"Export Contribution"*, *"Growth Fund"*, *"concerned about Governance Quality"* |
| Trade Finance | 4 | *"Cash in Advance"*, *"Letter of Credit"* |
| Sourcing | 3 | *"Camera Module"*, *"Final Assembly"* |
| Dashboard tabs | 1 | *"Classification Compliance / Product Safety"* |

**None is a regression.** They are the two classes already recorded as not
fixed: engine- or scenario-generated prose (V2-148's wider family — the news
headlines and investor-sentiment lines) and scenario-authored catalogue names in
tables that were not translated (components, trade-finance instruments,
compliance categories, government objective labels, investor fund names). The
value of this drive is that the remainder is now **37 items in five places**
rather than an unknown.
