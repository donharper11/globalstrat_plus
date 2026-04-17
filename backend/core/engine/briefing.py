"""
CC-27: Strategic Briefing Generation Engine.

Generates personalized strategic briefings for each team after round processing.
Combines rule-based analysis with optional RAG-enhanced recommendations.
"""
from django.db.models import Q
from core.models.core import Game, Team
from core.models.results_financials import (
    RoundResultFinancials, RoundResultPerformanceIndex,
    RoundResultCoherence, RoundResultMarketRevenue,
    RoundResultProductMarket, LeaderboardEntry,
)
from core.models.results import RoundResultAdoption
from core.models.cc24_models import ESGEconomicImpact, TalentEconomicImpact, PartnershipEconomicImpact
from core.models.cc26_models import AIInvestorHolding
from core.models.cc27_models import StrategicBriefing
from core.models.team_state import TeamMarketPresence, TeamPlant, TeamPartnership, TeamAcquisition
from core.models.decisions import DecisionSubmission, DecisionESG
from core.models.talent import TeamTalentState
from core.models.scenario import AICompetitorDefinition


def generate_strategic_briefings(game, round_number, agent_narratives=None):
    """Generate a personalized strategic briefing for every team."""
    teams = Team.objects.filter(game=game)
    briefings_created = 0

    for team in teams:
        try:
            briefing_data = _compile_briefing(
                game, team, round_number,
                agent_narratives=agent_narratives,
            )
            StrategicBriefing.objects.update_or_create(
                game=game, team=team, round_number=round_number,
                defaults=briefing_data,
            )
            briefings_created += 1
        except Exception as e:
            print(f"Briefing generation failed for {team.name}: {e}")

    return briefings_created


def _compile_briefing(game, team, round_number, agent_narratives=None):
    """Compile all sections of the strategic briefing for one team."""
    current = _get_round_data(game, team, round_number)
    previous = _get_round_data(game, team, round_number - 1)
    scenario = game.scenario

    performance = _generate_performance_analysis(team, current, previous)
    investments = _generate_investment_returns(game, team, round_number)
    investor_sent = _generate_investor_sentiment(game, team, round_number)
    competitive = _generate_competitive_landscape(game, team, round_number)

    # CC-32E: Filter agent narratives relevant to this team
    team_agent_narratives = []
    if agent_narratives:
        for n in agent_narratives:
            # Include team-specific narratives and market-wide narratives
            if n.get('team_id') == team.id or n.get('team_id') is None:
                team_agent_narratives.append(n)

    return {
        'executive_summary': _generate_executive_summary(game, team, current, previous),
        'performance_analysis': performance,
        'investment_returns': investments,
        'investor_sentiment': investor_sent,
        'competitive_landscape': competitive,
        'strategic_recommendations': _generate_recommendations(
            game, team, round_number, current, previous, performance, investments, investor_sent, scenario,
        ),
        'risk_alerts': _generate_risk_alerts(team, current),
        'agent_narratives': team_agent_narratives,
    }


def _get_round_data(game, team, round_number):
    """Fetch all results data for a team for a specific round."""
    if round_number < 0:
        return None

    return {
        'financials': RoundResultFinancials.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first(),
        'performance': RoundResultPerformanceIndex.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first(),
        'coherence': RoundResultCoherence.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first(),
        'adoptions': list(RoundResultAdoption.objects.filter(
            game=game, team=team, round_number=round_number,
        ).select_related('segment', 'market')),
        'market_revenues': list(RoundResultMarketRevenue.objects.filter(
            game=game, team=team, round_number=round_number,
        ).select_related('market')),
        'product_results': list(RoundResultProductMarket.objects.filter(
            game=game, team=team, round_number=round_number,
        ).select_related('team_product', 'market')),
        'leaderboard': LeaderboardEntry.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first(),
        'talent': {
            ts.talent_pool: ts for ts in TeamTalentState.objects.filter(
                team=team, round_number=round_number,
            )
        },
    }


# ─── Executive Summary ───────────────────────────────────────────────────

