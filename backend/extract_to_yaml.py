"""
Extract all scenario seed data from load_scenario.py to a YAML file.

Usage:
    cd backend
    DJANGO_SETTINGS_MODULE=globalstrat.settings python extract_to_yaml.py
"""
import os
import sys
from decimal import Decimal

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')
django.setup()

import yaml

from core.management.commands.load_scenario import (
    SCENARIO_DATA, CONFIGS, PLATFORM_FEATURES, MARKETING_FEATURES,
    STRATEGY_FEATURES, DERIVED_FEATURES, GENERATIONS, MARKETS,
    READINESS_DATA, CUSTOMER_SEGMENT_TEMPLATES, NON_CUSTOMER_SEGMENTS,
    AI_INVESTOR_FUNDS, TAX_STRUCTURES, ENTRY_MODES, STRATEGY_OPTIONS,
    EVENTS, AI_COMPETITORS, ACQUISITION_TARGETS, AI_BEHAVIORS,
    STARTER_PROFILES, MARKET_CONDITIONS, CULTURAL_DISTANCE_DATA,
    ORIGIN_TRUST_DATA, LOCAL_STRATEGIC_PARTNERS, ALLIANCE_PARTNER_PROFILES,
    GOVERNMENT_PROFILES, CC31C_CONFIGS, GOVERNANCE_COMMITMENT_TYPES,
    COMMUNICATION_ASSIGNMENTS, ORG_STRUCTURES,
    _build_segment_preferences,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def convert(obj):
    """Recursively convert Python objects for YAML serialization.

    - Decimal -> str (preserves exact representation)
    - tuple  -> list
    - dict keys that are tuples -> handled at call site
    """
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, tuple):
        return [convert(v) for v in obj]
    if isinstance(obj, list):
        return [convert(v) for v in obj]
    if isinstance(obj, dict):
        return {convert(k): convert(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# Build the output dict
# ---------------------------------------------------------------------------

output = {}

# --- scenario ---
output['scenario'] = convert(SCENARIO_DATA)

# --- config (merge CONFIGS + CC31C_CONFIGS) ---
merged_configs = {}
for key, (val, desc) in CONFIGS.items():
    merged_configs[key] = [val, desc]
for key, (val, desc) in CC31C_CONFIGS.items():
    merged_configs[key] = [val, desc]
output['config'] = convert(merged_configs)

# --- features ---
output['features'] = {
    'platform': convert(PLATFORM_FEATURES),
    'marketing': convert(MARKETING_FEATURES),
    'strategy': convert(STRATEGY_FEATURES),
    'derived': convert(DERIVED_FEATURES),
}

# --- platform_generations ---
gens_out = []
for g in GENERATIONS:
    gd = convert(g)
    gens_out.append(gd)
output['platform_generations'] = gens_out

# --- markets ---
output['markets'] = convert(MARKETS)

# --- readiness_data ---
readiness_out = []
for (mkt_code, gen_order), rounds in READINESS_DATA.items():
    readiness_out.append({
        'market': mkt_code,
        'generation': gen_order,
        'rounds': convert(rounds),
    })
output['readiness_data'] = readiness_out

# --- customer_segments ---
output['customer_segments'] = convert(CUSTOMER_SEGMENT_TEMPLATES)

# --- non_customer_segments ---
output['non_customer_segments'] = convert(NON_CUSTOMER_SEGMENTS)

# --- segment_preferences ---
prefs = _build_segment_preferences()
prefs_out = {}
for (seg_name, mkt_code), pref_list in prefs.items():
    mkt_key = mkt_code if mkt_code is not None else '__global__'
    if seg_name not in prefs_out:
        prefs_out[seg_name] = {}
    # Store as list of [feature_code, ideal, weight, tolerance]
    prefs_out[seg_name][mkt_key] = [
        [fc, round(ideal, 4), round(weight, 6), round(tol, 4)]
        for fc, ideal, weight, tol in pref_list
    ]
output['segment_preferences'] = prefs_out

# --- ai_investor_funds ---
output['ai_investor_funds'] = convert(AI_INVESTOR_FUNDS)

# --- tax_structures ---
output['tax_structures'] = convert(TAX_STRUCTURES)

# --- entry_modes ---
output['entry_modes'] = convert(ENTRY_MODES)

# --- strategy_options ---
strat_out = []
for so in STRATEGY_OPTIONS:
    sod = dict(so)
    # Convert effects tuples to lists: [feat_code, eff_type, eff_val, mkt_specific]
    sod['effects'] = [
        [fc, et, convert(ev), ms]
        for fc, et, ev, ms in so['effects']
    ]
    strat_out.append(convert(sod))
output['strategy_options'] = strat_out

# --- events ---
output['events'] = convert(EVENTS)

# --- ai_competitors ---
output['ai_competitors'] = convert(AI_COMPETITORS)

# --- ai_competitor_fit_data ---
market_affinity = {
    'TechVault Industries': {'NA': 0.25, 'APAC': 0.18, 'EU': 0.23, 'AFR': 0.12, 'LATAM': 0.16},
    'NovaStar Electronics': {'NA': 0.18, 'APAC': 0.25, 'EU': 0.20, 'AFR': 0.20, 'LATAM': 0.15},
}
segment_affinity = {
    'TechVault Industries': {
        'Value Seekers': -0.03, 'Premium Consumers': 0.05, 'Tech Enthusiasts': 0.02,
        'Enterprise & Institutional Buyers': 0.03, 'Sustainability-Conscious Buyers': 0.00,
    },
    'NovaStar Electronics': {
        'Value Seekers': 0.05, 'Premium Consumers': -0.03, 'Tech Enthusiasts': 0.03,
        'Enterprise & Institutional Buyers': 0.00, 'Sustainability-Conscious Buyers': -0.02,
    },
}
output['ai_competitor_fit_data'] = {
    'market_affinity': market_affinity,
    'segment_affinity': segment_affinity,
    'growth_per_round': 0.008,
    'fit_min': 0.15,
    'fit_max': 0.85,
}

# --- acquisition_targets ---
output['acquisition_targets'] = convert(ACQUISITION_TARGETS)

# --- ai_behaviors ---
output['ai_behaviors'] = convert(AI_BEHAVIORS)

# --- starter_profiles ---
output['starter_profiles'] = convert(STARTER_PROFILES)

# --- market_conditions ---
mc_out = {}
for mkt_code, conditions in MARKET_CONDITIONS.items():
    mc_out[mkt_code] = convert(conditions)
output['market_conditions'] = mc_out

# --- cultural_distance ---
output['cultural_distance'] = convert(CULTURAL_DISTANCE_DATA)

# --- origin_trust ---
output['origin_trust'] = convert(ORIGIN_TRUST_DATA)

# --- local_strategic_partners ---
output['local_strategic_partners'] = convert(LOCAL_STRATEGIC_PARTNERS)

# --- alliance_partner_profiles ---
output['alliance_partner_profiles'] = convert(ALLIANCE_PARTNER_PROFILES)

# --- government_profiles ---
output['government_profiles'] = convert(GOVERNMENT_PROFILES)

# --- governance_commitments ---
output['governance_commitments'] = convert(GOVERNANCE_COMMITMENT_TYPES)

# --- communication_assignments ---
output['communication_assignments'] = convert(COMMUNICATION_ASSIGNMENTS)

# --- org_structures ---
output['org_structures'] = convert(ORG_STRUCTURES)


# ---------------------------------------------------------------------------
# Write YAML
# ---------------------------------------------------------------------------

outpath = os.path.join(os.path.dirname(__file__), 'scenarios', 'consumer_electronics_2026.yaml')

# Custom representer: force long strings to use block scalar style
def str_representer(dumper, data):
    if '\n' in data or len(data) > 120:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_representer)

with open(outpath, 'w') as f:
    yaml.dump(output, f, default_flow_style=False, sort_keys=False, width=120, allow_unicode=True)

print(f"YAML written to {outpath}")
print(f"File size: {os.path.getsize(outpath):,} bytes")
