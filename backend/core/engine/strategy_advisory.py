"""
Strategy Advisory Framework — CC-35

Diagnoses team-specific strategic situations and maps them to navigation
strategies grounded in international business frameworks. The resulting
context is injected into briefing, coaching, coherence, and communication
evaluation prompts so the LLM references *this team's* actual challenges
rather than giving generic advice.

Usage:
    from core.engine.strategy_advisory import build_strategy_context
    context_text = build_strategy_context(team, game, round_number)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

logger = logging.getLogger(__name__)

D = Decimal


# ═══════════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Strategy:
    strategy_name: str
    description: str
    page_link: str
    estimated_impact: str
    framework_reference: str
    example: str


@dataclass
class DetectedSituation:
    situation_name: str
    severity: str  # 'info', 'warning', 'critical'
    summary: str
    details: dict = field(default_factory=dict)
    strategies: list = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# 1. ORIGIN TRUST GAP
# ═══════════════════════════════════════════════════════════════════════════

def detect_origin_trust_gap(team, game) -> Optional[DetectedSituation]:
    """Trigger: current_trust_multiplier < 0.85 in any foreign market."""
    from core.models.cc31_models import TeamMarketCompliance

    records = TeamMarketCompliance.objects.filter(
        game=game, team=team,
    ).select_related('market').exclude(market=team.home_market)

    affected = []
    for rec in records:
        trust = float(rec.current_trust_multiplier)
        if trust < 0.85:
            # Rough revenue impact: trust gap × market revenue
            from core.models.results_financials import RoundResultProductMarket
            mkt_rev = RoundResultProductMarket.objects.filter(
                game=game, team=team, round_number=game.current_round,
                market=rec.market,
            ).values_list('revenue', flat=True)
            rev = sum(float(r or 0) for r in mkt_rev)
            lost = rev * (1.0 - trust)
            affected.append({
                'market': rec.market.name,
                'trust': trust,
                'compliance_investment': float(rec.cumulative_investment),
                'revenue_impact': round(lost),
            })

    if not affected:
        return None

    worst = min(affected, key=lambda a: a['trust'])
    severity = 'critical' if worst['trust'] < 0.70 else 'warning'
    mkts = ', '.join(a['market'] for a in affected)
    total_lost = sum(a['revenue_impact'] for a in affected)

    return DetectedSituation(
        situation_name='Origin Trust Gap',
        severity=severity,
        summary=(
            f"Trust penalty in {mkts}. "
            f"Worst: {worst['market']} at {worst['trust']:.0%}. "
            f"Est. revenue impact: -${total_lost:,.0f}/round."
        ),
        details={'affected_markets': affected},
        strategies=[
            Strategy(
                strategy_name='Increase compliance investment',
                description=(
                    'Raise compliance spending in affected markets via '
                    'Market Strategy → Market Operations.'
                ),
                page_link='Market Strategy → Market Operations',
                estimated_impact='Each $1M invested erodes trust penalty by ~3% per round',
                framework_reference=(
                    'Institutional theory — legitimacy building through isomorphism'
                ),
                example='Haier invested $40M in US R&D centers before pushing the brand',
            ),
            Strategy(
                strategy_name='Establish Local Strategic Partner',
                description=(
                    'Partner with a local firm that lends credibility in the host market.'
                ),
                page_link='Market Strategy → Partnerships',
                estimated_impact='0.08-0.12 trust shield + 15-25% compliance acceleration',
                framework_reference=(
                    'Network theory — borrowed legitimacy from established local actors'
                ),
                example=(
                    'Huawei partnered with BT in the UK for network '
                    'infrastructure credibility'
                ),
            ),
            Strategy(
                strategy_name='Acquire with Brand Preservation',
                description=(
                    'Acquire a local company and retain its brand to cap the '
                    'trust penalty at ~8%.'
                ),
                page_link='Corporate Strategy → M&A',
                estimated_impact='Trust penalty capped at 8% under acquired brand',
                framework_reference=(
                    'Uppsala model — acquisition as accelerated market commitment'
                ),
                example=(
                    'Lenovo kept ThinkPad brand; Geely kept Volvo brand '
                    'and Swedish leadership'
                ),
            ),
            Strategy(
                strategy_name='Invest in technology sovereignty',
                description=(
                    'Move from licensed to in-house R&D to eliminate sanctions risk '
                    'and signal commitment.'
                ),
                page_link='R&D → In-House development',
                estimated_impact=(
                    '100% in-house = immune to sanctions + investor confidence signal'
                ),
                framework_reference=(
                    'Resource-based view — proprietary technology as inimitable resource'
                ),
                example="Huawei's HarmonyOS development after US restrictions",
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 2. CULTURAL DISTANCE PENALTY
# ═══════════════════════════════════════════════════════════════════════════

def detect_cultural_distance_penalty(team, game) -> Optional[DetectedSituation]:
    """Trigger: base_effectiveness < 0.75 in any foreign market presence."""
    from core.models.cc31_models import CulturalDistanceMatrix
    from core.models.team_state import TeamMarketPresence

    if not team.home_market:
        return None

    presences = TeamMarketPresence.objects.filter(
        team=team, status='active',
    ).exclude(market=team.home_market).select_related('market')

    affected = []
    for pres in presences:
        dist = CulturalDistanceMatrix.objects.filter(
            scenario=game.scenario,
            from_market=team.home_market,
            to_market=pres.market,
        ).first()
        if not dist:
            continue
        eff = float(dist.base_effectiveness)
        if eff < 0.75:
            affected.append({
                'market': pres.market.name,
                'distance_level': dist.distance_level,
                'base_effectiveness': eff,
                'effectiveness_gap': round(1.0 - eff, 2),
            })

    if not affected:
        return None

    worst = min(affected, key=lambda a: a['base_effectiveness'])
    severity = 'critical' if worst['base_effectiveness'] < 0.55 else 'warning'
    mkts = ', '.join(a['market'] for a in affected)

    return DetectedSituation(
        situation_name='Cultural Distance Penalty',
        severity=severity,
        summary=(
            f"High cultural distance in {mkts}. "
            f"Worst: {worst['market']} ({worst['distance_level']}, "
            f"effectiveness {worst['base_effectiveness']:.0%})."
        ),
        details={'affected_markets': affected},
        strategies=[
            Strategy(
                strategy_name='Increase local talent allocation',
                description=(
                    'Hire more local staff in affected markets to bridge '
                    'the cultural gap.'
                ),
                page_link='Corporate Strategy → Talent Allocation',
                estimated_impact=(
                    'Each additional local staff member improves effectiveness by ~3-5%'
                ),
                framework_reference=(
                    'CAGE distance framework — administrative and cultural distance '
                    'requires local bridging'
                ),
                example=(
                    'Xiaomi entered India with 95% local hiring and '
                    'built local supply chain'
                ),
            ),
            Strategy(
                strategy_name='Upgrade to Locally-Led operations',
                description=(
                    'Invest in sustained local talent development to reach 90%+ '
                    'effectiveness over 2-3 rounds.'
                ),
                page_link='Corporate Strategy → Talent Allocation',
                estimated_impact=(
                    '2-3 rounds to reach 90%+ effectiveness in distant markets'
                ),
                framework_reference=(
                    'Born-global theory vs Uppsala — staged commitment '
                    'with localization'
                ),
                example=(
                    "Haier's 'three-in-one' local strategy: local design, "
                    "local manufacturing, local sales"
                ),
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3. TECHNOLOGY SOVEREIGNTY RISK
# ═══════════════════════════════════════════════════════════════════════════

def detect_technology_sovereignty_risk(team, game) -> Optional[DetectedSituation]:
    """Trigger: licensed_dependency_pct > 0.30 on any active platform."""
    from core.models.team_state import TeamPlatform

    platforms = TeamPlatform.objects.filter(
        team=team, status='active',
    ).select_related('platform_generation')

    affected = []
    for plat in platforms:
        dep = float(plat.licensed_dependency_pct or 0)
        if dep > 0.30:
            affected.append({
                'platform': plat.name or plat.platform_generation.name,
                'dependency_pct': dep,
                'development_method': plat.development_method,
            })

    if not affected:
        return None

    worst = max(affected, key=lambda a: a['dependency_pct'])
    severity = 'critical' if worst['dependency_pct'] > 0.60 else 'warning'

    return DetectedSituation(
        situation_name='Technology Sovereignty Risk',
        severity=severity,
        summary=(
            f"Licensed technology dependency at "
            f"{worst['dependency_pct']:.0%} on {worst['platform']}. "
            f"Sanctions probability ~{worst['dependency_pct'] * 20:.0f}% per round."
        ),
        details={'affected_platforms': affected},
        strategies=[
            Strategy(
                strategy_name='Convert licensed features to in-house development',
                description=(
                    'Invest in R&D to replace licensed technology with '
                    'proprietary alternatives.'
                ),
                page_link='R&D → method selection',
                estimated_impact=(
                    'Reduces sanctions probability from ~12% to 0% per round'
                ),
                framework_reference=(
                    'Dynamic capabilities — building vs buying technological capability'
                ),
                example="SMIC's push for domestic chip fabrication capability",
            ),
            Strategy(
                strategy_name='Diversify technology sources across geographies',
                description=(
                    'Spread licensing across multiple partners to reduce '
                    'single-source risk.'
                ),
                page_link='R&D → Platform Development',
                estimated_impact=(
                    'Reduces single-source dependency concentration'
                ),
                framework_reference=(
                    'Real options theory — maintaining strategic flexibility'
                ),
                example=(
                    "Samsung's dual-sourcing strategy for critical components"
                ),
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4. GOVERNMENT FRICTION
# ═══════════════════════════════════════════════════════════════════════════

def detect_government_friction(team, game) -> Optional[DetectedSituation]:
    """Trigger: government_satisfaction < 0.50 (WARNING or RESTRICTED)."""
    from core.models.cc32f_models import GovernmentSatisfaction, GovernmentProfile

    records = GovernmentSatisfaction.objects.filter(
        game=game, team=team,
    ).select_related('market')

    affected = []
    for rec in records:
        sat = float(rec.satisfaction)
        if sat < 0.50:
            # Find weakest policy objective
            weakest_obj = None
            obj_scores = rec.objective_scores or {}
            if obj_scores:
                weakest_obj = min(obj_scores.items(), key=lambda x: x[1])

            profile = GovernmentProfile.objects.filter(
                scenario=game.scenario, market=rec.market,
            ).first()
            demands = []
            if profile and profile.policy_priorities:
                for p in profile.policy_priorities:
                    demands.append(p.get('objective', ''))

            affected.append({
                'market': rec.market.name,
                'satisfaction': sat,
                'status': rec.status,
                'weakest_objective': weakest_obj[0] if weakest_obj else None,
                'weakest_score': weakest_obj[1] if weakest_obj else None,
                'government_demands': demands[:3],
            })

    if not affected:
        return None

    worst = min(affected, key=lambda a: a['satisfaction'])
    severity = 'critical' if worst['status'] == 'RESTRICTED' else 'warning'
    mkts = ', '.join(a['market'] for a in affected)

    return DetectedSituation(
        situation_name='Government Friction',
        severity=severity,
        summary=(
            f"Government {worst['status']} in {mkts}. "
            f"Weakest area: {worst['weakest_objective'] or 'unknown'} "
            f"(satisfaction {worst['satisfaction']:.0%})."
        ),
        details={'affected_markets': affected},
        strategies=[
            Strategy(
                strategy_name='Align with government policy priorities',
                description=(
                    'Review the Government Relations tab and invest in the '
                    'policy areas where satisfaction is lowest.'
                ),
                page_link='Government Relations',
                estimated_impact=(
                    'Satisfaction above 0.70 unlocks incentives; '
                    'below 0.30 triggers restrictions'
                ),
                framework_reference=(
                    'Institutional theory — regulatory legitimacy through '
                    'policy alignment'
                ),
                example=(
                    "Tesla's Shanghai Gigafactory alignment with Chinese "
                    "industrial policy"
                ),
            ),
            Strategy(
                strategy_name='Increase local manufacturing investment',
                description=(
                    'Build or expand a plant in the affected market to signal '
                    'long-term commitment.'
                ),
                page_link='Market Strategy → Production',
                estimated_impact=(
                    'Plant ownership = strongest signal to government'
                ),
                framework_reference=(
                    'OLI paradigm — location advantages through direct investment'
                ),
                example=(
                    "TSMC's Arizona fab responding to US CHIPS Act incentives"
                ),
            ),
            Strategy(
                strategy_name='Pursue government procurement contracts',
                description=(
                    'Bid for public-sector contracts to build revenue and '
                    'relationship simultaneously.'
                ),
                page_link='Government Relations → Procurement',
                estimated_impact=(
                    'Direct revenue + relationship building + compliance signal'
                ),
                framework_reference=(
                    'Political economy — government as customer and regulator'
                ),
                example=(
                    "Huawei's early growth through government telecom contracts"
                ),
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 5. ALLIANCE STRAIN
# ═══════════════════════════════════════════════════════════════════════════

def detect_alliance_strain(team, game) -> Optional[DetectedSituation]:
    """Trigger: alliance satisfaction < 0.55 (STRAINED or worse)."""
    from core.models.cc32d_models import TeamAllianceState

    records = TeamAllianceState.objects.filter(
        game=game, team=team,
    ).select_related('partner_profile', 'market').exclude(status='DISSOLVED')

    affected = []
    for rec in records:
        sat = float(rec.satisfaction)
        if sat < 0.55:
            # Find weakest feature satisfaction
            feat_sat = rec.feature_satisfaction or {}
            weakest = min(feat_sat.items(), key=lambda x: x[1]) if feat_sat else (None, None)

            affected.append({
                'partner': rec.partner_profile.name,
                'market': rec.market.name,
                'satisfaction': sat,
                'status': rec.status,
                'weakest_feature': weakest[0],
                'weakest_score': weakest[1],
                'demands': rec.renegotiation_demands,
            })

    if not affected:
        return None

    worst = min(affected, key=lambda a: a['satisfaction'])
    severity = 'critical' if worst['status'] in ('DISSOLVING', 'RENEGOTIATING') else 'warning'
    partners = ', '.join(f"{a['partner']} ({a['market']})" for a in affected)

    return DetectedSituation(
        situation_name='Alliance Strain',
        severity=severity,
        summary=(
            f"Alliance {worst['status']} with {partners}. "
            f"Weakest dimension: {worst['weakest_feature'] or 'unknown'} "
            f"(satisfaction {worst['satisfaction']:.0%})."
        ),
        details={'affected_alliances': affected},
        strategies=[
            Strategy(
                strategy_name='Increase market investment where partner operates',
                description=(
                    'Boost commercial and operations spending in the '
                    "partner's market to demonstrate commitment."
                ),
                page_link='Market Strategy → Market Investment',
                estimated_impact=(
                    'Market investment is typically 25-30% of partner satisfaction'
                ),
                framework_reference=(
                    'Relational view — alliances require mutual value creation'
                ),
                example=(
                    'Renault-Nissan alliance health correlated with '
                    'shared investment levels'
                ),
            ),
            Strategy(
                strategy_name='Improve localization to demonstrate commitment',
                description=(
                    'Increase local staff count in the partner market to '
                    'signal long-term intent.'
                ),
                page_link='Corporate Strategy → Talent Allocation',
                estimated_impact=(
                    'Local staff signals long-term commitment to the partnership'
                ),
                framework_reference=(
                    'Transaction cost economics — credible commitment reduces '
                    'opportunism risk'
                ),
                example='',
            ),
            Strategy(
                strategy_name='Evaluate partnership vs subsidiary conversion',
                description=(
                    'If satisfaction is chronically low, direct ownership may '
                    'be more cost-effective than the strained alliance.'
                ),
                page_link='Corporate Strategy → M&A',
                estimated_impact=(
                    'If satisfaction is chronically low, direct ownership may '
                    'be more effective'
                ),
                framework_reference=(
                    'Internalization theory — when market-based governance fails, '
                    'hierarchical control'
                ),
                example='',
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 6. INVESTOR MISALIGNMENT
# ═══════════════════════════════════════════════════════════════════════════

def detect_investor_misalignment(team, game) -> Optional[DetectedSituation]:
    """Trigger: any AI fund selling for 2+ consecutive rounds."""
    from core.models.cc26_models import AIInvestorHolding, AIInvestorFund

    current_round = game.current_round
    if current_round < 2:
        return None

    funds = AIInvestorFund.objects.filter(scenario=game.scenario)
    affected = []

    for fund in funds:
        # Check last 2 rounds of action
        recent = AIInvestorHolding.objects.filter(
            game=game, team=team, fund=fund,
            round_number__in=[current_round, current_round - 1],
        ).order_by('round_number')

        sell_streak = sum(1 for h in recent if h.action == 'sell')
        if sell_streak >= 2:
            latest = recent.last()
            affected.append({
                'fund': fund.name,
                'philosophy': fund.investment_philosophy,
                'holding_pct': float(latest.holding_pct) if latest else 0,
                'concern': latest.trade_reason if latest else '',
                'consecutive_sells': sell_streak,
            })

    if not affected:
        return None

    fund_names = ', '.join(a['fund'] for a in affected)
    return DetectedSituation(
        situation_name='Investor Misalignment',
        severity='warning',
        summary=(
            f"{fund_names} selling for 2+ rounds. "
            f"Key concern: {affected[0].get('concern', 'performance below expectations')}."
        ),
        details={'affected_funds': affected},
        strategies=[
            Strategy(
                strategy_name='Address largest alignment gap',
                description=(
                    'Check the investor popover for each fund\'s preferences '
                    'and prioritize closing the biggest gap.'
                ),
                page_link='Dashboard → Investor Relations',
                estimated_impact=(
                    'Reversing a sell trend typically requires 2 rounds of '
                    'aligned decisions'
                ),
                framework_reference=(
                    'Agency theory — aligning management actions with '
                    'shareholder expectations'
                ),
                example='',
            ),
            Strategy(
                strategy_name='Match fund philosophy to strategy',
                description=(
                    'Growth funds want revenue growth and market expansion; '
                    'Value funds want margins and dividends; '
                    'ESG funds want sustainability investment.'
                ),
                page_link='Dashboard → Investor Relations',
                estimated_impact=(
                    'Aligned strategy can shift fund from sell → hold in 1-2 rounds'
                ),
                framework_reference=(
                    'Stakeholder theory — balancing diverse investor objectives'
                ),
                example='',
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 7. FINANCIAL DISTRESS RISK
# ═══════════════════════════════════════════════════════════════════════════

def detect_financial_distress_risk(team, game) -> Optional[DetectedSituation]:
    """Trigger: cash < 2 rounds of opex OR debt_to_equity > 1.5."""
    from core.models.results_financials import RoundResultFinancials

    fin = RoundResultFinancials.objects.filter(
        game=game, team=team, round_number=game.current_round,
    ).first()
    if not fin:
        return None

    cash = float(fin.cash_closing or 0)
    total_opex = float(
        (fin.rd_expense or 0)
        + (fin.marketing_expense or 0)
        + (fin.strategy_expense or 0)
        + (fin.admin_overhead or 0)
        + (fin.logistics_tariff_expense or 0)
    )
    d2e = float(fin.debt_to_equity or 0)
    interest = float(fin.interest_expense or 0)
    runway = cash / total_opex if total_opex > 0 else 999

    triggers = []
    if runway < 2.0:
        triggers.append(f"cash runway {runway:.1f} rounds")
    if d2e > 1.5:
        triggers.append(f"debt/equity {d2e:.2f}")

    if not triggers:
        return None

    severity = 'critical' if runway < 1.0 or d2e > 2.5 else 'warning'

    return DetectedSituation(
        situation_name='Financial Distress Risk',
        severity=severity,
        summary=(
            f"Financial stress: {'; '.join(triggers)}. "
            f"Cash: ${cash:,.0f}, interest burden: ${interest:,.0f}/round."
        ),
        details={
            'cash': cash,
            'runway_rounds': round(runway, 1),
            'debt_to_equity': d2e,
            'interest_expense': interest,
            'total_opex': total_opex,
        },
        strategies=[
            Strategy(
                strategy_name='Reduce cash burn',
                description='Identify and cut the largest discretionary cost centers.',
                page_link='Finance → Budget Allocation',
                estimated_impact='Immediate cash preservation',
                framework_reference=(
                    'Pecking order theory — financing hierarchy under distress'
                ),
                example=(
                    "Nokia's strategic retreat from multiple markets to "
                    "focus resources"
                ),
            ),
            Strategy(
                strategy_name='Divest underperforming markets',
                description=(
                    'Exit markets with the weakest revenue-to-cost ratio '
                    'to free cash and talent.'
                ),
                page_link='Market Strategy → Market Exit',
                estimated_impact=(
                    'Recovers invested capital and reduces ongoing costs'
                ),
                framework_reference=(
                    'Portfolio theory — divesting from negative-NPV positions'
                ),
                example='',
            ),
            Strategy(
                strategy_name='Issue equity if share price supports it',
                description=(
                    'Use equity financing to reduce debt burden if share '
                    'price is reasonable.'
                ),
                page_link='Finance',
                estimated_impact='Reduces interest expense and improves D/E ratio',
                framework_reference=(
                    'Modigliani-Miller with taxes — optimal capital structure'
                ),
                example='',
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 8. MARKET OVEREXTENSION
# ═══════════════════════════════════════════════════════════════════════════

def detect_market_overextension(team, game) -> Optional[DetectedSituation]:
    """
    Trigger: active markets > org structure optimal_market_range_max,
    OR thin talent (< 3 staff in any foreign market).
    """
    from core.models.team_state import TeamMarketPresence
    from core.models.cc32b_models import TeamOrganizationalStructure

    active_presences = TeamMarketPresence.objects.filter(
        team=team, status='active',
    ).select_related('market')
    active_count = active_presences.count()

    org = TeamOrganizationalStructure.objects.filter(
        game=game, team=team,
    ).select_related('current_structure').first()

    optimal_max = 5  # default
    structure_name = 'Unknown'
    penalty_per = 0
    if org and org.current_structure:
        optimal_max = org.current_structure.optimal_market_range_max
        structure_name = org.current_structure.name
        penalty_per = float(org.current_structure.overextension_effectiveness_penalty or 0)

    triggers = []
    details = {
        'active_markets': active_count,
        'optimal_max': optimal_max,
        'structure': structure_name,
    }

    if active_count > optimal_max:
        over_by = active_count - optimal_max
        triggers.append(
            f"{active_count} markets vs {optimal_max} max for {structure_name} "
            f"(–{penalty_per * 100:.0f}% effectiveness per extra market)"
        )
        details['overextended_by'] = over_by

    # Check for thin talent allocation per market
    from core.models.talent import TeamTalentState
    thin_markets = []
    for pres in active_presences:
        if pres.market == team.home_market:
            continue
        # Talent state is global not per-market in the current model,
        # so we check if total headcount / active markets < 3 per foreign market
        pass  # Talent is tracked globally; thin-market check uses market count

    # If total talent headcount / foreign markets < 3 per market → thin
    latest_round = game.current_round
    talent_records = TeamTalentState.objects.filter(
        team=team, round_number=latest_round,
    )
    total_headcount = sum(t.headcount for t in talent_records)
    foreign_markets = active_count - 1  # exclude home
    if foreign_markets > 0:
        per_market = total_headcount / foreign_markets
        if per_market < 3:
            triggers.append(
                f"Only {total_headcount} total staff across {foreign_markets} "
                f"foreign markets ({per_market:.1f} per market)"
            )
            details['headcount_per_foreign_market'] = round(per_market, 1)

    if not triggers:
        return None

    severity = 'critical' if active_count > optimal_max + 2 else 'warning'

    return DetectedSituation(
        situation_name='Market Overextension',
        severity=severity,
        summary='; '.join(triggers),
        details=details,
        strategies=[
            Strategy(
                strategy_name='Consider organizational restructure',
                description=(
                    f"Current {structure_name} structure optimized for "
                    f"≤{optimal_max} markets. A Regional or Matrix structure "
                    f"handles more markets efficiently."
                ),
                page_link='Corporate Strategy → Organization',
                estimated_impact=(
                    'Regional structure handles 5 markets; '
                    'Centralized breaks at 3'
                ),
                framework_reference=(
                    "Chandler's thesis — structure follows strategy"
                ),
                example='',
            ),
            Strategy(
                strategy_name='Consolidate to core markets',
                description=(
                    'Exit the weakest market to free budget and talent '
                    'for deeper investment elsewhere.'
                ),
                page_link='Market Strategy → Market Exit',
                estimated_impact=(
                    'Exiting weakest market frees budget + talent for '
                    'deeper investment elsewhere'
                ),
                framework_reference=(
                    'BCG portfolio matrix — divest dogs, invest in stars'
                ),
                example='',
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 9. ESG GAP
# ═══════════════════════════════════════════════════════════════════════════

def detect_esg_gap(team, game) -> Optional[DetectedSituation]:
    """
    Trigger: ESG cumulative investment < $1M AND operating in EU,
    OR governance commitments < 2 AND ESG-focused fund investing.
    """
    from core.models.cc24_models import ESGEconomicImpact
    from core.models.cc31_models import TeamGovernanceCommitment
    from core.models.team_state import TeamMarketPresence
    from core.models.cc26_models import AIInvestorFund

    # Check total ESG savings as proxy for investment level
    esg_impacts = ESGEconomicImpact.objects.filter(
        game=game, team=team,
    )
    total_esg_savings = sum(float(e.savings or 0) for e in esg_impacts)

    # Count active governance commitments
    active_commitments = TeamGovernanceCommitment.objects.filter(
        game=game, team=team, is_active=True,
    ).count()

    # Check if operating in EU (regulatory-heavy market)
    in_eu = TeamMarketPresence.objects.filter(
        team=team, status='active',
        market__code__in=['EU', 'eu'],
    ).exists()

    # Check if ESG fund exists and is selling
    esg_fund = AIInvestorFund.objects.filter(
        scenario=game.scenario, investment_philosophy='esg',
    ).first()
    esg_fund_selling = False
    if esg_fund:
        from core.models.cc26_models import AIInvestorHolding
        latest = AIInvestorHolding.objects.filter(
            game=game, team=team, fund=esg_fund,
            round_number=game.current_round,
        ).first()
        if latest and latest.action == 'sell':
            esg_fund_selling = True

    triggers = []
    if in_eu and active_commitments < 2:
        triggers.append(
            f"Operating in EU with only {active_commitments} governance commitments"
        )
    if esg_fund_selling and active_commitments < 2:
        triggers.append(
            f"ESG fund ({esg_fund.name}) selling; "
            f"only {active_commitments} commitments active"
        )

    if not triggers:
        return None

    return DetectedSituation(
        situation_name='ESG Gap',
        severity='warning',
        summary=(
            f"ESG underinvestment: {'; '.join(triggers)}. "
            f"Total ESG savings: ${total_esg_savings:,.0f}."
        ),
        details={
            'active_commitments': active_commitments,
            'total_esg_savings': total_esg_savings,
            'in_eu': in_eu,
            'esg_fund_selling': esg_fund_selling,
        },
        strategies=[
            Strategy(
                strategy_name='Adopt governance commitments',
                description=(
                    'Each commitment costs per round but signals ESG seriousness '
                    'to regulators and investors.'
                ),
                page_link='Corporate Strategy → ESG & Governance',
                estimated_impact=(
                    '2+ commitments typically satisfies ESG fund and EU regulatory expectations'
                ),
                framework_reference=(
                    'Stakeholder theory — ESG as multi-stakeholder value creation'
                ),
                example=(
                    "Northvolt's sustainability-first positioning earned EU subsidies"
                ),
            ),
            Strategy(
                strategy_name='Invest in sustainability features',
                description=(
                    'Increase R&D investment in sustainability-related platform features.'
                ),
                page_link='R&D → Feature Investment',
                estimated_impact=(
                    'Sustainability features boost ESG scores and reduce COGS via tariff benefits'
                ),
                framework_reference=(
                    'Porter hypothesis — environmental regulation as competitive advantage'
                ),
                example='',
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 10. COMPETITIVE PRESSURE
# ═══════════════════════════════════════════════════════════════════════════

def detect_competitive_pressure(team, game) -> Optional[DetectedSituation]:
    """
    Trigger: AI competitor fit improving in segments where team has >15% share.
    """
    from core.models.scenario import AICompetitorFitByRound, AICompetitorDefinition
    from core.models.results import RoundResultAdoption

    current_round = game.current_round
    if current_round < 2:
        return None

    # Find segments where team has significant share
    adoptions = RoundResultAdoption.objects.filter(
        game=game, team=team, round_number=current_round,
    ).select_related('segment', 'market')

    significant_segments = {}
    for a in adoptions:
        share = float(a.market_share or 0)
        if share > 0.15:
            key = (a.segment.id, a.market.id)
            significant_segments[key] = {
                'segment': a.segment,
                'market': a.market,
                'share': share,
            }

    if not significant_segments:
        return None

    # Check if any AI competitor fit is improving in those segments
    competitors = AICompetitorDefinition.objects.filter(scenario=game.scenario)
    threats = []

    for comp in competitors:
        for (seg_id, mkt_id), info in significant_segments.items():
            current_fit = AICompetitorFitByRound.objects.filter(
                ai_competitor=comp, segment_id=seg_id, market_id=mkt_id,
                round_number=current_round,
            ).first()
            prev_fit = AICompetitorFitByRound.objects.filter(
                ai_competitor=comp, segment_id=seg_id, market_id=mkt_id,
                round_number=current_round - 1,
            ).first()

            if current_fit and prev_fit:
                improvement = float(current_fit.fit_score) - float(prev_fit.fit_score)
                if improvement > 0.02:  # Meaningful improvement
                    threats.append({
                        'competitor': comp.name,
                        'segment': info['segment'].name,
                        'market': info['market'].name,
                        'team_share': info['share'],
                        'fit_improvement': round(improvement, 3),
                        'current_fit': float(current_fit.fit_score),
                    })

    if not threats:
        return None

    worst = max(threats, key=lambda t: t['fit_improvement'])
    severity = 'warning'

    threat_summary = '; '.join(
        f"{t['competitor']} gaining in {t['segment']}/{t['market']}"
        for t in threats[:3]
    )

    return DetectedSituation(
        situation_name='Competitive Pressure',
        severity=severity,
        summary=(
            f"AI competitors gaining ground: {threat_summary}. "
            f"Biggest threat: {worst['competitor']} "
            f"(fit +{worst['fit_improvement']:.1%} in {worst['segment']})."
        ),
        details={'threats': threats},
        strategies=[
            Strategy(
                strategy_name='Differentiate through feature investment',
                description=(
                    'Invest in the features that matter most to threatened segments '
                    'to widen the fit gap.'
                ),
                page_link='R&D → Feature Investment',
                estimated_impact=(
                    'Maintaining 2+ point feature lead typically preserves segment share'
                ),
                framework_reference=(
                    "Porter's differentiation strategy — sustainable competitive advantage"
                ),
                example='',
            ),
            Strategy(
                strategy_name='Defend with pricing and marketing',
                description=(
                    'Adjust pricing or increase marketing in threatened markets '
                    'to retain customer loyalty.'
                ),
                page_link='Market Strategy → Marketing & Pricing',
                estimated_impact=(
                    'Short-term share defense while R&D investments mature'
                ),
                framework_reference=(
                    'Game theory — competitive response strategy'
                ),
                example='',
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

# All 10 detector functions
_DETECTORS = [
    detect_origin_trust_gap,
    detect_cultural_distance_penalty,
    detect_technology_sovereignty_risk,
    detect_government_friction,
    detect_alliance_strain,
    detect_investor_misalignment,
    detect_financial_distress_risk,
    detect_market_overextension,
    detect_esg_gap,
    detect_competitive_pressure,
]


def run_all_detectors(team, game) -> List[DetectedSituation]:
    """Run all 10 situation detectors. Returns list of triggered situations."""
    situations = []
    for detector in _DETECTORS:
        try:
            result = detector(team, game)
            if result is not None:
                situations.append(result)
        except Exception as e:
            logger.warning(
                "Strategy detector %s failed for team %s: %s",
                detector.__name__, team.name, e,
            )
    # Sort: critical first, then warning, then info
    severity_order = {'critical': 0, 'warning': 1, 'info': 2}
    situations.sort(key=lambda s: severity_order.get(s.severity, 9))
    return situations


def build_strategy_context(team, game, round_number=None) -> str:
    """
    Build the strategy context string to inject into LLM prompts.

    Returns a formatted text block describing:
    - Active challenges (with quantified severity)
    - Recommended strategies (with framework references and examples)

    Returns empty string if no situations detected.
    """
    situations = run_all_detectors(team, game)
    if not situations:
        return ''

    lines = ['STRATEGIC CONTEXT FOR THIS TEAM:', '', 'ACTIVE CHALLENGES:']
    for i, sit in enumerate(situations, 1):
        icon = '🔴' if sit.severity == 'critical' else '🟡'
        lines.append(f"  {i}. {icon} {sit.situation_name}: {sit.summary}")

    lines.append('')
    lines.append('RECOMMENDED STRATEGIES:')

    for i, sit in enumerate(situations, 1):
        # Top 2 strategies per situation
        for strat in sit.strategies[:2]:
            lines.append(
                f"  {i}. For {sit.situation_name.lower()}: "
                f"{strat.description}"
            )
            if strat.estimated_impact:
                lines.append(f"     Impact: {strat.estimated_impact}")
            if strat.framework_reference:
                lines.append(f"     Framework: {strat.framework_reference}")
            if strat.example:
                lines.append(f"     Example: {strat.example}")

    lines.append('')
    lines.append(
        'INCORPORATE THESE INTO YOUR ANALYSIS. Reference the specific '
        'challenges and strategies in your briefing/evaluation.'
    )

    return '\n'.join(lines)