def _generate_executive_summary(game, team, current, previous):
    """3-4 sentence headline summary."""
    if not current or not current['financials'] or not current['performance']:
        return "Round data not yet available."

    f = current['financials']
    pi = current['performance']
    lb = current['leaderboard']
    prev_f = previous['financials'] if previous else None
    total_teams = Team.objects.filter(game=game).count()

    parts = []

    # Performance headline
    index_change = float(pi.index_change)
    rank = lb.rank if lb else '?'
    if index_change > 2:
        parts.append(f"Strong quarter. Your Performance Index rose {index_change:+.1f} points to {float(pi.index_value):.1f}, placing you #{rank} of {total_teams} teams.")
    elif index_change > 0:
        parts.append(f"Steady progress. Your Performance Index edged up {index_change:+.1f} to {float(pi.index_value):.1f} (#{rank}).")
    elif index_change > -2:
        parts.append(f"Flat quarter. Your Performance Index dipped slightly to {float(pi.index_value):.1f} ({index_change:+.1f}, #{rank}).")
    else:
        parts.append(f"Challenging quarter. Your Performance Index fell {index_change:+.1f} to {float(pi.index_value):.1f}, dropping you to #{rank}.")

    # Revenue headline
    revenue = float(f.total_revenue)
    if prev_f and float(prev_f.total_revenue) > 0:
        prev_revenue = float(prev_f.total_revenue)
        rev_change = (revenue - prev_revenue) / prev_revenue * 100
        if rev_change > 10:
            parts.append(f"Revenue surged {rev_change:.0f}% to ${revenue/1e6:.1f}M.")
        elif rev_change > 0:
            parts.append(f"Revenue grew {rev_change:.0f}% to ${revenue/1e6:.1f}M.")
        elif rev_change > -10:
            parts.append(f"Revenue softened {rev_change:.0f}% to ${revenue/1e6:.1f}M.")
        else:
            parts.append(f"Revenue declined {rev_change:.0f}% to ${revenue/1e6:.1f}M — investigate segment performance.")
    else:
        parts.append(f"Revenue of ${revenue/1e6:.1f}M established.")

    # Financial health
    cash = float(f.cash_closing or 0)
    d_e = float(f.debt_to_equity or 0)
    net_income = float(f.net_income or 0)
    if cash < 5_000_000:
        parts.append(f"Cash reserves critically low at ${cash/1e6:.1f}M. Immediate action required.")
    elif d_e > 1.5:
        parts.append(f"Leverage elevated at {d_e:.2f}x D/E. Conservative investors may be concerned.")
    elif net_income > 0:
        parts.append(f"Net income of ${net_income/1e6:.1f}M ({float(f.net_margin_pct or 0)*100:.0f}% margin) — a profitable quarter.")
    else:
        parts.append(f"Net loss of ${abs(net_income)/1e6:.1f}M. Monitor cash runway closely.")

    return ' '.join(parts)


# ─── Performance Analysis ─────────────────────────────────────────────────

