# Starter-profile definition and assignment — inventory

**Task:** GSP-CRV2-11 Stage 2 / ruling **R28** (competition owner, 2026-09-12) — every
firm in a heat must begin from a distinct position, at the R12 cap of 8 firms.
**Branch:** `crv2-11-distinct-starter-profiles`, cut from `crv2-release-integration`
at `46b4bbe`, in an isolated worktree.
**Built from:** the scenario YAML sections, the Django model registry
(`core/models/scenario.py`) and the two registered game-creation entry points —
not by grepping for the helper the fix is expected to call.

**This inventory is committed before any authoring**, as the handoff requires. It
records the behaviour as found. Nothing below is a proposal.

---

## 1. Where a starter profile is authored

Each shipped scenario carries one top-level `starter_profiles:` list:

| scenario | line | profiles authored |
|---|---:|---:|
| `backend/scenarios/consumer_electronics_2026.yaml` | 5487 | **4** |
| `backend/scenarios/clean_energy_tech_2026.yaml` | 4814 | **4** |
| `backend/scenarios/media_entertainment_2026.yaml` | 4822 | **4** |

Every scenario authors **four**. The R12 cap is **eight firms per game**.

A profile entry carries `profile_name`, `profile_name_zh`, `description`,
`description_zh`, `home_market` (a market code), `starting_cash`,
`starting_debt`, `starting_revenue`, a `platforms:` mapping of platform label →
`{feature_code: level}`, and a `products:` list. Each product row is a 6- or
7-element sequence:

```
[product_name, positioning, base_price, market_code, unit_volume, market_share_pct, platform_label?]
```

`platform_label` defaults to `alpha` when the 7th element is absent.

## 2. What the loader creates

`backend/core/management/commands/load_scenario.py:1014-1057` maps one YAML
entry onto three models:

| model | rows per profile | notes |
|---|---|---|
| `FirmStarterProfile` | 1 | `home_market` FK, `starting_cash`, `starting_debt`, `starting_revenue` |
| `FirmStarterPlatformConfig` | one per `platform_label` × feature | `unique_together = (profile, platform_label, feature)`; **every row is attached to generation 1** (`gen_objs.get(1)`), regardless of label |
| `FirmStarterProduct` | one per product row | `positioning_label`, `base_price`, `market` FK, `unit_volume`, `market_share_pct`, `platform_label` |

All twelve shipped profiles author exactly **5 features under `alpha` and 5
under `beta`**, and exactly **2 products**. `max_platform_features` is 5 in all
three scenarios (`core/services/rd_costs.py:573`), so the authored alpha block
is exactly at the cap.

## 3. How a profile is assigned to a team

There are **two** registered game-creation paths. Both select the profile with
the same expression:

| entry point | line | expression |
|---|---:|---|
| `core/management/commands/initialize_game.py` (CLI) | **112** | `profile = profiles[i % len(profiles)]` |
| `core/views/scenario_views.py` (instructor API) | **325** | `profile = profiles[i % len(profiles)]` |

In both, `profiles` is built as:

```python
profiles = list(FirmStarterProfile.objects.filter(scenario=scenario))
```

with **no `.order_by()`**. The team-index → profile mapping therefore rests on
unordered database return order. In practice a freshly loaded scenario returns
insertion (primary-key) order, but nothing pins it.

## 4. The repeat behaviour — this is the defect R28 names

For a game of `N` teams against `P` authored profiles, team index `i` (0-based)
receives `profiles[i mod P]`. Nothing checks whether `N > P`; no warning, no log
line and no error is produced when profiles run out and the list wraps.

At the R12 cap of **8 firms** against the **4** authored profiles, every
scenario produces four duplicate pairs:

| team index | profile | duplicate of |
|---:|---|---|
| 0 | profile 1 | — |
| 1 | profile 2 | — |
| 2 | profile 3 | — |
| 3 | profile 4 | — |
| **4** | **profile 1** | **team 0** |
| **5** | **profile 2** | **team 1** |
| **6** | **profile 3** | **team 2** |
| **7** | **profile 4** | **team 3** |

