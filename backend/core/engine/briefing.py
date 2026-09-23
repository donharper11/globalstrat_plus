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
from core.utils.localization import get_localized_field, get_team_language
from core.utils.participant_messages import market_label, participant_message


# W-CE3-11. Every sentence below was an f-string with no catalogue entry, so
# the briefing -- a student's first screen after signing in -- was English
# whatever their language. `StrategicBriefing` is a NARRATIVE section
# (`in_output=False`, every field a `narrative_field`): Phase-2 prose, never
# part of the competitive hash. The sibling writer of the same rows,
# `engine/narratives._build_briefing_fields`, already writes them in the
# team's language through `get_team_language`, so these follow it and are
# STORED in the team's language rather than re-rendered at read time. The
# `coherence_feedback` pattern is for a scoring artefact inside the
# competitive envelope; nothing here is.
def _t(language, key, **values):
    """One briefing sentence, in the team's language."""
    return participant_message(key, language=language, **values)


def _money(value):
    """$1.2M, the way every briefing figure was already written."""
    return f'${value / 1e6:.1f}M'


def _thousands(value):
    return f'${value / 1e3:.0f}K'


def generate_strategic_briefings(game, round_number, agent_narratives=None):
    """Generate a personalized strategic briefing for every team."""
    teams = Team.objects.filter(game=game, participation_status='active')
    briefings_created = 0

    for team in teams:
        try:
            briefing_data = _compile_briefing(
                game, team, round_number,
                agent_narratives=agent_narratives,
                language=get_team_language(team),
            )
            StrategicBriefing.objects.update_or_create(
                game=game, team=team, round_number=round_number,
                defaults=briefing_data,
            )
            briefings_created += 1
        except Exception as e:
            print(f"Briefing generation failed for {team.name}: {e}")

    return briefings_created