def _generate_performance_analysis(team, current, previous):
    if not current or not current['financials']:
        return {'revenue_drivers': [], 'segment_performance': [], 'market_performance': [], 'stakeholder_satisfaction': [], 'key_changes': []}

    analysis = {
        'revenue_drivers': [],
        'segment_performance': [],
        'market_performance': [],
        'stakeholder_satisfaction': [],
        'key_changes': [],
    }

    f = current['financials']
    prev_f = previous['financials'] if previous else None

    # Revenue drivers
    for mr in current['market_revenues']:
        prev_mr = None
        if previous:
            prev_mr = next((p for p in previous['market_revenues'] if p.market_id == mr.market_id), None)

        revenue = float(mr.home_revenue or 0)
        prev_revenue = float(prev_mr.home_revenue or 0) if prev_mr else 0
        change = revenue - prev_revenue

        if revenue > 0:
            analysis['revenue_drivers'].append({
                'market': mr.market.name,
                'revenue': revenue,
                'change': change,
                'change_pct': (change / prev_revenue * 100) if prev_revenue > 0 else None,
                'share': float(mr.market_share_pct or 0),
            })

    # Segment performance
    customer_adoptions = [a for a in current['adoptions'] if a.segment.segment_type == 'customer']
    if customer_adoptions:
        sorted_by_fit = sorted(customer_adoptions, key=lambda a: float(a.adjusted_fit_score or 0), reverse=True)
        for a in sorted_by_fit[:3]:
            analysis['segment_performance'].append({
                'segment': a.segment.name,
                'market': a.market.name if a.market else 'Global',
                'fit': _fit_label(float(a.adjusted_fit_score or 0)),
                'fit_score': float(a.adjusted_fit_score or 0),
                'adopters': float(a.new_adopters or 0),
                'share': float(a.team_share_pct or 0),
                'position': 'strong',
            })
        for a in sorted_by_fit[-3:]:
            if a not in sorted_by_fit[:3]:
                analysis['segment_performance'].append({
                    'segment': a.segment.name,
                    'market': a.market.name if a.market else 'Global',
                    'fit': _fit_label(float(a.adjusted_fit_score or 0)),
                    'fit_score': float(a.adjusted_fit_score or 0),
                    'adopters': float(a.new_adopters or 0),
                    'share': float(a.team_share_pct or 0),
                    'position': 'weak',
                })

    # Stakeholder satisfaction
    non_customer = [a for a in current['adoptions'] if a.segment.segment_type != 'customer']
    for a in non_customer:
        prev_a = None
        if previous:
            prev_a = next((p for p in previous['adoptions'] if p.segment_id == a.segment_id), None)

        current_fit = float(a.adjusted_fit_score or 0)
        prev_fit = float(prev_a.adjusted_fit_score or 0) if prev_a else 0
        trend = 'improved' if current_fit > prev_fit + 0.03 else ('declined' if current_fit < prev_fit - 0.03 else 'stable')

        type_map = {'investor': 'investors', 'regulator': 'regulators', 'channel_partner': 'channel partners'}
        group = type_map.get(a.segment.segment_type, a.segment.segment_type)

        if current_fit >= 0.7:
            narrative = f"Your {group} are satisfied with your current direction."
        elif current_fit >= 0.5 and trend == 'improved':
            narrative = f"Your {group} are warming to your strategy."
        elif current_fit >= 0.5:
            narrative = f"Your {group} have moderate confidence."
        elif trend == 'declined':
            narrative = f"Your {group} are losing confidence. Review what changed."
        else:
            narrative = f"Your {group} have low confidence in your current strategy."

        analysis['stakeholder_satisfaction'].append({
            'segment': a.segment.name,
            'type': a.segment.segment_type,
            'satisfaction': _fit_label(current_fit),
            'satisfaction_score': current_fit,
            'trend': trend,
            'narrative': narrative,
        })

    # Key changes
    if prev_f:
        for metric, field, fmt_fn in [
            ('Revenue', 'total_revenue', lambda v: f"${v/1e6:.1f}M"),
            ('Debt-to-Equity', 'debt_to_equity', lambda v: f"{v:.2f}"),
            ('Cash Position', 'cash_closing', lambda v: f"${v/1e6:.1f}M"),
        ]:
            old_val = float(getattr(prev_f, field) or 0)
            new_val = float(getattr(f, field) or 0)
            if abs(new_val - old_val) > 0.001:
                analysis['key_changes'].append({
                    'metric': metric,
                    'old': old_val,
                    'new': new_val,
                    'formatted': f"{fmt_fn(old_val)} → {fmt_fn(new_val)}",
                })

    return analysis


# ─── Investment Returns ───────────────────────────────────────────────────

