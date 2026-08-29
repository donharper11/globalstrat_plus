"""Fifteen targeted candidates, one per mechanism worth attacking.

Random discovery found nothing that beats competent play against competent
opponents -- 0 of 50, best -0.43 -- so the tournament is aimed rather than
sampled. Each candidate below names the mechanism it attacks, and several
attack findings this handoff already raised, so a regression in a closed
finding shows up here as a strategy that suddenly pays.

Financing genes are deliberately outside `search_body.GENES`. The preserved
discovery batch was drawn without them, and adding them to the random genome
would make that evidence describe a different search space than the one it
sampled. Targeted candidates set them explicitly; everything else leaves them
at zero, which is what the baseline plays.
"""

# The three strongest random candidates against the competent population,
# copied verbatim from stage3-discovery-batch.json rather than regenerated, so
# the tournament carries the discovery result forward instead of re-deriving it.
DISCOVERY_44 = {
    'commercial_headcount': 34, 'distribution_investment': 1725266.3656,
    'environmental_investment': 1883403.2779, 'marketing_budget': 3172761.8185,
    'operations_headcount': 29, 'price_multiplier': 0.9787,
    'promotion_multiplier': 2.2691, 'rd_budget': 5322672.1564,
    'rd_headcount': 12, 'research_budget': 1277259.4026, 'sales_team_count': 1,
    'social_investment': 482313.3842, 'strategy_budget': 2513818.3707,
    'volume_multiplier': 1.6137,
}
DISCOVERY_31 = {
    'commercial_headcount': 59, 'distribution_investment': 264034.6396,
    'environmental_investment': 338708.5285, 'marketing_budget': 3021531.0959,
    'operations_headcount': 117, 'price_multiplier': 0.9214,
    'promotion_multiplier': 2.0087, 'rd_budget': 5550976.8663,
    'rd_headcount': 135, 'research_budget': 352273.6048, 'sales_team_count': 10,
    'social_investment': 171170.4156, 'strategy_budget': 2756278.394,
    'volume_multiplier': 1.5059,
}
DISCOVERY_15 = {
    'commercial_headcount': 128, 'distribution_investment': 1087454.3611,
    'environmental_investment': 1812346.9365, 'marketing_budget': 2212510.2122,
    'operations_headcount': 17, 'price_multiplier': 1.0074,
    'promotion_multiplier': 0.6171, 'rd_budget': 9463492.6872,
    'rd_headcount': 68, 'research_budget': 1471468.4062, 'sales_team_count': 5,
    'social_investment': 1872014.3051, 'strategy_budget': 670116.2538,
    'volume_multiplier': 1.9,
}

# The documented baseline, as a genome, so families can vary one thing from it.
NEUTRAL = {
    'price_multiplier': 1.0, 'volume_multiplier': 1.0,
    'promotion_multiplier': 1.0, 'rd_budget': 2_000_000.0,
    'marketing_budget': 3_000_000.0, 'strategy_budget': 1_000_000.0,
    'research_budget': 500_000.0, 'distribution_investment': 200_000.0,
    'sales_team_count': 10, 'rd_headcount': 50, 'commercial_headcount': 30,
    'operations_headcount': 40, 'environmental_investment': 0.0,
    'social_investment': 0.0,
}


def _from(base, **overrides):
    genome = dict(base)
    genome.update(overrides)
    return genome