def _compile_briefing(game, team, round_number, agent_narratives=None,
                      language='en'):
    """Compile all sections of the strategic briefing for one team."""
    current = _get_round_data(game, team, round_number)
    previous = _get_round_data(game, team, round_number - 1)
    scenario = game.scenario

    performance = _generate_performance_analysis(
        team, current, previous, language)
    investments = _generate_investment_returns(
        game, team, round_number, language)
    investor_sent = _generate_investor_sentiment(
        game, team, round_number, language)
    competitive = _generate_competitive_landscape(
        game, team, round_number, language)

    # CC-32E: Filter agent narratives relevant to this team
    team_agent_narratives = []
    if agent_narratives:
        for n in agent_narratives:
            # Include team-specific narratives and market-wide narratives
            if n.get('team_id') == team.id or n.get('team_id') is None:
                team_agent_narratives.append(n)

    return {
        'executive_summary': _generate_executive_summary(
            game, team, current, previous, language),
        'performance_analysis': performance,
        'investment_returns': investments,
        'investor_sentiment': investor_sent,
        'competitive_landscape': competitive,
        'strategic_recommendations': _generate_recommendations(
            game, team, round_number, current, previous, performance,
            investments, investor_sent, scenario, language,
        ),
        'risk_alerts': _generate_risk_alerts(team, current, language),
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

def _generate_executive_summary(game, team, current, previous,
                                language='en'):
    """3-4 sentence headline summary."""
    if not current or not current['financials'] or not current['performance']:
        return _t(language, 'briefing_no_data')

    f = current['financials']
    pi = current['performance']
    lb = current['leaderboard']
    prev_f = previous['financials'] if previous else None
    total_teams = Team.objects.filter(
        game=game, participation_status='active',
    ).count()

    parts = []

    # Performance headline
    index_change = float(pi.index_change)
    rank = lb.rank if lb else '?'
    change = f'{index_change:+.1f}'
    index_value = f'{float(pi.index_value):.1f}'
    if index_change > 2:
        parts.append(_t(language, 'briefing_perf_strong', change=change,
                        index=index_value, rank=rank, total=total_teams))
    elif index_change > 0:
        parts.append(_t(language, 'briefing_perf_steady', change=change,
                        index=index_value, rank=rank))
    elif index_change > -2:
        parts.append(_t(language, 'briefing_perf_flat', change=change,
                        index=index_value, rank=rank))
    else:
        parts.append(_t(language, 'briefing_perf_weak', change=change,
                        index=index_value, rank=rank))

    # Revenue headline
    revenue = float(f.total_revenue)
    if prev_f and float(prev_f.total_revenue) > 0:
        prev_revenue = float(prev_f.total_revenue)
        rev_change = (revenue - prev_revenue) / prev_revenue * 100
        pct = f'{rev_change:.0f}'
        if rev_change > 10:
            key = 'briefing_revenue_surged'
        elif rev_change > 0:
            key = 'briefing_revenue_grew'
        elif rev_change > -10:
            key = 'briefing_revenue_softened'
        else:
            key = 'briefing_revenue_declined'
        parts.append(_t(language, key, pct=pct, revenue=_money(revenue)))
    else:
        parts.append(_t(language, 'briefing_revenue_established',
                        revenue=_money(revenue)))

    # Financial health
    cash = float(f.cash_closing or 0)
    d_e = float(f.debt_to_equity or 0)
    net_income = float(f.net_income or 0)
    if cash < 5_000_000:
        parts.append(_t(language, 'briefing_cash_critical',
                        cash=_money(cash)))
    elif d_e > 1.5:
        parts.append(_t(language, 'briefing_leverage_elevated',
                        ratio=f'{d_e:.2f}'))
    elif net_income > 0:
        parts.append(_t(language, 'briefing_net_income_positive',
                        net_income=_money(net_income),
                        margin=f'{float(f.net_margin_pct or 0) * 100:.0f}'))
    else:
        parts.append(_t(language, 'briefing_net_loss',
                        loss=_money(abs(net_income))))

    return ' '.join(parts)


# ─── Performance Analysis ─────────────────────────────────────────────────

def _generate_performance_analysis(team, current, previous, language='en'):
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
                'market': get_localized_field(mr.market, 'name', language),
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
                # The id travels beside the name so a recommendation can find
                # the segment definition without matching on a localised
                # string (W-CE3-11).
                'segment_id': a.segment_id,
                'segment': get_localized_field(a.segment, 'name', language),
                'market': market_label(a.market, language),
                'fit': _fit_label(float(a.adjusted_fit_score or 0), language),
                'fit_score': float(a.adjusted_fit_score or 0),
                'adopters': float(a.new_adopters or 0),
                'share': float(a.team_share_pct or 0),
                'position': 'strong',
            })
        for a in sorted_by_fit[-3:]:
            if a not in sorted_by_fit[:3]:
                analysis['segment_performance'].append({
                    'segment_id': a.segment_id,
                    'segment': get_localized_field(a.segment, 'name', language),
                    'market': market_label(a.market, language),
                    'fit': _fit_label(float(a.adjusted_fit_score or 0),
                                      language),
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

        group = _group_label(a.segment.segment_type, language)

        if current_fit >= 0.7:
            key = 'briefing_stake_satisfied'
        elif current_fit >= 0.5 and trend == 'improved':
            key = 'briefing_stake_warming'
        elif current_fit >= 0.5:
            key = 'briefing_stake_moderate'
        elif trend == 'declined':
            key = 'briefing_stake_declining'
        else:
            key = 'briefing_stake_low'
        narrative = _t(language, key, group=group)

        analysis['stakeholder_satisfaction'].append({
            'segment': get_localized_field(a.segment, 'name', language),
            'type': a.segment.segment_type,
            'satisfaction': _fit_label(current_fit, language),
            'satisfaction_score': current_fit,
            # The screen prints `trend`, so it carries the word; the code it
            # was chosen by travels beside it for anything that branches.
            'trend': _t(language, f'briefing_trend_{trend}'),
            'trend_code': trend,
            'narrative': narrative,
        })

    # Key changes
    if prev_f:
        for metric_key, field, fmt_fn in [
            ('briefing_metric_revenue', 'total_revenue', _money),
            ('briefing_metric_debt_to_equity', 'debt_to_equity',
             lambda v: f"{v:.2f}"),
            ('briefing_metric_cash_position', 'cash_closing', _money),
        ]:
            metric = _t(language, metric_key)
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

def _generate_investment_returns(game, team, round_number, language='en'):
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
            'market': market_label(impact.market, language),
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
        if roi_pct < 10:
            verdict = 'briefing_esg_building'
        elif roi_pct < 25:
            verdict = 'briefing_esg_solid'
        else:
            verdict = 'briefing_esg_excellent'
        returns['esg']['narrative'] = ' '.join([
            _t(language, 'briefing_esg_return',
               invested=_money(returns['esg']['invested']),
               savings=_thousands(returns['esg']['total_savings']),
               roi=f'{roi_pct:.0f}'),
            _t(language, verdict),
        ])
    else:
        returns['esg']['narrative'] = _t(language, 'briefing_esg_none')

    # Talent
    talent_impact = TalentEconomicImpact.objects.filter(
        game=game, team=team, round_number=round_number,
    ).first()
    if talent_impact:
        returns['talent']['invested'] = float(talent_impact.total_talent_cost)
        returns['talent']['total_savings'] = float(talent_impact.total_talent_benefit)
        returns['talent']['net_roi'] = float(talent_impact.net_talent_roi)

        for label_key, field in [
            ('briefing_talent_rd_savings', 'rd_cost_savings'),
            ('briefing_talent_cogs_savings', 'cogs_savings'),
            ('briefing_talent_campaign_uplift', 'campaign_revenue_uplift'),
        ]:
            val = float(getattr(talent_impact, field, 0) or 0)
            if val > 0:
                returns['talent']['returns'].append(
                    {'type': _t(language, label_key), 'savings': val})

        if returns['talent']['net_roi'] > 0:
            returns['talent']['narrative'] = _t(
                language, 'briefing_talent_positive',
                invested=_money(returns['talent']['invested']),
                savings=_thousands(returns['talent']['total_savings']))
        elif returns['talent']['total_savings'] > 0:
            returns['talent']['narrative'] = _t(
                language, 'briefing_talent_building',
                invested=_money(returns['talent']['invested']),
                savings=_thousands(returns['talent']['total_savings']))
        else:
            returns['talent']['narrative'] = _t(
                language, 'briefing_talent_baseline')

    # Partnerships
    partnership_impacts = PartnershipEconomicImpact.objects.filter(
        game=game, team=team, round_number=round_number,
    )
    returns['partnerships']['count'] = TeamPartnership.objects.filter(team=team, status='active').count()
    returns['partnerships']['total_value'] = sum(float(p.benefit_amount) for p in partnership_impacts)
    if returns['partnerships']['count'] > 0:
        returns['partnerships']['narrative'] = _t(
            language, 'briefing_partnerships_active',
            count=returns['partnerships']['count'],
            value=_thousands(returns['partnerships']['total_value']))
    else:
        returns['partnerships']['narrative'] = _t(
            language, 'briefing_partnerships_none')

    # Plants
    plants = TeamPlant.objects.filter(team=team, status='operational')
    returns['plants']['count'] = plants.count()
    if plants.exists():
        returns['plants']['narrative'] = _t(
            language, 'briefing_plants_operational', count=plants.count())
    else:
        returns['plants']['narrative'] = _t(
            language, 'briefing_plants_none')

    # Totals
    returns['total_strategic_cost'] = returns['esg']['invested'] + returns['talent']['invested']
    returns['total_strategic_return'] = returns['esg']['total_savings'] + returns['talent']['total_savings'] + returns['partnerships']['total_value']

    if returns['total_strategic_cost'] > 0:
        overall_roi = returns['total_strategic_return'] / returns['total_strategic_cost'] * 100
        returns['overall_narrative'] = _t(
            language, 'briefing_strategic_totals',
            cost=_money(returns['total_strategic_cost']),
            returns=_thousands(returns['total_strategic_return']),
            roi=f'{overall_roi:.0f}')
    else:
        returns['overall_narrative'] = _t(
            language, 'briefing_strategic_none')

    return returns


# ─── Investor Sentiment ───────────────────────────────────────────────────

def _generate_investor_sentiment(game, team, round_number, language='en'):
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

        # Per-investor narrative. The fund's own name decides which
        # reason is given, exactly as before; only the wording moved.
        name = h.fund.name
        if 'Velocity' in name:
            flavour = 'growth'
        elif 'Granite' in name:
            flavour = 'value'
        elif 'Green' in name:
            flavour = 'esg'
        else:
            flavour = None
        shares = f'{abs(change):,}'
        if action_word == 'held':
            narr = _t(language, 'briefing_investor_held', name=name)
        else:
            key = f'briefing_investor_{action_word}'
            if flavour:
                key = f'{key}_{flavour}'
            narr = _t(language, key, name=name, shares=shares)

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
    if sentiment['share_price_change'] > 0:
        price_key = 'briefing_share_price_rose'
    elif sentiment['share_price_change'] < 0:
        price_key = 'briefing_share_price_fell'
    else:
        price_key = 'briefing_share_price_steady'
    parts = [_t(language, price_key,
                price=f"${sentiment['share_price']:.2f}",
                pct=f"{sentiment['share_price_change_pct']:+.1f}")]

    buyers = [i for i in sentiment['investors'] if i['action'] == 'bought']
    sellers = [i for i in sentiment['investors'] if i['action'] == 'sold']
    if buyers:
        parts.append(_t(language, 'briefing_investors_increased',
                        names=', '.join(i['name'] for i in buyers)))
    if sellers:
        parts.append(_t(language, 'briefing_investors_reduced',
                        names=', '.join(i['name'] for i in sellers)))

    sentiment['narrative'] = ' '.join(parts)
    return sentiment


# ─── Competitive Landscape ────────────────────────────────────────────────

def _generate_competitive_landscape(game, team, round_number,
                                    language='en'):
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
    other_teams = Team.objects.filter(
        game=game, participation_status='active',
    ).exclude(id=team.id)
    for other in other_teams:
        moves = []
        new_entries = TeamMarketPresence.objects.filter(
            team=other, established_round=round_number,
        ).select_related('market', 'entry_mode')
        for entry in new_entries:
            mode_name = (get_localized_field(entry.entry_mode, 'name', language)
                         if entry.entry_mode
                         else _t(language, 'briefing_unknown_mode'))
            moves.append(_t(
                language, 'briefing_move_entered',
                market=get_localized_field(entry.market, 'name', language),
                mode=mode_name))

        new_acqs = TeamAcquisition.objects.filter(team=other, acquired_round=round_number)
        for acq in new_acqs:
            moves.append(_t(
                language, 'briefing_move_acquired',
                target=get_localized_field(
                    acq.acquisition_target, 'target_name', language)))

        if moves:
            landscape['competitor_moves'].append({'team': other.name, 'moves': moves})

    # Narrative
    parts = []
    if landscape['rank_change'] > 0:
        parts.append(_t(language, 'briefing_rank_climbed',
                        places=landscape['rank_change'],
                        rank=landscape['your_rank']))
    elif landscape['rank_change'] < 0:
        parts.append(_t(language, 'briefing_rank_dropped',
                        places=abs(landscape['rank_change']),
                        rank=landscape['your_rank']))
    else:
        parts.append(_t(language, 'briefing_rank_held',
                        rank=landscape['your_rank']))

    for cm in landscape['competitor_moves']:
        parts.append(_t(language, 'briefing_competitor_moves',
                        team=cm['team'], moves='; '.join(cm['moves'])))

    landscape['narrative'] = ' '.join(parts)
    return landscape


# ─── Strategic Recommendations ────────────────────────────────────────────

def _generate_recommendations(game, team, round_number, current, previous, performance, investments, investor_sent, scenario, language='en'):
    if not current or not current['financials']:
        return []

    recommendations = []
    f = current['financials']

    # 1. Segment opportunity — distinguish universal gaps from team-specific weaknesses
    weak_segs = [s for s in performance.get('segment_performance', []) if s['position'] == 'weak']
    if weak_segs:
        w = weak_segs[0]
        # Check if this is an industry-wide gap: are ALL teams weak on this segment?
        #
        # Found by id, not by the displayed name: the name follows the
        # reader now, and matching a localised string against the stored
        # English one made the gap check silently miss on a Chinese team
        # (W-CE3-11).
        from core.models.scenario import SegmentDefinition
        seg_def = SegmentDefinition.objects.filter(
            scenario=scenario, pk=w.get('segment_id'),
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
                'title': _t(language, 'briefing_rec_first_mover_title',
                            segment=w['segment']),
                'detail': _t(language, 'briefing_rec_first_mover_detail',
                             segment=w['segment']),
                'action_page': _t(
                    language, 'briefing_page_market_research_segments'),
            })
        else:
            recommendations.append({
                'priority': 'high',
                'category': 'market',
                'title': _t(language, 'briefing_rec_improve_fit_title',
                            segment=w['segment']),
                'detail': _t(language, 'briefing_rec_improve_fit_detail',
                             segment=w['segment'], market=w['market'],
                             fit=w['fit']),
                'action_page': _t(
                    language, 'briefing_page_market_research_segments'),
            })

    # 2. Financial health
    d_e = float(f.debt_to_equity or 0)
    cash_ratio = float(f.cash_closing or 0) / max(float(f.total_revenue or 1), 1)

    if d_e > 1.0:
        recommendations.append({
            'priority': 'high',
            'category': 'finance',
            'title': _t(language, 'briefing_rec_reduce_leverage_title'),
            'detail': _t(language, 'briefing_rec_reduce_leverage_detail',
                         ratio=f'{d_e:.2f}'),
            'action_page': _t(language, 'briefing_page_finance_capital'),
        })
    elif cash_ratio > 3.0:
        recommendations.append({
            'priority': 'medium',
            'category': 'finance',
            'title': _t(language, 'briefing_rec_deploy_cash_title'),
            'detail': _t(language, 'briefing_rec_deploy_cash_detail',
                         cash=f'${float(f.cash_closing) / 1e6:.0f}M',
                         ratio=f'{cash_ratio:.0f}'),
            'action_page': _t(language, 'briefing_page_finance_budget'),
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
                'title': _t(language, 'briefing_rec_esg_critical_title'),
                'detail': _t(language, 'briefing_rec_esg_critical_detail'),
                'action_page': _t(language, 'briefing_page_corporate_esg'),
            })
        else:
            recommendations.append({
                'priority': 'medium',
                'category': 'strategy',
                'title': _t(language, 'briefing_rec_esg_consider_title'),
                'detail': _t(language, 'briefing_rec_esg_consider_detail'),
                'action_page': _t(language, 'briefing_page_corporate_esg'),
            })

    # 4. Talent
    rd_talent = current.get('talent', {}).get('rd')
    if rd_talent and float(rd_talent.talent_level) <= 3.0:
        recommendations.append({
            'priority': 'medium',
            'category': 'capability',
            'title': _t(language, 'briefing_rec_rd_talent_title'),
            'detail': _t(language, 'briefing_rec_rd_talent_detail'),
            'action_page': _t(language, 'briefing_page_corporate_talent'),
        })

    # 5. Market expansion
    market_count = TeamMarketPresence.objects.filter(team=team, status='active').count()
    if market_count == 1 and float(f.cash_closing or 0) > 15_000_000:
        recommendations.append({
            'priority': 'medium',
            'category': 'growth',
            'title': _t(language, 'briefing_rec_expansion_title'),
            # The $500K is the literal this sentence has always carried; it
            # is not read from the scenario, and moving the sentence into the
            # catalogue does not change that. Reported as a finding.
            'detail': _t(language, 'briefing_rec_expansion_detail',
                         cash=f'${float(f.cash_closing) / 1e6:.0f}M'),
            'action_page': _t(language, 'briefing_page_market_strategy'),
        })

    # 6. Investor-driven
    sellers = [i for i in investor_sent.get('investors', []) if i['action'] == 'sold']
    if sellers:
        seller = sellers[0]
        recommendations.append({
            'priority': 'medium',
            'category': 'investor_relations',
            'title': _t(language, 'briefing_rec_investor_title',
                        name=seller['name']),
            'detail': _t(language, 'briefing_rec_investor_detail',
                         name=seller['name']),
            'action_page': _t(language, 'briefing_page_investor_relations'),
        })

    # RAG enhancement for top 2
    for rec in recommendations[:2]:
        enhanced = _rag_enhance_recommendation(rec, scenario, language)
        if enhanced:
            rec['framework_reference'] = enhanced

    # Sort by priority, limit to 5
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    recommendations.sort(key=lambda r: priority_order.get(r['priority'], 2))
    return recommendations[:5]


def _rag_enhance_recommendation(recommendation, scenario, language='en'):
    """Add a framework reference from the RAG corpus.

    The sentence it returns is shown under the recommendation, so the model
    is asked for it in the team's language -- the same instruction the
    teaching-note path already uses (W-CE3-11).
    """
    try:
        from core.rag.embeddings import get_embedding
        from core.rag.client import search_articles
        from django.conf import settings
        import time

        query = f"{recommendation['title']}: {recommendation['detail'][:100]}"
        embedding = get_embedding(query)
        results = search_articles(embedding, limit=1)

        from core.engine import llm_runner
        from core.engine.llm_runner import build_language_instruction
        if not results or not llm_runner.llm_configured():
            return None

        time.sleep(0.3)
        return llm_runner.chat_completion(
            model=llm_runner.model_for_purpose('briefing_framework'),
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
                        + build_language_instruction(language)
                    ),
                },
            ],
            max_tokens=60,
            temperature=0.3,
            timeout=5,
        )
    except Exception:
        return None