def _generate_investment_returns(game, team, round_number):
    returns = {
        'esg': {'invested': 0, 'returns': [], 'total_savings': 0, 'narrative': ''},
        'talent': {'invested': 0, 'returns': [], 'total_savings': 0, 'net_roi': 0, 'narrative': ''},
        'partnerships': {'count': 0, 'returns': [], 'total_value': 0, 'narrative': ''},
        'plants': {'count': 0, 'narrative': ''},
        'total_strategic_cost': 0,
        'total_strategic_return': 0,
        'overall_narrative': '',
    }

    # ESG
    esg_impacts = ESGEconomicImpact.objects.filter(game=game, team=team, round_number=round_number)
    for impact in esg_impacts:
        returns['esg']['returns'].append({
            'type': impact.benefit_type,
            'market': impact.market.name if impact.market else 'Global',
            'savings': float(impact.savings),
        })
    returns['esg']['total_savings'] = sum(float(i.savings) for i in esg_impacts)

    submission = DecisionSubmission.objects.filter(
        team=team, round__game=game, round__round_number=round_number, status='locked',
    ).first()
    if submission:
        esg_dec = DecisionESG.objects.filter(submission=submission).first()
        if esg_dec:
            returns['esg']['invested'] = float(
                (esg_dec.environmental_investment or 0) + (esg_dec.social_investment or 0)
            )

    if returns['esg']['invested'] > 0:
        roi_pct = returns['esg']['total_savings'] / returns['esg']['invested'] * 100
        returns['esg']['narrative'] = (
            f"Your ESG investment of ${returns['esg']['invested']/1e6:.1f}M generated "
            f"${returns['esg']['total_savings']/1e3:.0f}K in economic benefits ({roi_pct:.0f}% quarterly return). "
        )
        if roi_pct < 10:
            returns['esg']['narrative'] += "Returns are building — ESG investments compound over time."
        elif roi_pct < 25:
            returns['esg']['narrative'] += "Solid returns."
        else:
            returns['esg']['narrative'] += "Excellent returns. Your ESG leadership is a competitive advantage."
    else:
        returns['esg']['narrative'] = "No ESG investment this round. You're missing potential tariff and tax benefits."

    # Talent
    talent_impact = TalentEconomicImpact.objects.filter(
        game=game, team=team, round_number=round_number,
    ).first()
    if talent_impact:
        returns['talent']['invested'] = float(talent_impact.total_talent_cost)
        returns['talent']['total_savings'] = float(talent_impact.total_talent_benefit)
        returns['talent']['net_roi'] = float(talent_impact.net_talent_roi)

        for label, field in [
            ('R&D cost reduction', 'rd_cost_savings'),
            ('Operations efficiency', 'cogs_savings'),
            ('Marketing effectiveness', 'campaign_revenue_uplift'),
        ]:
            val = float(getattr(talent_impact, field, 0) or 0)
            if val > 0:
                returns['talent']['returns'].append({'type': label, 'savings': val})

        if returns['talent']['net_roi'] > 0:
            returns['talent']['narrative'] = (
                f"Talent investment of ${returns['talent']['invested']/1e6:.1f}M generated "
                f"${returns['talent']['total_savings']/1e3:.0f}K in benefits. Net positive ROI."
            )
        elif returns['talent']['total_savings'] > 0:
            returns['talent']['narrative'] = (
                f"Talent costs ${returns['talent']['invested']/1e6:.1f}M with "
                f"${returns['talent']['total_savings']/1e3:.0f}K in benefits. Building momentum."
            )
        else:
            returns['talent']['narrative'] = "Talent at baseline levels. Invest above 3.0 to unlock cost reductions."

    # Partnerships
    partnership_impacts = PartnershipEconomicImpact.objects.filter(
        game=game, team=team, round_number=round_number,
    )
    returns['partnerships']['count'] = TeamPartnership.objects.filter(team=team, status='active').count()
    returns['partnerships']['total_value'] = sum(float(p.benefit_amount) for p in partnership_impacts)
    if returns['partnerships']['count'] > 0:
        returns['partnerships']['narrative'] = (
            f"{returns['partnerships']['count']} active partnership(s) generating "
            f"${returns['partnerships']['total_value']/1e3:.0f}K in value."
        )
    else:
        returns['partnerships']['narrative'] = "No active partnerships."

    # Plants
    plants = TeamPlant.objects.filter(team=team, status='operational')
    returns['plants']['count'] = plants.count()
    if plants.exists():
        returns['plants']['narrative'] = (
            f"{plants.count()} operational plant(s). Local manufacturing eliminates tariffs "
            f"and reduces logistics costs."
        )
    else:
        returns['plants']['narrative'] = "No owned plants."

    # Totals
    returns['total_strategic_cost'] = returns['esg']['invested'] + returns['talent']['invested']
    returns['total_strategic_return'] = returns['esg']['total_savings'] + returns['talent']['total_savings'] + returns['partnerships']['total_value']

    if returns['total_strategic_cost'] > 0:
        overall_roi = returns['total_strategic_return'] / returns['total_strategic_cost'] * 100
        returns['overall_narrative'] = (
            f"Total strategic investment: ${returns['total_strategic_cost']/1e6:.1f}M. "
            f"Returns: ${returns['total_strategic_return']/1e3:.0f}K ({overall_roi:.0f}% quarterly)."
        )
    else:
        returns['overall_narrative'] = "No significant strategic investments this round."

    return returns


