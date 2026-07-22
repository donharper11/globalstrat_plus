# GSP-R1-04 Follow-Up — Finance Typing Fix Report

Date: 2026-07-22
Target: `https://globalstrat.camdani.com`
Live bundle proven: `static/js/main.ffcc7bb2.js`

## Issue

The GSP-R1-08 quick re-audit found that character-by-character typing into Finance budget fields could mangle normal student input. Typing `2000000` into Strategy Budget produced `$ 20` and could persist that tiny value.

## Fix

Updated `frontend/globalstrat-frontend/src/pages/FinancePage.js`:

- Replaced the budget allocation `InputNumber` controls with a local `MoneyTextInput` text control.
- Keeps draft typing local to the field so the Finance page does not re-render and interrupt keystrokes.
- Parses and commits money values on blur / Enter.
- Formats committed values back to currency after commit.
- Left the existing budget autosave path intact.

## Build And Deploy

- `npm run build` passed with pre-existing lint warnings.
- Deployed with `./frontend/deploy-frontend.sh`.
- Latest deploy backup: `/var/www/globalstrat-backup-20260722-120631`.
- Cloudflare purge skipped because `CF_TOKEN` is not set.

## Browser Proof

Ran live browser proof as `student1` on `/games/12/teams/18/decisions/finance`.

Proof result:

```json
{
  "initial": "$ 1,500,000",
  "focus1": { "value": "$ 1,500,000", "active": true, "start": 11, "end": 11 },
  "afterClear": "",
  "typedValueBeforeBlur": "2000000",
  "typedValueAfterBlur": "$ 2,000,000",
  "persistedTyped": "$ 2,000,000",
  "restored": "$ 1,500,000",
  "bad": []
}
```

Screenshot captured on verifier host:

- `/tmp/globalstrat-finance-type-moneyinput-proof.png`

## Data Safety

Student1 / team 18 Strategy Budget was temporarily changed to `$2,000,000` for proof and restored to `$1,500,000`, verified after reload. Net data change: none.

No game advance/process/reset/inject/delete/archive or lock/submit action was executed.