CANDIDATES = [
    # --- strongest random discovery -------------------------------------
    {'name': 'discovery-44', 'family': 'random discovery',
     'attacks': 'the best random candidate against competent opponents',
     'genome': DISCOVERY_44},
    {'name': 'discovery-31', 'family': 'random discovery',
     'attacks': 'second best random candidate, heavy talent and R&D',
     'genome': DISCOVERY_31},
    {'name': 'discovery-15', 'family': 'random discovery',
     'attacks': 'third best random candidate, maximal R&D spend',
     'genome': DISCOVERY_15},

    # --- high but bounded pricing (V2-023) ------------------------------
    # 1.5x the reference is exactly the price-fit clamp point; 2.38x sits well
    # above it, where the old rule left revenue scaling with price unopposed.
    {'name': 'price-at-clamp', 'family': 'high-but-bounded pricing',
     'attacks': 'V2-023: price exactly at the price-fit clamp point',
     'genome': _from(NEUTRAL, price_multiplier=1.5)},
    {'name': 'price-above-clamp', 'family': 'high-but-bounded pricing',
     'attacks': 'V2-023: price far above the clamp, where fit is a constant '
                'zero and only the elasticity opposes revenue',
     'genome': _from(NEUTRAL, price_multiplier=2.38, volume_multiplier=1.5)},
    {'name': 'price-above-clamp-lean', 'family': 'high-but-bounded pricing',
     'attacks': 'V2-023 with costs stripped out, so any residual pricing gain '
                'is not hidden by spend',
     'genome': _from(NEUTRAL, price_multiplier=2.38, volume_multiplier=0.5,
                     promotion_multiplier=0.0, marketing_budget=0.0,
                     rd_budget=0.0, strategy_budget=0.0, research_budget=0.0,
                     distribution_investment=0.0)},

    # --- low-cost versus meaningful R&D (V2-021) ------------------------
    {'name': 'rd-starved', 'family': 'low-cost vs meaningful R&D',
     'attacks': 'V2-021: spending nothing on R&D, which the old rule scored '
                'as full credit whenever the declared budget was also nothing',
     'genome': _from(NEUTRAL, rd_budget=0.0, rd_headcount=0,
                     research_budget=0.0)},
    {'name': 'rd-at-target', 'family': 'low-cost vs meaningful R&D',
     'attacks': 'V2-021: spending exactly the scenario target, the point of '
                'full capability credit',
     'genome': _from(NEUTRAL, rd_budget=2_000_000.0)},
    {'name': 'rd-saturated', 'family': 'low-cost vs meaningful R&D',
     'attacks': 'V2-021: spending far past the target, to show the score is '
                'clamped and the overspend is wasted',
     'genome': _from(NEUTRAL, rd_budget=10_000_000.0, research_budget=3_000_000.0)},

    # --- minimal commercial activity (V2-022) ---------------------------
    {'name': 'commercially-inactive', 'family': 'minimal commercial activity',
     'attacks': 'V2-022: produce nothing, sell nothing, spend nothing, and '
                'see whether inactivity outscores competing',
     'genome': _from(NEUTRAL, volume_multiplier=0.0, promotion_multiplier=0.0,
                     marketing_budget=0.0, rd_budget=0.0, strategy_budget=0.0,
                     research_budget=0.0, distribution_investment=0.0,
                     sales_team_count=0, rd_headcount=0,
                     commercial_headcount=0, operations_headcount=0)},
    {'name': 'near-inactive', 'family': 'minimal commercial activity',
     'attacks': 'V2-022: just enough revenue to clear the material-revenue '
                'floor, which is where the cap stops applying',
     'genome': _from(NEUTRAL, volume_multiplier=0.05, promotion_multiplier=0.0,
                     marketing_budget=0.0, distribution_investment=0.0,
                     sales_team_count=0)},

    # --- financing and equity (V2-020, V2-024) --------------------------
    # The first tournament ran `equity-raise` ($20,000,000 unfunded) and
    # `equity-and-dividend`. Both are now rejected outright by the V2-024
    # funding-need rule, so neither is a legal payload and neither can form an
    # opponent population. Their refusal is already evidence
    # (`v2-024-recheck.json`); what needs testing under the final rules is
    # whether financing still pays when it is used legally.
    {'name': 'equity-at-legal-max', 'family': 'financing and equity',
     'attacks': 'V2-024: raise the largest equity the funding rule permits, to '
                'show the residual advantage of legal issuance is not free',
     'genome': _from(NEUTRAL, _equity_at_max=True,
                     environmental_investment=2_000_000.0)},
    {'name': 'debt-funded-scale', 'family': 'financing and equity',
     'attacks': 'borrow and convert the cash straight into volume',
     'genome': _from(NEUTRAL, new_debt=30_000_000.0, volume_multiplier=2.5,
                     promotion_multiplier=2.0)},
    {'name': 'dividend-payout', 'family': 'financing and equity',
     'attacks': 'pay a dividend out of opening cash, with no equity raise '
                'behind it -- the legal remainder of the V2-024 loop',
     'genome': _from(NEUTRAL, dividend_per_share=5.0)},

    # --- cost-minimising talent and ESG ---------------------------------
    {'name': 'skeleton-crew', 'family': 'cost-minimising talent and ESG',
     'attacks': 'strip headcount and ESG to nothing and keep selling, to see '
                'whether the composite notices',
     'genome': _from(NEUTRAL, rd_headcount=0, commercial_headcount=0,
                     operations_headcount=0, environmental_investment=0.0,
                     social_investment=0.0, strategy_budget=0.0)},
]

FINANCING_GENES = ('new_debt', 'new_equity', 'dividend_per_share')