# ─── Investor Sentiment ───────────────────────────────────────────────────

def _generate_investor_sentiment(game, team, round_number):
    sentiment = {
        'share_price': 0,
        'share_price_change': 0,
        'share_price_change_pct': 0,
        'investors': [],
        'narrative': '',
    }

    financials = RoundResultFinancials.objects.filter(
        game=game, team=team, round_number=round_number,
    ).first()
    prev_financials = RoundResultFinancials.objects.filter(
        game=game, team=team, round_number=round_number - 1,
    ).first()

    if financials:
        sentiment['share_price'] = float(financials.share_price or 0)
        if prev_financials and float(prev_financials.share_price or 0) > 0:
            prev_price = float(prev_financials.share_price)
            sentiment['share_price_change'] = sentiment['share_price'] - prev_price
            sentiment['share_price_change_pct'] = sentiment['share_price_change'] / prev_price * 100

    # AI investor holdings (CC-26 field names)
    holdings = AIInvestorHolding.objects.filter(
        game=game, team=team, round_number=round_number,
    ).select_related('fund')

    for h in holdings:
        prev_h = AIInvestorHolding.objects.filter(
            game=game, team=team, fund=h.fund, round_number=round_number - 1,
        ).first()
        prev_shares = prev_h.shares_held if prev_h else int(float(h.fund.initial_holding_pct) * team.shares_outstanding)
        change = h.shares_held - prev_shares

        action_word = 'bought' if change > 0 else ('sold' if change < 0 else 'held')

        # Per-investor narrative
        name = h.fund.name
        if action_word == 'bought':
            if 'Velocity' in name:
                narr = f"{name} added {abs(change):,} shares. Your growth trajectory is attracting growth capital."
            elif 'Granite' in name:
                narr = f"{name} added {abs(change):,} shares. Your financial discipline appeals to value investors."
            elif 'Green' in name:
                narr = f"{name} added {abs(change):,} shares. Your ESG investments are attracting responsible capital."
            else:
                narr = f"{name} added {abs(change):,} shares."
        elif action_word == 'sold':
            if 'Velocity' in name:
                narr = f"{name} sold {abs(change):,} shares. They may see insufficient growth momentum."
            elif 'Granite' in name:
                narr = f"{name} sold {abs(change):,} shares. Rising leverage or declining margins may concern them."
            elif 'Green' in name:
                narr = f"{name} sold {abs(change):,} shares. Your ESG profile may not meet their criteria."
            else:
                narr = f"{name} sold {abs(change):,} shares."
        else:
            narr = f"{name} maintained position. No change in confidence."

        sentiment['investors'].append({
            'name': name,
            'philosophy': h.fund.investment_philosophy,
            'shares': h.shares_held,
            'change': change,
            'action': action_word,
            'satisfaction': float(h.satisfaction_score),
            'narrative': narr,
        })

    # Overall narrative
    price_dir = 'rose' if sentiment['share_price_change'] > 0 else ('fell' if sentiment['share_price_change'] < 0 else 'held steady')
    parts = [f"Your share price {price_dir} to ${sentiment['share_price']:.2f} ({sentiment['share_price_change_pct']:+.1f}%)."]

    buyers = [i for i in sentiment['investors'] if i['action'] == 'bought']
    sellers = [i for i in sentiment['investors'] if i['action'] == 'sold']
    if buyers:
        parts.append(f"{', '.join(i['name'] for i in buyers)} increased positions.")
    if sellers:
        parts.append(f"{', '.join(i['name'] for i in sellers)} reduced exposure.")

    sentiment['narrative'] = ' '.join(parts)
    return sentiment


