# GSP-R1-12 — Vertex Anomaly Resolution and Fresh-Game Readiness

Date: 2026-08-23  
Branch: `main` at `18d3fc6`  
Verification game: #19, Round 1

## Root cause

Game #17 confirms that Vertex Electronics had two valid North America marketing decisions but no customs-classification decision. Deterministic compliance enforcement selected Vertex for a North America customs event and froze that team-market for Round 1. Revenue correctly honored the freeze, so Vertex produced no `RoundResultProductMarket` rows and booked zero revenue.

The defect was downstream inconsistency: before GSP-R1-10, Bass adoption still awarded customer adoption/adjusted-fit credit to a frozen team-market. The old PI calculation then allowed that invalid fit credit to outweigh the financial failure and rank Vertex first. GSP-R1-10 (`434980c`) gates adoption/adjusted fit on compliance freezes; GSP-R1-11 (`979dc86`) uses a market/financial-aware five-component PI and penalizes active-market freezes.

## Regression proof

`CC18ComplianceTest` contains regression coverage for:

- customs documents preventing customs enforcement;
- compliance freezes blocking revenue;
- compliance freezes blocking customer adoption/adjusted-fit credit;
- the composite PI rewarding financial performance and penalizing active-market freezes.

Command:

```bash
python3 manage.py test core.tests.test_cc18_compliance.CC18ComplianceTest --verbosity=2 --keepdb
```

Result: 9 tests passed. `python3 manage.py check` also passed.

## Fresh-game Round 1 verification

Created game #19 with `python3 manage.py setup_test_game` without `--flush`. Seeded the same conservative, known-valid Round 1 decision pattern for four synthetic students and explicitly saved North America customs classifications for all four teams. Every submission passed `DecisionLockView._full_validate`; all four were locked. Round 1 processing completed in 6.1 seconds.

| Rank | Team | Starter profile | Product-market rows | Revenue | Net income | PI |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 1 | Solaris Consumer | Innovator | 2 | $13,184,400.00 | $5,796,299.52 | 59.54 |
| 2 | Zenith Hardware | Brand Builder | 2 | $17,864,400.00 | $9,951,383.52 | 59.52 |
| 3 | Helix Digital | Workhorse (Vertex-equivalent) | 2 | $13,184,400.00 | $6,293,999.52 | 58.75 |
| 4 | Cipher Systems | Green Pioneer | 2 | $13,184,400.00 | $6,317,699.52 | 58.37 |

All teams had three nonzero adoption rows and zero compliance events. The Workhorse/Vertex-equivalent team produced IronClad X and IronClad Field product-market rows with $13.18M total revenue. No zero-revenue/high-PI anomaly recurred. Zenith's second-place PI is intelligible despite leading revenue because the documented composite also includes strategic capability, stakeholder confidence, and resilience; the score difference from first is 0.02.

Round state after processing: `processed` / `RESULTS_AVAILABLE`, current round remains 1, and lock count remains 4/4.

## Browser and service verification

The locally served production frontend bundle (`main.e6fdf1c6.js`) was exercised against the production backend for all four live student accounts. Each account rendered dashboard, leaderboard, and financial reports with `R1 of 10 RESULTS AVAILABLE`. No page was shell-only or stuck loading. No page exception or API 5xx occurred.

The instructor Game Control rendered game #19, `4 of 4 teams have locked decisions`, Round 1 `processed`, latest processed results round 1, and results ready. The only suppressed browser probe request was Google Fonts, which is unreachable from the VM's sandboxed Chromium and is unrelated to application/API behavior.

Health proof:

- `curl -I https://globalstrat.camdani.com` → HTTP/2 200.
- `globalstrat-backend` → active.
- `globalstrat-frpc` → active.

## Acceptance result

- Vertex root cause documented: PASS.
- Vertex-equivalent produces product-market rows and nonzero revenue: PASS.
- Zero-revenue team cannot retain invalid adoption credit/high ranking: PASS by regression tests and controlled game proof.
- Four students validate and lock: PASS (4/4).
- Processing and result persistence: PASS.
- Student and instructor result surfaces: PASS.
- No 5xx, shell-only pages, indefinite spinners, or unhandled exceptions: PASS in the controlled browser pass.
- Live-rehearsal protocol: delivered at `handoffs_v3/round1-live-rehearsal-protocol.md`.
- Platform-owner approval: PENDING manual owner sign-off.

Verdict: technical Round 1 readiness is PASS; operational sign-off is pending platform-owner approval of the rehearsal protocol.
