"""
Progressive-disclosure helper (CC-04 Amendment A1 §4.1).

Every SC write serializer that enforces progressive disclosure calls
`get_effective_unlock_round` rather than hardcoding `if round < N:` checks.
The helper consults `ClassProgressiveDisclosureOverride` for the field+game
and falls back to the CC-2 §8 baseline schedule declared here.
"""
from core.models.overrides import ClassProgressiveDisclosureOverride


# CC-2 §8 baseline unlock rounds, keyed by dot-notation field path.
# A field not listed here is treated as always-available (round 1).
DEFAULT_UNLOCK_ROUNDS = {
    # Round 3 unlocks
    'sourcing.multi_sourcing_strategy': 3,
    'logistics.modal_mix': 3,
    'inventory.buffer_inventory': 3,
    'inventory.buffer_days': 3,
    'inventory.safety_stock_trigger_pct': 3,

    # Round 4 unlocks
    'sourcing.payment_terms': 4,
    'logistics.incoterms': 4,
    'logistics.insurance_coverage_pct': 4,
    'trade_finance.buyer_payment_instrument': 4,
    'trade_finance.lc_doc_prep_investment': 4,
    'trade_finance.sinosure_coverage': 4,
    'esg.supplier_audit': 4,
    'esg.scope_3': 4,

    # Round 5 unlocks
    'sourcing.tier_2_3_visibility_investment': 5,
    'sourcing.volume_commitments': 5,
    'logistics.customs_classification': 5,
    'logistics.reverse_logistics': 5,
    'logistics.volume_commitment_teu': 5,
    'trade_finance.fx_hedging': 5,
    'inventory.contingency_plans': 5,
    'esg.cbam_readiness': 5,
    'esg.uflpa_tier_mapping': 5,
    'plants.scope_emissions_visibility': 5,
    'plants.reverse_logistics_enabled': 5,
}


def get_effective_unlock_round(game, field_path, default_unlock_round=None):
    """
    Return the effective unlock round for `field_path` in `game`.

    Consults the override table first; falls back to the CC-2 §8 default
    (either the argument or the registry entry). Returns 1 if no default is
    supplied and the field is not in the registry — interpreted as "always
    available."
    """
    override = ClassProgressiveDisclosureOverride.objects.filter(
        game=game, field_path=field_path,
    ).first()
    if override:
        return override.override_unlock_round
    if default_unlock_round is not None:
        return default_unlock_round
    return DEFAULT_UNLOCK_ROUNDS.get(field_path, 1)


def is_known_field_path(field_path):
    """True if `field_path` appears in the CC-2 §8 registry."""
    return field_path in DEFAULT_UNLOCK_ROUNDS