# ─── Competitive Landscape ────────────────────────────────────────────────

def _generate_competitive_landscape(game, team, round_number):
    landscape = {
        'your_rank': 0,
        'rank_change': 0,
        'competitor_moves': [],
        'narrative': '',
    }

    lb = LeaderboardEntry.objects.filter(game=game, team=team, round_number=round_number).first()
    prev_lb = LeaderboardEntry.objects.filter(game=game, team=team, round_number=round_number - 1).first()

    if lb:
        landscape['your_rank'] = lb.rank
        if prev_lb:
            landscape['rank_change'] = prev_lb.rank - lb.rank

    # Other teams' notable moves
    other_teams = Team.objects.filter(game=game).exclude(id=team.id)
    for other in other_teams:
        moves = []
        new_entries = TeamMarketPresence.objects.filter(
            team=other, established_round=round_number,
        ).select_related('market', 'entry_mode')
        for entry in new_entries:
            mode_name = entry.entry_mode.name if entry.entry_mode else 'unknown mode'
            moves.append(f"Entered {entry.market.name} via {mode_name}")

        new_acqs = TeamAcquisition.objects.filter(team=other, acquired_round=round_number)
        for acq in new_acqs:
            moves.append(f"Acquired {acq.acquisition_target.target_name}")

        if moves:
            landscape['competitor_moves'].append({'team': other.name, 'moves': moves})

    # Narrative
    parts = []
    if landscape['rank_change'] > 0:
        parts.append(f"You climbed {landscape['rank_change']} position(s) to #{landscape['your_rank']}.")
    elif landscape['rank_change'] < 0:
        parts.append(f"You dropped {abs(landscape['rank_change'])} position(s) to #{landscape['your_rank']}.")
    else:
        parts.append(f"You maintained position #{landscape['your_rank']}.")

    for cm in landscape['competitor_moves']:
        parts.append(f"{cm['team']}: {'; '.join(cm['moves'])}.")

    landscape['narrative'] = ' '.join(parts)
    return landscape


# ─── Strategic Recommendations ────────────────────────────────────────────