# ─── Risk Alerts ──────────────────────────────────────────────────────────

def _generate_risk_alerts(team, current, language='en'):
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
                'title': _t(language, 'briefing_risk_runway_critical_title',
                            runway=f'{runway:.1f}'),
                'detail': _t(language, 'briefing_risk_runway_critical_detail',
                             burn=_money(burn), runway=f'{runway:.1f}'),
            })
        elif runway < 6:
            alerts.append({
                'severity': 'warning',
                'title': _t(language, 'briefing_risk_runway_warning_title',
                            runway=f'{runway:.1f}'),
                'detail': _t(language,
                             'briefing_risk_runway_warning_detail'),
            })

    # Interest burden
    interest = float(f.interest_expense or 0)
    oi = float(f.operating_income or 0)
    if interest > 0:
        coverage = oi / interest
        if coverage < 2:
            alerts.append({
                'severity': 'warning',
                'title': _t(language, 'briefing_risk_interest_title',
                            coverage=f'{coverage:.1f}'),
                'detail': _t(language, 'briefing_risk_interest_detail'),
            })

    # Market concentration
    market_count = TeamMarketPresence.objects.filter(team=team, status='active').count()
    lb = current.get('leaderboard')
    if market_count == 1 and lb and lb.rank >= 3:
        alerts.append({
            'severity': 'info',
            'title': _t(language, 'briefing_risk_concentration_title'),
            'detail': _t(language, 'briefing_risk_concentration_detail'),
        })

    # Talent turnover
    for pool, state in current.get('talent', {}).items():
        if hasattr(state, 'turnover_rate') and float(state.turnover_rate) > 0.20:
            alerts.append({
                'severity': 'warning',
                'title': _t(language, 'briefing_risk_turnover_title',
                            pool=_pool_label(pool, language),
                            pct=f'{float(state.turnover_rate) * 100:.0f}'),
                'detail': _t(language, 'briefing_risk_turnover_detail'),
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
                'title': _t(language, 'briefing_risk_inventory_title',
                            product=pr.team_product.name,
                            market=get_localized_field(
                                pr.market, 'name', language)),
                'detail': _t(language, 'briefing_risk_inventory_detail',
                             pct=f'{pct:.0f}'),
            })

    return alerts


def _fit_label(score, language='en'):
    if score >= 0.7:
        key = 'briefing_fit_strong'
    elif score >= 0.5:
        key = 'briefing_fit_moderate'
    elif score >= 0.3:
        key = 'briefing_fit_weak'
    else:
        key = 'briefing_fit_very_weak'
    return _t(language, key)


# The three stakeholder groups the briefing names, and the three talent pools.
# A type or pool the catalogue has not been taught keeps its own token
# prettified, so a scenario that adds one renders a readable word rather than
# an empty one.
_GROUP_KEYS = {
    'investor': 'briefing_group_investors',
    'regulator': 'briefing_group_regulators',
    'channel_partner': 'briefing_group_channel_partners',
}
_POOL_KEYS = {
    'rd': 'briefing_pool_rd',
    'commercial': 'briefing_pool_commercial',
    'operations': 'briefing_pool_operations',
}


def _group_label(segment_type, language='en'):
    key = _GROUP_KEYS.get(segment_type)
    if key is None:
        return (segment_type or '').replace('_', ' ')
    return _t(language, key)


def _pool_label(pool, language='en'):
    key = _POOL_KEYS.get(pool)
    if key is None:
        return (pool or '').replace('_', ' ').title()
    return _t(language, key)
