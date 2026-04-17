"""
Instructor AI Assistant — Alert Generation Engine.
Generates coaching alerts after round processing and on decision lock.
"""
from decimal import Decimal

from core.models.cc21_models import InstructorAlert
from core.models.core import Game, Team
from core.models.results_financials import (
    RoundResultFinancials, RoundResultPerformanceIndex,
    RoundResultCoherence, RoundResultProductMarket,
)
from core.models.decisions import (
    DecisionSubmission, DecisionRDInvestment, DecisionMarketing,
    DecisionMarketEntry, DecisionBudgetAllocation,
)
from core.models.team_state import TeamMarketPresence
from core.engine.llm_runner import build_language_instruction
from core.utils.localization import get_instructor_language

# Defensive imports for models that may not exist yet (CC-20 parallel)
try:
    from core.models.team_state import TeamAcquisition
except ImportError:
    TeamAcquisition = None

try:
    from core.models.decisions import DecisionESG
except ImportError:
    DecisionESG = None


def _create_alert(game, team, round_number, alert_type, severity, title, detail, teaching_note=''):
    return InstructorAlert(
        game=game, team=team, round_number=round_number,
        alert_type=alert_type, severity=severity,
        title=title, detail=detail, teaching_note=teaching_note,
    )


def _count_rounds_without_rd(team, current_round):
    """Count consecutive rounds (backward from current) with no R&D investment."""
    count = 0
    for rnd_num in range(current_round, -1, -1):
        has_rd = DecisionRDInvestment.objects.filter(
            submission__team=team,
            submission__round__round_number=rnd_num,
            amount__gt=0,
        ).exists()
        if has_rd:
            break
        count += 1
    return count