def _generate_recommendations(game, team, round_number, current, previous, performance, investments, investor_sent, scenario):
    if not current or not current['financials']:
        return []

    recommendations = []
    f = current['financials']

    # 1. Segment opportunity — distinguish universal gaps from team-specific weaknesses
    weak_segs = [s for s in performance.get('segment_performance', []) if s['position'] == 'weak']
    if weak_segs:
        w = weak_segs[0]
        # Check if this is an industry-wide gap: are ALL teams weak on this segment?
        from core.models.scenario import SegmentDefinition
        seg_def = SegmentDefinition.objects.filter(
            scenario=scenario, name=w['segment'],
        ).first()
        is_universal_gap = False
        if seg_def:
            all_fits = RoundResultAdoption.objects.filter(
                game=game, round_number=round_number, segment=seg_def,
            ).values_list('adjusted_fit_score', flat=True)
            best_competitor_fit = max((float(f) for f in all_fits), default=0)
            is_universal_gap = best_competitor_fit < 0.15

        if is_universal_gap:
            recommendations.append({
                'priority': 'high',
                'category': 'market',
                'title': f"First-Mover Opportunity: {w['segment']}",
                'detail': (
                    f"No competitor currently serves {w['segment']} well — this is an industry-wide gap. "
                    f"Investing in the features this segment values could give you first-mover advantage. "
                    f"Check Market Research to identify which platform capabilities they prioritize."
                ),
                'action_page': 'Market Research → Segments',
            })
        else:
            recommendations.append({
                'priority': 'high',
                'category': 'market',
                'title': f"Improve {w['segment']} Appeal",
                'detail': (
                    f"Your fit with {w['segment']} in {w['market']} is {w['fit']}, "
                    f"but competitors are doing better. "
                    f"Review Market Research to identify which features this segment values most."
                ),
                'action_page': 'Market Research → Segments',
            })

    # 2. Financial health
    d_e = float(f.debt_to_equity or 0)
    cash_ratio = float(f.cash_closing or 0) / max(float(f.total_revenue or 1), 1)

    if d_e > 1.0:
        recommendations.append({
            'priority': 'high',
            'category': 'finance',
            'title': 'Reduce Leverage',
            'detail': (
                f"Your debt-to-equity ratio is {d_e:.2f}. Conservative investors are concerned. "
                f"Consider using cash flow to repay debt or issuing equity."
            ),
            'action_page': 'Finance → Capital Management',
        })
    elif cash_ratio > 3.0:
        recommendations.append({
            'priority': 'medium',
            'category': 'finance',
            'title': 'Deploy Excess Cash',
            'detail': (
                f"Holding ${float(f.cash_closing)/1e6:.0f}M in cash — {cash_ratio:.0f}x revenue. "
                f"Consider R&D, market entry, marketing, or dividends."
            ),
            'action_page': 'Finance → Budget Allocation',
        })

    # 3. ESG
    if investments['esg']['total_savings'] == 0:
        in_high_reg = TeamMarketPresence.objects.filter(
            team=team, status='active'
        ).filter(
            Q(market__code='EU') | Q(market__regulatory_difficulty__gte=6)
        ).exists()
        if in_high_reg:
            recommendations.append({
                'priority': 'high',
                'category': 'strategy',
                'title': 'ESG Investment Critical for Highly Regulated Market',
                'detail': "Operating in a highly regulated market without ESG investment. Regulators heavily weight sustainability.",
                'action_page': 'Corporate Strategy → ESG',
            })
        else:
            recommendations.append({
                'priority': 'medium',
                'category': 'strategy',
                'title': 'Consider ESG Investment',
                'detail': "ESG generates tariff reductions, tax incentives, and improves regulator satisfaction.",
                'action_page': 'Corporate Strategy → ESG',
            })

    # 4. Talent
    rd_talent = current.get('talent', {}).get('rd')
    if rd_talent and float(rd_talent.talent_level) <= 3.0:
        recommendations.append({
            'priority': 'medium',
            'category': 'capability',
            'title': 'Invest in R&D Talent',
            'detail': "R&D team at baseline (3.0). Each level above 3.0 saves 5% on R&D costs.",
            'action_page': 'Corporate Strategy → Talent',
        })

    # 5. Market expansion
    market_count = TeamMarketPresence.objects.filter(team=team, status='active').count()
    if market_count == 1 and float(f.cash_closing or 0) > 15_000_000:
        recommendations.append({
            'priority': 'medium',
            'category': 'growth',
            'title': 'Consider International Expansion',
            'detail': f"Operating in one market with ${float(f.cash_closing)/1e6:.0f}M cash. Export entry costs only $500K.",
            'action_page': 'Market Strategy',
        })

    # 6. Investor-driven
    sellers = [i for i in investor_sent.get('investors', []) if i['action'] == 'sold']
    if sellers:
        seller = sellers[0]
        recommendations.append({
            'priority': 'medium',
            'category': 'investor_relations',
            'title': f"Address {seller['name']} Concerns",
            'detail': (
                f"{seller['name']} reduced their position. Check Investor Relations "
                f"to understand their criteria."
            ),
            'action_page': 'Financial Reports → Investor Relations',
        })

    # RAG enhancement for top 2
    for rec in recommendations[:2]:
        enhanced = _rag_enhance_recommendation(rec, scenario)
        if enhanced:
            rec['framework_reference'] = enhanced

    # Sort by priority, limit to 5
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    recommendations.sort(key=lambda r: priority_order.get(r['priority'], 2))
    return recommendations[:5]


