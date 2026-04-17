# Scenarios Directory

This directory contains YAML scenario definition files for GlobalStrat simulations. Each file fully specifies the industry setting, markets, features, segments, AI competitors, and all other data needed to run a simulation.

## Usage

Load a scenario with the `load_scenario` management command:

```bash
# Load from a specific YAML file
python manage.py load_scenario --file scenarios/consumer_electronics_2026.yaml --flush

# Load a built-in preset
python manage.py load_scenario --preset electronics --flush

# Limit to a subset of markets (useful for testing)
python manage.py load_scenario --file scenarios/consumer_electronics_2026.yaml --flush --markets 3
```

**Flags:**
- `--file` — Path to the scenario YAML file.
- `--preset` — Shorthand for a built-in scenario (e.g., `electronics`).
- `--flush` — Delete existing scenario data before loading.
- `--markets N` — Load only the first N markets defined in the YAML. Defaults to all.

## Creating a New Scenario

1. Copy an existing YAML file (e.g., `consumer_electronics_2026.yaml`) as a starting point.
2. Update the `scenario.name`, `scenario.industry_label`, and `scenario.description` fields.
3. Redefine features, markets, segments, and other sections to match the new industry.
4. Load it: `python manage.py load_scenario --file scenarios/your_scenario.yaml --flush`

## Required YAML Sections

A complete scenario file must include these top-level keys:

| Section | Purpose |
|---|---|
| `scenario` | Name, description, round count, starting cash, limits |
| `config` | Tuning parameters (Bass model coefficients, cost rates, UI labels, etc.) |
| `features` | Technology/product feature definitions with level ranges |
| `platform_generations` | Platform generation unlock rules and feature ceilings |
| `markets` | Market definitions (size, growth, tariffs, regions) |
| `readiness_data` | Per-market readiness scores by round |
| `customer_segments` | Customer segment definitions per market |
| `non_customer_segments` | Non-customer stakeholder segments (investors, regulators, etc.) |
| `segment_preferences` | Feature preferences and weights per segment |
| `entry_modes` | Market entry mode options (export, JV, subsidiary, etc.) |
| `strategy_options` | Strategic decision options and their effects |
| `events` | Event templates, impacts, and response options |
| `market_conditions` | Per-market economic conditions by round |
| `ai_competitors` | AI competitor definitions and per-round fit data |
| `ai_behaviors` | AI competitor behavioral patterns |
| `ai_investor_funds` | AI investor fund profiles and preferences |
| `starter_profiles` | Starting firm configurations (platforms, products, cash) |
| `cultural_distance` | Cultural distance matrix between regions |
| `origin_trust` | Origin-based trust modifiers per market |
| `alliance_partner_profiles` | Strategic alliance partner definitions |
| `government_profiles` | Government profiles per market |
| `governance_commitments` | Governance commitment type definitions |
| `tax_structures` | Tax structure type definitions |
| `org_structures` | Organizational structure type definitions |
| `communication_assignments` | Communication channel assignments |
| `local_strategic_partners` | Local partner profiles per market |
| `acquisition_targets` | Acquisition target company profiles |

## Feature Naming Conventions

Feature codes in the YAML should use lowercase `snake_case` (e.g., `battery_life`, `display_quality`, `ai_processing`). These codes are referenced throughout segment preferences, platform ceilings, and R&D configurations, so they must be consistent across all sections.

Abstract features (used by non-customer segments like investors and regulators) are defined in the loader itself and do not appear in the `features` section. Examples: `rd_intensity`, `revenue_growth`, `esg_composite`, `sustainability_level`.