def generate_post_round_alerts(game, round_number):
    """
    Analyze all teams after a round is processed.
    Generate alerts for the instructor based on patterns.
    """
    teams = Team.objects.filter(game=game)
    alerts = []

    for team in teams:
        financials = RoundResultFinancials.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first()
        prev_financials = RoundResultFinancials.objects.filter(
            game=game, team=team, round_number=round_number - 1,
        ).first()
        performance = RoundResultPerformanceIndex.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first()
        coherence = RoundResultCoherence.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first()

        if not financials:
            continue

        # === FINANCIAL ALERTS ===

        # Cash crisis approaching
        if financials.cash_closing < 5_000_000:
            alerts.append(_create_alert(
                game, team, round_number,
                'financial', 'critical',
                f'{team.name} has only ${financials.cash_closing:,.0f} cash remaining',
                f'At current burn rate, they may run out of cash within 1-2 rounds. '
                f'Debt: ${financials.total_debt:,.0f}, Net Income: ${financials.net_income:,.0f}. '
                f'Watch for distress spiral — teams in financial trouble often make desperate decisions.',
                'This is a teaching moment about cash management and financial planning. '
                'Ask the team: "What was your cash forecast? Did you account for all costs?"'
            ))

        # Excessive debt
        de_ratio = float(financials.debt_to_equity) if financials.debt_to_equity else 0
        if de_ratio > 1.5:
            alerts.append(_create_alert(
                game, team, round_number,
                'financial', 'concern',
                f'{team.name} debt-to-equity ratio at {de_ratio:.2f}',
                f'Total debt: ${financials.total_debt:,.0f}, Equity: ${financials.total_equity:,.0f}. '
                f'Interest expense: ${financials.interest_expense:,.0f}/round. '
                f'This level of leverage limits future borrowing capacity and increases risk.',
                'Discuss the trade-offs of debt vs equity financing. '
                'Reference: Modigliani-Miller theorem and real-world capital structure decisions.'
            ))

        # Revenue declining
        if prev_financials and prev_financials.total_revenue > 0:
            if financials.total_revenue < prev_financials.total_revenue * Decimal('0.90'):
                decline_pct = (1 - float(financials.total_revenue / prev_financials.total_revenue)) * 100
                alerts.append(_create_alert(
                    game, team, round_number,
                    'strategic', 'watch',
                    f'{team.name} revenue declined {decline_pct:.1f}% this round',
                    f'Revenue: ${financials.total_revenue:,.0f} (was ${prev_financials.total_revenue:,.0f}). '
                    f'Check if this is due to pricing, production, market share loss, or currency effects.',
                    'Revenue decline in a growing market suggests competitive pressure. '
                    'Ask: "What changed in your competitive position? Did competitors improve or did you stand still?"'
                ))

        # === STRATEGIC ALERTS ===

        # No R&D investment for 2+ rounds
        rounds_without_rd = _count_rounds_without_rd(team, round_number)
        if rounds_without_rd >= 2:
            alerts.append(_create_alert(
                game, team, round_number,
                'strategic', 'concern',
                f'{team.name} has not invested in R&D for {rounds_without_rd} consecutive rounds',
                f'Their technology capability is stagnating while competitors may be advancing. '
                f'This will erode fit scores with technology-sensitive segments.',
                'Classic short-term thinking trap. Teams sacrifice long-term capability for short-term profits. '
                "Reference: The Innovator's Dilemma — established firms underinvest in innovation."
            ))

        # Only in home market after Round 3
        market_count = TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).count()
        if round_number >= 3 and market_count <= 1:
            alerts.append(_create_alert(
                game, team, round_number,
                'missed_opportunity', 'watch',
                f'{team.name} still operates in only {market_count} market (Round {round_number})',
                f'Remaining in one market limits revenue growth potential '
                f'and increases concentration risk.',
                'Discuss market entry timing. Reference: Uppsala model of internationalization — '
                'firms often delay foreign market entry due to uncertainty, but delay has costs.'
            ))

        # High coherence score (positive)
        if coherence and float(coherence.blended_score) >= 80:
            alerts.append(_create_alert(
                game, team, round_number,
                'notable_move', 'info',
                f'{team.name} achieved a coherence score of {float(coherence.blended_score):.0f}/100',
                f'Their strategy is internally consistent. Pricing aligns with positioning, '
                f'distribution matches segments, entry modes match risk profiles.',
                'Highlight this in debrief as an example of strategic alignment. '
                'What specific choices created this coherence?'
            ))

        # Performance index dropped significantly
        if performance and float(performance.index_change) < -3:
            alerts.append(_create_alert(
                game, team, round_number,
                'strategic', 'concern',
                f'{team.name} performance index dropped {abs(float(performance.index_change)):.1f} points',
                f'Index: {float(performance.index_value):.2f} '
                f'(was {float(performance.index_value - performance.index_change):.2f}). '
                f'Satisfaction score: {float(performance.satisfaction_score):.3f}.',
                'A sharp index drop indicates multiple stakeholder groups are dissatisfied simultaneously. '
                'This team may be spreading too thin or making contradictory decisions.'
            ))

        # === TEACHING MOMENTS ===

        # First acquisition (defensive — TeamAcquisition may not exist)
        if TeamAcquisition is not None:
            try:
                new_acquisition = TeamAcquisition.objects.filter(
                    team=team, acquired_round=round_number,
                ).select_related('acquisition_target').first()
                if new_acquisition:
                    alerts.append(_create_alert(
                        game, team, round_number,
                        'notable_move', 'info',
                        f'{team.name} acquired {new_acquisition.acquisition_target.target_name}',
                        f'Cost: ${new_acquisition.total_cost_paid:,.0f}. '
                        f'Integration will take {new_acquisition.integration_rounds_remaining} rounds.',
                        'Good opportunity to discuss M&A strategy: was this acquisition value-creating? '
                        'What synergies does the team expect? How will integration costs affect near-term performance?'
                    ))
            except Exception:
                pass  # Table may not exist yet

        # Entered new market
        new_entries = DecisionMarketEntry.objects.filter(
            submission__team=team,
            submission__round__round_number=round_number,
            action='enter',
        ).select_related('market', 'entry_mode')
        for entry in new_entries:
            market = entry.market
            mode_name = entry.entry_mode.name if entry.entry_mode else 'unknown mode'
            growth_rate = float(market.growth_rate_base) * 100 if hasattr(market, 'growth_rate_base') else 0
            tariff_rate = float(market.tariff_rate) * 100 if hasattr(market, 'tariff_rate') else 0
            alerts.append(_create_alert(
                game, team, round_number,
                'notable_move', 'info',
                f'{team.name} entered {market.name} via {mode_name}',
                f'Investment: ${entry.initial_investment:,.0f}. '
                f'This market has {growth_rate:.0f}% growth rate '
                f'and {tariff_rate:.0f}% tariff rate.',
                "Discuss entry mode choice. Was this the right fit for the market's risk profile? "
                "Reference: Dunning's OLI framework for entry mode selection."
            ))

    # Save all alerts
    InstructorAlert.objects.bulk_create(alerts)
    return len(alerts)