def _rag_enhance_recommendation(recommendation, scenario):
    """Add a framework reference from the RAG corpus."""
    try:
        from core.rag.embeddings import get_embedding
        from core.rag.client import search_articles
        from django.conf import settings
        import time

        query = f"{recommendation['title']}: {recommendation['detail'][:100]}"
        embedding = get_embedding(query)
        results = search_articles(embedding, limit=1)

        if not results or not getattr(settings, 'DASHSCOPE_API_KEY', None):
            return None

        import dashscope
        from dashscope import Generation
        dashscope.api_key = settings.DASHSCOPE_API_KEY

        time.sleep(0.3)
        response = Generation.call(
            model=settings.DASHSCOPE_MODEL,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are a strategy professor. Given a recommendation and research source, '
                        'provide one sentence grounding it in theory. Write as: "This aligns with..." '
                        'Do not cite sources by title.'
                    ),
                },
                {
                    'role': 'user',
                    'content': (
                        f"Recommendation: {recommendation['title']}\n"
                        f"Context: {recommendation['detail']}\n"
                        f"Research: {results[0]['text'][:300]}"
                    ),
                },
            ],
            max_tokens=60,
            temperature=0.3,
            request_timeout=5,
        )
        return response.output.text
    except Exception:
        return None


# ─── Risk Alerts ──────────────────────────────────────────────────────────

def _generate_risk_alerts(team, current):
    if not current or not current['financials']:
        return []

    alerts = []
    f = current['financials']

    # Cash runway
    net_income = float(f.net_income or 0)
    if net_income < 0:
        burn = abs(net_income)
        cash = float(f.cash_closing or 0)
        runway = cash / burn if burn > 0 else 999
        if runway < 3:
            alerts.append({
                'severity': 'critical',
                'title': f'Cash Runway: {runway:.1f} rounds remaining',
                'detail': f'At current burn of ${burn/1e6:.1f}M/round, cash depletes in ~{runway:.1f} rounds.',
            })
        elif runway < 6:
            alerts.append({
                'severity': 'warning',
                'title': f'Cash runway declining: {runway:.1f} rounds',
                'detail': 'Monitor closely. Consider revenue acceleration or cost reduction.',
            })

    # Interest burden
    interest = float(f.interest_expense or 0)
    oi = float(f.operating_income or 0)
    if interest > 0:
        coverage = oi / interest
        if coverage < 2:
            alerts.append({
                'severity': 'warning',
                'title': f'Interest coverage critically low: {coverage:.1f}x',
                'detail': 'Operating income barely covers interest. Consider debt repayment.',
            })

    # Market concentration
    market_count = TeamMarketPresence.objects.filter(team=team, status='active').count()
    lb = current.get('leaderboard')
    if market_count == 1 and lb and lb.rank >= 3:
        alerts.append({
            'severity': 'info',
            'title': 'Single-market concentration risk',
            'detail': 'All revenue from one market. Consider geographic diversification.',
        })

    # Talent turnover
    for pool, state in current.get('talent', {}).items():
        if hasattr(state, 'turnover_rate') and float(state.turnover_rate) > 0.20:
            alerts.append({
                'severity': 'warning',
                'title': f'{pool.replace("_", " ").title()} talent turnover at {float(state.turnover_rate)*100:.0f}%',
                'detail': 'High turnover erodes institutional knowledge.',
            })

    # Inventory buildup
    for pr in current.get('product_results', []):
        units_sold = float(pr.units_sold or 0)
        units_unsold = float(pr.units_unsold or 0)
        units_produced = float(pr.units_produced or 0)
        if units_unsold > units_sold * 0.3 and units_produced > 0:
            pct = units_unsold / units_produced * 100
            alerts.append({
                'severity': 'warning',
                'title': f'{pr.team_product.name} inventory buildup in {pr.market.name}',
                'detail': f'{pct:.0f}% of production unsold. Reduce production or lower price.',
            })

    return alerts


def _fit_label(score):
    if score >= 0.7:
        return 'Strong'
    if score >= 0.5:
        return 'Moderate'
    if score >= 0.3:
        return 'Weak'
    return 'Very Weak'