**What a duplicate pair shares.** The two teams point at the *same*
`FirmStarterProfile` row, so they are identical in every authored respect:

* same `home_market`, `starting_cash`, `starting_debt`, `starting_revenue`
  (and therefore the same opening `total_equity` and share price);
* the same `TeamPlatformFeatureLevel` set, built from the same
  `FirmStarterPlatformConfig` rows — identical feature levels;
* the same product names, the same `positioning`, the same authored
  `base_price`, `unit_volume` and `market_share_pct`, in the same market;
* consequently the same round-0 revenue, COGS, net income, market share and
  segment adoption apportionment.

**What differs between a duplicate pair:** the team's display name — drawn from
`_get_company_names()` (`core/views/scenario_views.py:41-56`), which calls
`random.shuffle` with no seed — and its primary key. Nothing else.

So in an 8-firm heat two teams do not merely begin *similarly*; they begin from
a byte-identical authored position and differ only in what they are called.

## 5. Round-zero parity is not what is broken

`core/engine/bootstrap.py` writes, for every team unconditionally:

* `RoundResultPerformanceIndex.index_value = scenario.performance_index_base`
  (`bootstrap.py:449`) — 55.00 in all three scenarios;
* `LeaderboardEntry.rank = 1` for every team whose index equals that base
  (`bootstrap.py:531`), so round 0 is joint-first for the whole field.

Duplication therefore does **not** break R22's parity rule. It breaks
*distinctness*: R22 requires equal score and **unequal position**, and a
duplicate pair has equal score and **equal** position.

## 6. A second, pre-existing divergence between the two paths

The two entry points do not build the same starting state from the same
authored data:

| | `initialize_game.py` (CLI) | `scenario_views.py` (instructor API) |
|---|---|---|
| platform configs read | **`platform_label='alpha'` only** (`:148-151`) | every distinct label (`:349-356`) |
| `TeamPlatform` rows created | **one** | **one per label** (`alpha`, `beta`) |
| product → platform | every product attached to the single platform (`:172-177`) | attached to its own `platform_label` (`:399-404`) |
| other platform features | not created | created at level 0 (`:386-392`) |

All twelve shipped profiles author a `beta` block, and every profile's second
product names `beta`. So on the CLI path the authored `beta` platform and
`FirmStarterProduct.platform_label` are **read but never used** — both of a
team's products sit on the alpha platform and are scored on alpha's feature
levels.

This is outside R28's scope and is **recorded, not repaired**: it changes what
a game starts from depending on which path created it, and it is the owning
handoff's to rule on.

## 7. Related drift noticed while building this inventory

`core/management/commands/verify_scenario_schema.py:30` declares
`firm_starter_platform_config` unique on `('firm_starter_profile_id',
'feature_id')`, while the model (`core/models/scenario.py:543`) declares
`('firm_starter_profile', 'platform_label', 'feature')`. The schema verifier's
expectation predates the dual-platform format. Recorded only.

## 8. Inventory rows and their disposition

| row | disposition under this task |
|---|---|
| `starter_profiles:` × 3 scenarios, 4 entries each | **changed** — authored up to 8 per scenario |
| `FirmStarterProfile` / `FirmStarterPlatformConfig` / `FirmStarterProduct` models | **unchanged** — data only, no migration |
| `initialize_game.py:112` wrap-around | **unchanged** — with 8 profiles and ≤8 teams it no longer repeats; the modulo itself is engine code and out of scope |
| `scenario_views.py:325` wrap-around | **unchanged**, same reason |
| unordered `profiles` queryset | **not changed** — engine code; reported as a finding |
| alpha/beta divergence between the two paths | **not changed** — reported as a finding |
| `verify_scenario_schema.py` unique-key drift | **not changed** — reported as a finding |
| `bootstrap.py` round-0 index and rank | **unchanged** — parity already holds and must keep holding |