def generate_pre_lock_alerts(game, team, submission):
    """
    Generate alerts when a team locks their decisions.
    Catches obvious mistakes before round processing.
    """
    alerts = []

    # Check: production volume far exceeds historical sales
    for mktg in DecisionMarketing.objects.filter(submission=submission).select_related('team_product', 'market'):
        prev_result = RoundResultProductMarket.objects.filter(
            game=game, team=team,
            team_product=mktg.team_product, market=mktg.market,
            round_number=game.current_round - 1,
        ).first()
        if prev_result and prev_result.units_sold > 0:
            if mktg.production_volume > float(prev_result.units_sold) * 2:
                alerts.append(_create_alert(
                    game, team, game.current_round,
                    'financial', 'watch',
                    f'{team.name} producing 2x+ last round sales for {mktg.team_product.name} in {mktg.market.name}',
                    f'Production: {mktg.production_volume:,} units. Last round sold: {int(prev_result.units_sold):,}. '
                    f'This may result in significant unsold inventory.',
                    ''
                ))

    InstructorAlert.objects.bulk_create(alerts)
    return alerts


def _get_strategy_context_for_alert(alert):
    """CC-35: Build strategy context for teaching note enhancement."""
    try:
        if alert.team and alert.game:
            from core.engine.strategy_advisory import build_strategy_context
            ctx = build_strategy_context(alert.team, alert.game)
            if ctx:
                return f'{ctx}\n\n'
    except Exception:
        pass
    return ''


def enhance_teaching_note_with_rag(alert):
    """
    Use the RAG layer to provide framework-grounded teaching suggestions.
    Called for 'concern' and 'critical' severity alerts.
    """
    if alert.severity not in ('concern', 'critical'):
        return

    try:
        from core.rag.embeddings import get_embedding
        from core.rag.client import search_articles
    except ImportError:
        return

    try:
        query = f"Teaching strategy for: {alert.title}"
        embedding = get_embedding(query)
        results = search_articles(embedding, limit=2)

        if not results:
            return

        from django.conf import settings
        api_key = getattr(settings, 'DASHSCOPE_API_KEY', None)
        if not api_key:
            return

        import dashscope
        from dashscope import Generation
        dashscope.api_key = api_key

        context_text = '\n'.join([r['text'][:300] for r in results])

        # Teaching notes are instructor-facing — use instructor's language
        language = get_instructor_language(alert.game) if alert.game else 'en'
        lang_instruction = build_language_instruction(language)

        response = Generation.call(
            model=getattr(settings, 'DASHSCOPE_MODEL', 'qwen3-max-preview'),
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are an experienced business strategy professor. '
                        'Given a student team situation and relevant research, '
                        'provide a concise teaching note (2-3 sentences) that the instructor '
                        'can use in class discussion. Reference specific frameworks or concepts. '
                        'Write as a peer note to the instructor, not as advice to students.'
                    ),
                },
                {
                    'role': 'user',
                    'content': (
                        f'Situation: {alert.title}\n'
                        f'Detail: {alert.detail}\n\n'
                        + _get_strategy_context_for_alert(alert)
                        + f'Relevant research:\n{context_text}'
                        + lang_instruction
                    ),
                },
            ],
            max_tokens=150,
            temperature=0.3,
        )

        alert.teaching_note = (alert.teaching_note + '\n\n' + response.output.text).strip()
        alert.save()

    except Exception as e:
        print(f"RAG teaching note enhancement failed: {e}")
