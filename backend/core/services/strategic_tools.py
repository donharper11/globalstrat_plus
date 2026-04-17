"""
Strategic Analysis Tools Service
Generates contextual PESTLE, SWOT, Porter's 5 Forces, and 4Ps analyses
based on a team's actual game state.
"""
from decimal import Decimal

from core.models import (
    TeamIncomeStatement, TeamPerformance,
    # TODO: GlobalStrat — update to use new scenario models (CC-3)
    # Removed: Scenario, Segment, SegmentPreference, Feature
    Program, ProgramType, ProgramPortfolio, ProgramFeature,
    PestleAnalysis,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _f(val):
    """Safely convert Decimal/None to float."""
    if val is None:
        return 0.0
    return float(val)


def _get_scenario(scenario_id):
    # TODO: GlobalStrat — update to use new scenario models (CC-3)
    # Scenario model removed — returning placeholder
    return {'scenario_id': scenario_id, 'scenario_name': 'Unknown'}


def _get_latest_esg(team_id):
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # ESGScorecard model deleted — return zeroes
    # esg = ESGScorecard.objects.filter(team_id=team_id).order_by('-round_number').first()
    # if esg:
    #     return {
    #         'E': esg.environmental_score or 0,
    #         'S': esg.social_score or 0,
    #         'G': esg.governance_score or 0,
    #     }
    return {'E': 0, 'S': 0, 'G': 0}


def _get_latest_financials(team_id):
    inc = TeamIncomeStatement.objects.filter(team_id=team_id).order_by('-round_id').first()
    if inc:
        return {
            'revenue': _f(inc.revenue),
            'program_expenses': _f(inc.program_expenses),
            'operating_costs': _f(inc.operating_costs),
        }
    return {'revenue': 0, 'program_expenses': 0, 'operating_costs': 0}


def _get_team_performance(team_id):
    perf = TeamPerformance.objects.filter(team_id=team_id).first()
    if perf:
        return {
            'avg_stakeholder_satisfaction': _f(perf.average_stakeholder_satisfaction),
            'total_score': _f(perf.total_score) if hasattr(perf, 'total_score') else 0,
        }
    return {'avg_stakeholder_satisfaction': 0, 'total_score': 0}


def _get_competitors():
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Competitor model deleted
    # return list(Competitor.objects.all().values(
    #     'competitor_id', 'name', 'description', 'total_esg_score', 'esg_priority',
    # ))
    return []


def _get_active_programs(team_id, scenario_id=None):
    """Get active programs, optionally filtered by economy via program_type."""
    qs = Program.objects.filter(team_id=team_id, status='Active')
    if scenario_id:
        type_ids = ProgramType.objects.filter(
            scenario_id=scenario_id
        ).values_list('program_type_id', flat=True)
        qs = qs.filter(program_type_id__in=type_ids)
    return list(qs)


def _get_program_type_map():
    return {pt.program_type_id: pt.program_type_name for pt in ProgramType.objects.all()}


def _competitor_avg_esg():
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Competitor model deleted
    # comps = Competitor.objects.all()
    # if not comps.exists():
    #     return 0
    # total = sum(_f(c.total_esg_score) for c in comps)
    # return total / comps.count()
    return 0


# ---------------------------------------------------------------------------
# Scenario-specific context strings
# ---------------------------------------------------------------------------

SCENARIO_CONTEXT = {
    1: {
        'Political': 'Standard regulatory oversight with moderate government intervention in corporate affairs.',
        'Economic': 'Competitive consumer market with traditional supply-demand dynamics and cost-sensitive buyers.',
        'Social': 'Growing consumer awareness of sustainability, but price still dominates purchasing decisions.',
        'Technological': 'Mature technology ecosystem with incremental innovation cycles.',
        'Legal': 'Established compliance frameworks with evolving ESG disclosure requirements.',
        'Environmental': 'Increasing pressure for carbon reduction but enforcement remains gradual.',
    },
    2: {
        'Political': 'Strict regulatory environment with elevated government scrutiny of corporate ESG practices.',
        'Economic': 'Principle-driven market where stakeholders reward genuine ESG commitment over lowest cost.',
        'Social': 'Highly conscious consumer base; ethical sourcing and labor practices are market differentiators.',
        'Technological': 'Resource scarcity drives innovation in circular economy and sustainable manufacturing.',
        'Legal': 'Stringent compliance requirements with significant penalties for ESG violations.',
        'Environmental': 'Elevated environmental pressure with mandatory carbon reporting and e-waste targets.',
    },
}


# ---------------------------------------------------------------------------
# PESTLE Analysis
# ---------------------------------------------------------------------------

def analyze_pestle(team_id, scenario_id):
    esg = _get_latest_esg(team_id)
    economy = _get_scenario(scenario_id)
    pestle_rows = PestleAnalysis.objects.all()

    # Map PESTLE categories to ESG pillars for relevance scoring
    pillar_map = {
        'Political': 'G', 'Legal': 'G',
        'Economic': 'G', 'Social': 'S',
        'Technological': 'E', 'Environmental': 'E',
    }

    categories = {}
    for row in pestle_rows:
        cat = row.category or 'Other'
        if cat not in categories:
            ctx = SCENARIO_CONTEXT.get(scenario_id, {}).get(cat, '')
            categories[cat] = {
                'category': cat,
                'economy_context': ctx,
                'factors': [],
            }

        pillar = pillar_map.get(cat, 'G')
        score = esg.get(pillar, 0)
        if score < 40:
            relevance = 'high'
        elif score < 65:
            relevance = 'medium'
        else:
            relevance = 'low'

        categories[cat]['factors'].append({
            'factor_description': row.factor_description,
            'potential_impact': row.potential_impact,
            'mitigation_strategy': row.mitigation_strategy,
            'relevance': relevance,
        })

    return {
        'tool': 'pestle',
        'economy': economy,
        'team_esg': esg,
        'categories': list(categories.values()),
    }


# ---------------------------------------------------------------------------
# SWOT Analysis
# ---------------------------------------------------------------------------

def analyze_swot(team_id, scenario_id):
    esg = _get_latest_esg(team_id)
    financials = _get_latest_financials(team_id)
    performance = _get_team_performance(team_id)
    competitors = _get_competitors()
    programs = _get_active_programs(team_id, scenario_id)
    type_map = _get_program_type_map()
    economy = _get_scenario(scenario_id)
    benchmark = _competitor_avg_esg()

    team_total_esg = esg['E'] + esg['S'] + esg['G']
    net_income = financials['revenue'] - financials['program_expenses'] - financials['operating_costs']
    satisfaction = performance['avg_stakeholder_satisfaction']
    program_types = set(p.program_type_id for p in programs)

    strengths = []
    weaknesses = []
    opportunities = []
    threats = []

    # --- Strengths ---
    for pillar, label in [('E', 'Environmental'), ('S', 'Social'), ('G', 'Governance')]:
        if benchmark > 0 and esg[pillar] > (benchmark / 3) + 10:
            strengths.append({
                'finding': f'Strong {label} performance',
                'metric': f'{esg[pillar]} vs {benchmark / 3:.0f} avg benchmark',
                'source': 'ESG',
            })

    if net_income > 0:
        strengths.append({
            'finding': 'Profitable operations',
            'metric': f'Net income: ${net_income:,.0f}',
            'source': 'Financial',
        })

    if satisfaction >= 0.60:
        strengths.append({
            'finding': 'Strong stakeholder relationships',
            'metric': f'{satisfaction:.0%} satisfaction',
            'source': 'Stakeholders',
        })

    if len(program_types) >= 3:
        strengths.append({
            'finding': 'Diversified Program portfolio',
            'metric': f'{len(program_types)} program types active',
            'source': 'Programs',
        })

    # --- Weaknesses ---
    for pillar, label in [('E', 'Environmental'), ('S', 'Social'), ('G', 'Governance')]:
        if benchmark > 0 and esg[pillar] < (benchmark / 3) - 10:
            weaknesses.append({
                'finding': f'Weak {label} performance',
                'metric': f'{esg[pillar]} vs {benchmark / 3:.0f} avg benchmark',
                'source': 'ESG',
            })

    if net_income < 0:
        weaknesses.append({
            'finding': 'Financial pressure from Program investments',
            'metric': f'Net loss: ${abs(net_income):,.0f}',
            'source': 'Financial',
        })

    if 0 < satisfaction < 0.40:
        weaknesses.append({
            'finding': 'Poor stakeholder engagement',
            'metric': f'{satisfaction:.0%} satisfaction',
            'source': 'Stakeholders',
        })

    if len(programs) < 2:
        weaknesses.append({
            'finding': 'Limited Program program coverage',
            'metric': f'{len(programs)} active program(s)',
            'source': 'Programs',
        })

    if esg['G'] < 40:
        weaknesses.append({
            'finding': 'Ongoing governance credibility concerns',
            'metric': f'Governance score: {esg["G"]}',
            'source': 'ESG',
        })

    # --- Opportunities ---
    if scenario_id == 1:
        opportunities.append({
            'finding': 'Growing consumer awareness of sustainability',
            'metric': '', 'source': 'Market',
        })
        opportunities.append({
            'finding': 'Partnership potential with NGOs and local communities',
            'metric': '', 'source': 'Market',
        })
    elif scenario_id == 2:
        opportunities.append({
            'finding': 'Principle-driven market rewards genuine ESG commitment',
            'metric': '', 'source': 'Market',
        })
        opportunities.append({
            'finding': 'Early-mover advantage with S-4 adopters',
            'metric': '', 'source': 'Market',
        })

    if benchmark > 0 and team_total_esg > benchmark:
        opportunities.append({
            'finding': 'Position as industry sustainability leader',
            'metric': f'Team ESG {team_total_esg} vs {benchmark:.0f} industry avg',
            'source': 'Competitive',
        })

    # --- Threats ---
    stronger_comps = [c for c in competitors if _f(c['total_esg_score']) > team_total_esg]
    if stronger_comps:
        top = max(stronger_comps, key=lambda c: _f(c['total_esg_score']))
        threats.append({
            'finding': f'Competitor "{top["name"]}" outperforms on ESG',
            'metric': f'Their ESG: {_f(top["total_esg_score"]):.0f} vs yours: {team_total_esg}',
            'source': 'Competitive',
        })

    if scenario_id == 2:
        threats.append({
            'finding': 'Strict regulatory environment increases compliance costs',
            'metric': '', 'source': 'Regulatory',
        })

    if esg['G'] < 50:
        threats.append({
            'finding': 'Continued reputational risk from governance scandals',
            'metric': f'Governance: {esg["G"]}', 'source': 'Reputation',
        })

    threats.append({
        'finding': 'Shifting stakeholder preferences across rounds',
        'metric': '', 'source': 'Market',
    })

    # Ensure at least one item per quadrant for early-game teams
    if not strengths:
        strengths.append({
            'finding': 'Launch Program programs to build strengths',
            'metric': 'No data yet', 'source': 'Guidance',
        })
    if not weaknesses:
        weaknesses.append({
            'finding': 'Maintain balanced ESG performance',
            'metric': '', 'source': 'Guidance',
        })

    return {
        'tool': 'swot',
        'economy': economy,
        'team_esg': esg,
        'strengths': strengths,
        'weaknesses': weaknesses,
        'opportunities': opportunities,
        'threats': threats,
    }


# ---------------------------------------------------------------------------
# Porter's 5 Forces
# ---------------------------------------------------------------------------

def analyze_porters(team_id, scenario_id):
    esg = _get_latest_esg(team_id)
    team_total_esg = esg['E'] + esg['S'] + esg['G']
    competitors = _get_competitors()
    economy = _get_scenario(scenario_id)
    programs = _get_active_programs(team_id, scenario_id)
    type_map = _get_program_type_map()
    program_types_used = set(p.program_type_id for p in programs)
    # TODO: GlobalStrat — update to use new scenario models (CC-3)
    # Segment model removed — using placeholder count
    stakeholder_count = 0

    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # ProgramResource / ResourceType models deleted
    # resource_types_used = set()
    # for p in programs:
    #     rids = ProgramResource.objects.filter(
    #         program_id=p.program_id
    #     ).values_list('resource_type_id', flat=True)
    #     resource_types_used.update(rids)
    # total_resource_types = ResourceType.objects.count()
    resource_types_used = set()
    total_resource_types = 0

    total_program_types = ProgramType.objects.filter(scenario_id=scenario_id).count()

    forces = []

    # 1. Competitive Rivalry
    comp_count = len(competitors)
    if comp_count == 0:
        rivalry_score = 3
    else:
        close_comps = [c for c in competitors
                       if abs(_f(c['total_esg_score']) - team_total_esg) < 20]
        rivalry_score = min(10, 3 + comp_count + len(close_comps))

    forces.append({
        'force': 'Competitive Rivalry',
        'rating': 'high' if rivalry_score >= 7 else ('medium' if rivalry_score >= 4 else 'low'),
        'score': rivalry_score,
        'analysis': (
            f'{comp_count} AI competitors in the market. '
            f'{len([c for c in competitors if _f(c["total_esg_score"]) > team_total_esg])} '
            f'currently outperform your total ESG score of {team_total_esg}.'
        ),
        'implications': 'Differentiate through targeted stakeholder engagement and unique program features.',
    })

    # 2. Threat of New Entrants
    if scenario_id == 2:
        entrant_score = 3
        entrant_analysis = 'High regulatory barriers in the Arkanis System discourage new entrants.'
    else:
        entrant_score = 6
        entrant_analysis = 'Moderate barriers in the Traditional Market. New players can enter with lower ESG requirements.'

    if len(program_types_used) >= 3:
        entrant_score = max(1, entrant_score - 2)
        entrant_analysis += ' Your diversified portfolio raises the bar for newcomers.'

    forces.append({
        'force': 'Threat of New Entrants',
        'rating': 'high' if entrant_score >= 7 else ('medium' if entrant_score >= 4 else 'low'),
        'score': entrant_score,
        'analysis': entrant_analysis,
        'implications': 'Build switching costs through strong stakeholder relationships and ESG leadership.',
    })

    # 3. Bargaining Power of Buyers (Stakeholders)
    buyer_score = 5
    if stakeholder_count >= 6:
        buyer_score += 2
    performance = _get_team_performance(team_id)
    sat = performance['avg_stakeholder_satisfaction']
    if sat > 0 and sat < 0.50:
        buyer_score += 2
    elif sat >= 0.70:
        buyer_score = max(1, buyer_score - 2)

    forces.append({
        'force': 'Bargaining Power of Buyers',
        'rating': 'high' if buyer_score >= 7 else ('medium' if buyer_score >= 4 else 'low'),
        'score': min(10, buyer_score),
        'analysis': (
            f'{stakeholder_count} stakeholder groups in this economy with diverse preferences. '
            f'Your satisfaction rate: {sat:.0%}.'
        ),
        'implications': 'Align programs closely with stakeholder preferences to reduce their power to switch.',
    })

    # 4. Bargaining Power of Suppliers
    if total_resource_types > 0:
        coverage = len(resource_types_used) / total_resource_types
    else:
        coverage = 0
    supplier_score = int(7 - coverage * 4)
    supplier_score = max(1, min(10, supplier_score))

    forces.append({
        'force': 'Bargaining Power of Suppliers',
        'rating': 'high' if supplier_score >= 7 else ('medium' if supplier_score >= 4 else 'low'),
        'score': supplier_score,
        'analysis': (
            f'Using {len(resource_types_used)} of {total_resource_types} available resource types. '
            f'{"Limited" if coverage < 0.5 else "Broad"} resource diversification.'
        ),
        'implications': 'Diversify resource usage across programs to reduce dependency on any single supplier.',
    })

    # 5. Threat of Substitutes
    if total_program_types > 0:
        type_coverage = len(program_types_used) / total_program_types
    else:
        type_coverage = 0
    substitute_score = int(8 - type_coverage * 5)
    if scenario_id == 2:
        substitute_score = max(1, substitute_score - 2)

    forces.append({
        'force': 'Threat of Substitutes',
        'rating': 'high' if substitute_score >= 7 else ('medium' if substitute_score >= 4 else 'low'),
        'score': max(1, min(10, substitute_score)),
        'analysis': (
            f'Covering {len(program_types_used)} of {total_program_types} program types in this economy. '
            f'Gaps leave room for competitors to offer alternative Program approaches.'
        ),
        'implications': 'Expand program type coverage to close gaps competitors could exploit.',
    })

    return {
        'tool': 'porters',
        'economy': economy,
        'team_esg': esg,
        'forces': forces,
    }


# ---------------------------------------------------------------------------
# 4Ps Marketing Mix
# ---------------------------------------------------------------------------

def analyze_4ps(team_id, scenario_id):
    economy = _get_scenario(scenario_id)
    esg = _get_latest_esg(team_id)
    financials = _get_latest_financials(team_id)
    programs = _get_active_programs(team_id, scenario_id)
    type_map = _get_program_type_map()

    program_ids = [p.program_id for p in programs]

    # --- PRODUCT ---
    product_programs = []
    for p in programs:
        portfolios = ProgramPortfolio.objects.filter(
            program_id=p.program_id, status='Active'
        ).values_list('program_portfolio_id', flat=True)

        features = ProgramFeature.objects.filter(
            program_portfolio_id__in=portfolios
        ).select_related()

        # TODO: GlobalStrat — update to use new scenario models (CC-3)
        # Feature model removed — using feature_id as placeholder name
        feature_list = []
        for pf in features:
            feature_list.append({
                'feature_name': f"Feature {pf.feature_id}",
                'value': _f(pf.feature_value),
                'min': 0.0,
                'max': 0.0,
            })

        product_programs.append({
            'program_name': p.program_name,
            'program_type': type_map.get(p.program_type_id, 'Unknown'),
            'features': feature_list,
        })

    type_dist = {}
    for p in programs:
        tname = type_map.get(p.program_type_id, 'Unknown')
        type_dist[tname] = type_dist.get(tname, 0) + 1

    # --- PRICE ---
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # ProgramImplementationCost model deleted — use zero cost
    total_cost = 0
    program_costs = []
    for p in programs:
        # cost_row = ProgramImplementationCost.objects.filter(
        #     program_id=p.program_id
        # ).order_by('-round_id').first()
        # cost = _f(cost_row.implementation_cost) if cost_row else 0
        cost = 0
        total_cost += cost
        program_costs.append({
            'program_name': p.program_name,
            'cost': cost,
        })

    revenue = financials['revenue']
    cost_efficiency = (revenue / total_cost) if total_cost > 0 else 0

    # --- PLACE ---
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # ProgramGeography / GeographyFocus models deleted
    # geo_data = ProgramGeography.objects.filter(program_id__in=program_ids)
    # geo_ids_used = set(g.focus_id for g in geo_data if g.focus_id)
    # all_geos = {g.focus_id: g.focus_area_name for g in GeographyFocus.objects.all()}
    # current_coverage = [all_geos.get(gid, f'Area {gid}') for gid in geo_ids_used]
    # underserved = [name for gid, name in all_geos.items() if gid not in geo_ids_used]
    current_coverage = []
    underserved = []

    economy_note = (
        'Traditional Market: broad geographic reach may capture diverse customer segments.'
        if scenario_id == 1
        else 'Arkanis System: targeted geographic focus may be more effective in this principle-driven market.'
    )

    # --- PROMOTION ---
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # ProgramMedia / MediaType / StakeholderMediaPref models deleted
    # media_data = ProgramMedia.objects.filter(program_id__in=program_ids)
    # all_media = {m.media_type_id: m.media_type_name for m in MediaType.objects.all()}
    # media_mix = {}
    # for m in media_data:
    #     name = all_media.get(m.media_type_id, f'Media {m.media_type_id}')
    #     media_mix[name] = media_mix.get(name, 0) + _f(m.budget_allocated)
    # total_media_budget = sum(media_mix.values())
    # ...
    media_mix = {}
    total_media_budget = 0
    missing_media = []

    # Ensure results are meaningful even with no programs
    if not programs:
        return {
            'tool': '4ps',
            'economy': economy,
            'team_esg': esg,
            'no_data': True,
            'message': 'Launch Program programs to generate a 4Ps marketing mix analysis.',
            'product': {'programs': [], 'program_type_distribution': {}, 'feature_count': 0},
            'price': {'total_cost': 0, 'total_revenue': 0, 'cost_efficiency': 0, 'program_costs': []},
            'place': {'current_coverage': [], 'underserved_areas': [], 'economy_note': economy_note},
            'promotion': {'media_mix': {}, 'missing_channels': [], 'total_budget': 0},
        }

    return {
        'tool': '4ps',
        'economy': economy,
        'team_esg': esg,
        'product': {
            'programs': product_programs,
            'program_type_distribution': type_dist,
            'feature_count': sum(len(pp['features']) for pp in product_programs),
        },
        'price': {
            'total_cost': total_cost,
            'total_revenue': revenue,
            'cost_efficiency': round(cost_efficiency, 2),
            'program_costs': program_costs,
        },
        'place': {
            'current_coverage': current_coverage,
            'underserved_areas': underserved,
            'economy_note': economy_note,
        },
        'promotion': {
            'media_mix': media_mix,
            'missing_channels': missing_media,
            'total_budget': total_media_budget,
        },
    }


# ---------------------------------------------------------------------------
# Triple Bottom Line (TBL)
# ---------------------------------------------------------------------------

def analyze_tbl(team_id, scenario_id):
    economy = _get_scenario(scenario_id)
    esg = _get_latest_esg(team_id)
    financials = _get_latest_financials(team_id)
    performance = _get_team_performance(team_id)
    competitors = _get_competitors()
    programs = _get_active_programs(team_id, scenario_id)
    type_map = _get_program_type_map()
    benchmark = _competitor_avg_esg()

    revenue = financials['revenue']
    program_expenses = financials['program_expenses']
    operating_costs = financials['operating_costs']
    net_income = revenue - program_expenses - operating_costs
    satisfaction = performance['avg_stakeholder_satisfaction']

    # Cumulative revenue for profit trend
    from django.db.models import Sum
    cum_rev = TeamIncomeStatement.objects.filter(
        team_id=team_id
    ).aggregate(total=Sum('revenue'))
    cumulative_revenue = _f(cum_rev['total'])

    cum_csr = TeamIncomeStatement.objects.filter(
        team_id=team_id
    ).aggregate(total=Sum('program_expenses'))
    cumulative_csr = _f(cum_csr['total'])

    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # ESGScorecard deleted — no historical ESG data
    # esg_history = list(
    #     ESGScorecard.objects.filter(team_id=team_id)
    #     .order_by('round_number')
    #     .values('round_number', 'environmental_score', 'social_score', 'governance_score')
    # )
    esg_history = []

    # Program breakdown by ESG pillar (program_types 1=E, 2=S, 3=G)
    pillar_programs = {'Environmental': [], 'Social': [], 'Governance': []}
    pillar_type_map = {1: 'Environmental', 2: 'Social', 3: 'Governance'}
    for p in programs:
        pillar = pillar_type_map.get(p.program_type_id)
        if pillar:
            pillar_programs[pillar].append(p.program_name)
        else:
            # Operational types (4-9) map back through feature_esg_mapping
            # For TBL summary, group under the type name
            tname = type_map.get(p.program_type_id, 'Other')
            # Add to whichever pillar has the weakest score as "supporting"
            weakest = min(pillar_programs.keys(), key=lambda k: esg.get(k[0], 0))
            pillar_programs[weakest].append(f'{p.program_name} ({tname})')

    # --- PEOPLE (Social) ---
    people_score = esg['S']
    people_benchmark = benchmark / 3 if benchmark > 0 else 0
    people_insights = []

    if people_score >= 70:
        people_insights.append('Strong social performance — your programs are effectively addressing stakeholder needs.')
    elif people_score >= 40:
        people_insights.append('Moderate social performance — room to strengthen employee welfare and community engagement.')
    elif people_score > 0:
        people_insights.append('Social performance needs attention — consider programs targeting employee training, fair labor, or community investment.')
    else:
        people_insights.append('No social score yet — launch Social-type programs to build your People bottom line.')

    if satisfaction >= 0.60:
        people_insights.append(f'Segment satisfaction is healthy at {satisfaction:.0%}.')
    elif satisfaction > 0:
        people_insights.append(f'Segment satisfaction at {satisfaction:.0%} — engagement strategies need strengthening.')

    if pillar_programs['Social']:
        people_insights.append(f'Active social programs: {", ".join(pillar_programs["Social"])}.')

    # --- PLANET (Environmental) ---
    planet_score = esg['E']
    planet_benchmark = benchmark / 3 if benchmark > 0 else 0
    planet_insights = []

    if planet_score >= 70:
        planet_insights.append('Strong environmental stewardship — your carbon and resource management are effective.')
    elif planet_score >= 40:
        planet_insights.append('Moderate environmental performance — consider strengthening recycling, emissions, or sustainable sourcing initiatives.')
    elif planet_score > 0:
        planet_insights.append('Environmental performance is lagging — invest in programs addressing carbon footprint, e-waste, or sustainable materials.')
    else:
        planet_insights.append('No environmental score yet — launch Environmental-type programs to build your Planet bottom line.')

    if scenario_id == 2:
        planet_insights.append('The Arkanis System has elevated environmental expectations — environmental leadership is a market differentiator here.')

    if pillar_programs['Environmental']:
        planet_insights.append(f'Active environmental programs: {", ".join(pillar_programs["Environmental"])}.')

    # --- PROFIT (Financial) ---
    profit_insights = []

    if revenue > 0 and net_income > 0:
        margin = (net_income / revenue) * 100
        profit_insights.append(f'Profitable operations with {margin:.1f}% net margin.')
    elif revenue > 0:
        profit_insights.append(f'Generating revenue (${revenue:,.0f}) but Program investments (${program_expenses:,.0f}) exceed returns — balance spending with stakeholder adoption.')
    else:
        profit_insights.append('No revenue yet — as stakeholder adoption grows through effective programs, revenue will follow.')

    if cumulative_revenue > 0:
        csr_ratio = (cumulative_csr / cumulative_revenue) * 100 if cumulative_revenue > 0 else 0
        profit_insights.append(f'Cumulative Program investment ratio: {csr_ratio:.1f}% of revenue.')

    if esg['G'] >= 50:
        profit_insights.append(f'Governance score of {esg["G"]} supports investor confidence and sustainable profitability.')
    elif esg['G'] > 0:
        profit_insights.append(f'Governance score of {esg["G"]} — strengthening governance will improve investor trust and long-term financial stability.')

    # --- Overall TBL Assessment ---
    scores = [people_score, planet_score, esg['G']]
    total = sum(scores)
    balance = max(scores) - min(scores) if any(s > 0 for s in scores) else 0

    if balance <= 15 and total >= 150:
        overall = 'Excellent — strong and balanced across all three bottom lines.'
    elif balance <= 15:
        overall = 'Balanced but developing — maintain equilibrium as you grow each pillar.'
    elif total >= 150:
        overall = 'Strong overall but imbalanced — address the weaker pillar to achieve sustainable performance.'
    elif total > 0:
        overall = 'Developing — focus on building each bottom line while maintaining balance across People, Planet, and Profit.'
    else:
        overall = 'Launch programs across Environmental, Social, and Governance types to begin building your Triple Bottom Line.'

    return {
        'tool': 'tbl',
        'economy': economy,
        'team_esg': esg,
        'people': {
            'score': people_score,
            'benchmark': round(people_benchmark, 1),
            'program_count': len(pillar_programs['Social']),
            'programs': pillar_programs['Social'],
            'insights': people_insights,
        },
        'planet': {
            'score': planet_score,
            'benchmark': round(planet_benchmark, 1),
            'program_count': len(pillar_programs['Environmental']),
            'programs': pillar_programs['Environmental'],
            'insights': planet_insights,
        },
        'profit': {
            'revenue': revenue,
            'program_expenses': program_expenses,
            'operating_costs': operating_costs,
            'net_income': net_income,
            'cumulative_revenue': cumulative_revenue,
            'governance_score': esg['G'],
            'governance_benchmark': round(people_benchmark, 1),
            'insights': profit_insights,
        },
        'overall': {
            'total_score': total,
            'balance_gap': balance,
            'assessment': overall,
        },
        'esg_history': esg_history,
    }


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

TOOL_FUNCTIONS = {
    'pestle': analyze_pestle,
    'swot': analyze_swot,
    'porters': analyze_porters,
    '4ps': analyze_4ps,
    'tbl': analyze_tbl,
}


def run_analysis(team_id, scenario_id, tool):
    """Main entry point. Returns dict or raises ValueError."""
    func = TOOL_FUNCTIONS.get(tool)
    if not func:
        raise ValueError(f'Unknown tool: {tool}. Valid options: {", ".join(TOOL_FUNCTIONS.keys())}')
    return func(team_id, scenario_id)
