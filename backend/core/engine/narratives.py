"""
CC-32H: Phase 2 Narrative Generation.

All LLM calls for a round are batched and fired concurrently.
Called from a background thread after Phase 1 completes.
"""
import json
import logging
from decimal import Decimal

from django.conf import settings

from core.models.core import Game, Team, Round
from core.models.results_financials import (
    RoundResultFinancials, RoundResultCoherence, MarketIntelligenceBrief,
)
from core.engine.llm_runner import build_language_instruction
from core.utils.localization import get_team_language, get_instructor_language

logger = logging.getLogger('narratives')

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

BRIEFING_SYSTEM_PROMPT = (
    "You are a strategic advisor writing a quarterly briefing for a "
    "multinational corporation's leadership team. Write 3-5 paragraphs "
    "covering financial performance, market position, competitive dynamics, "
    "and strategic recommendations. Be specific with numbers. "
    "Professional, analytical tone."
)

COHERENCE_SYSTEM_PROMPT = (
    "You are a strategic management professor evaluating a company's "
    "strategic coherence. Score the strategy from 0-100 and provide "
    "2-3 sentences of feedback. Respond ONLY in valid JSON: "
    '{"score": <int 0-100>, "feedback": "<string>"}'
)

COACHING_SYSTEM_PROMPT = (
    "You are an MBA instructor writing a coaching note for a student team "
    "playing a global strategy simulation. Identify 1-2 teaching moments "
    "from their round results. Be constructive and specific. 3-5 sentences."
)

OUTLOOK_SYSTEM_PROMPT = (
    "You are a market analyst enhancing a market outlook brief with "
    "insights from strategic research. Add 2-3 sentences of strategic "
    "context grounded in the research. Maintain a professional, "
    "analytical tone. Do not cite sources by name."
)


def generate_round_narratives(game, round_obj):
    """
    Generate all LLM content for the round concurrently.
    Called from Phase 2 background thread.
    """
    from core.engine.llm_runner import run_llm_batch_sync

    if not getattr(settings, 'DASHSCOPE_API_KEY', ''):
        logger.info("No DASHSCOPE_API_KEY — using fallbacks only")
        _generate_all_fallbacks(game, round_obj)
        return

    teams = list(Team.objects.filter(game=game))
    round_number = round_obj.round_number

    calls = []

    # 1. Strategic briefings (1 per team)
    for team in teams:
        prompt = _build_briefing_prompt(game, round_number, team)
        if prompt:
            calls.append({
                'id': f'briefing_{team.id}',
                'prompt': prompt,
                'system_prompt': BRIEFING_SYSTEM_PROMPT,
                'max_tokens': 2000,
            })

    # 2. Coherence RAG evaluation (1 per team)
    for team in teams:
        prompt = _build_coherence_prompt(game, round_number, team)
        if prompt:
            calls.append({
                'id': f'coherence_{team.id}',
                'prompt': prompt,
                'system_prompt': COHERENCE_SYSTEM_PROMPT,
                'max_tokens': 800,
            })

    # 3. Instructor coaching alerts (1 per team)
    for team in teams:
        prompt = _build_coaching_prompt(game, round_number, team)
        if prompt:
            calls.append({
                'id': f'coaching_{team.id}',
                'prompt': prompt,
                'system_prompt': COACHING_SYSTEM_PROMPT,
                'max_tokens': 600,
            })

    # 4. Market outlook enhancement (1 per market with base narrative)
    outlook_calls = _build_outlook_calls(game, round_number)
    calls.extend(outlook_calls)

    if not calls:
        logger.info("Phase 2: no LLM calls needed")
        return

    logger.info(f"Phase 2: dispatching {len(calls)} LLM calls concurrently")
    results = run_llm_batch_sync(calls)

    # Store results
    _store_briefing_results(game, round_obj, teams, results)
    _store_coherence_results(game, round_number, teams, results)
    _store_coaching_results(game, round_number, teams, results)
    _store_outlook_results(game, round_number, results, outlook_calls)

    successful = sum(1 for r in results.values() if r.get('success'))
    logger.info(f"Phase 2: {successful}/{len(calls)} LLM calls succeeded")


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_briefing_prompt(game, round_number, team):
    """Build a strategic briefing prompt from financial data."""
    fin = RoundResultFinancials.objects.filter(
        game=game, team=team, round_number=round_number,
    ).first()
    if not fin:
        return None

    prev_fin = RoundResultFinancials.objects.filter(
        game=game, team=team, round_number=round_number - 1,
    ).first()

    rev_change = ""
    if prev_fin and prev_fin.total_revenue and prev_fin.total_revenue > 0:
        pct = (float(fin.total_revenue or 0) - float(prev_fin.total_revenue)) / float(prev_fin.total_revenue) * 100
        rev_change = f"Revenue changed {pct:+.1f}% from last quarter."

    # CC-35: Inject situation-specific strategy context
    from core.engine.strategy_advisory import build_strategy_context
    strategy_ctx = build_strategy_context(team, game, round_number)
    strategy_block = f"\n\n{strategy_ctx}\n\n" if strategy_ctx else "\n"

    language = get_team_language(team)
    return (
        f"Company: {team.name}\n"
        f"Round: {round_number}\n"
        f"Revenue: ${float(fin.total_revenue or 0):,.0f}\n"
        f"Net Income: ${float(fin.net_income or 0):,.0f}\n"
        f"Cash: ${float(fin.cash_closing or 0):,.0f}\n"
        f"Total Equity: ${float(fin.total_equity or 0):,.0f}\n"
        f"Total Debt: ${float(fin.total_debt or 0):,.0f}\n"
        f"Share Price: ${float(getattr(team, 'share_price', 0) or 0):,.2f}\n"
        f"{rev_change}"
        f"{strategy_block}"
        f"Write a strategic briefing analyzing performance and recommending next steps."
        + build_language_instruction(language)
    )


def _build_coherence_prompt(game, round_number, team):
    """Build coherence evaluation prompt from decision data."""
    coherence = RoundResultCoherence.objects.filter(
        game=game, round_number=round_number, team=team,
    ).first()
    if not coherence:
        return None

    breakdown = coherence.breakdown or {}
    formula = float(coherence.formula_score)

    summary_parts = [f"Formula coherence score: {formula:.1f}/100"]
    for dim, data in breakdown.items():
        if isinstance(data, dict) and 'score' in data:
            summary_parts.append(f"  {dim}: {data['score']:.2f}")

    # CC-35: Inject situation-specific strategy context
    from core.engine.strategy_advisory import build_strategy_context
    strategy_ctx = build_strategy_context(team, game, round_number)
    strategy_block = f"\n\n{strategy_ctx}\n\n" if strategy_ctx else "\n\n"

    language = get_team_language(team)
    summary_text = '\n'.join(summary_parts)
    return (
        f"Team: {team.name}\n"
        f"Round: {round_number}\n"
        f"{summary_text}"
        f"{strategy_block}"
        f"Evaluate this team's strategic coherence. Consider whether their "
        f"pricing, distribution, R&D, and financial decisions are aligned."
        + build_language_instruction(language)
    )


def _build_coaching_prompt(game, round_number, team):
    """Build instructor coaching prompt."""
    fin = RoundResultFinancials.objects.filter(
        game=game, team=team, round_number=round_number,
    ).first()
    if not fin:
        return None

    # CC-35: Inject situation-specific strategy context
    from core.engine.strategy_advisory import build_strategy_context
    strategy_ctx = build_strategy_context(team, game, round_number)
    strategy_block = f"\n{strategy_ctx}\n" if strategy_ctx else ""

    # Coaching alerts are instructor-facing — use instructor's language
    language = get_instructor_language(game)
    return (
        f"Team: {team.name}, Round: {round_number}\n"
        f"Revenue: ${float(fin.total_revenue or 0):,.0f}, "
        f"Net Income: ${float(fin.net_income or 0):,.0f}, "
        f"Cash: ${float(fin.cash_closing or 0):,.0f}\n"
        f"{strategy_block}"
        f"Identify 1-2 teaching moments from these results."
        + build_language_instruction(language)
    )


def _build_outlook_calls(game, round_number):
    """Build market outlook enhancement calls."""
    from core.models.scenario import MarketDefinition, MarketConditionByRound

    calls = []
    next_round = round_number + 1
    scenario = game.scenario
    markets = MarketDefinition.objects.filter(scenario=scenario)

    for market in markets:
        condition = MarketConditionByRound.objects.filter(
            market=market, round_number=next_round,
        ).first()
        if not condition or not condition.market_outlook_narrative:
            continue

        base = condition.market_outlook_narrative
        calls.append({
            'id': f'outlook_{market.code}',
            'prompt': (
                f"Base outlook for {market.name}:\n{base}\n\n"
                f"Enhance this outlook with strategic insights."
            ),
            'system_prompt': OUTLOOK_SYSTEM_PROMPT,
            'max_tokens': 250,
            '_market_code': market.code,
            '_market_id': market.id,
            '_base_narrative': base,
        })

    return calls


# ---------------------------------------------------------------------------
# Result storage
# ---------------------------------------------------------------------------

def _store_briefing_results(game, round_obj, teams, results):
    """Store strategic briefings for each team."""
    from core.models.cc27_models import StrategicBriefing

    round_number = round_obj.round_number
    for team in teams:
        result = results.get(f'briefing_{team.id}', {})
        if result.get('success') and result.get('content'):
            briefing_data = _build_briefing_fields(
                game, round_number, team, llm_text=result['content'],
            )
        else:
            briefing_data = _build_briefing_fields(
                game, round_number, team, llm_text=None,
            )

        try:
            StrategicBriefing.objects.update_or_create(
                game=game, team=team, round_number=round_number,
                defaults=briefing_data,
            )
        except Exception as e:
            logger.error(f"Failed to store briefing for {team.name}: {e}")


def _store_coherence_results(game, round_number, teams, results):
    """Update coherence scores with RAG component."""
    from core.engine.coherence import update_coherence_with_rag

    for team in teams:
        result = results.get(f'coherence_{team.id}', {})
        if result.get('success') and result.get('content'):
            try:
                update_coherence_with_rag(game, round_number, team, result['content'])
            except Exception as e:
                logger.error(f"Failed to update coherence RAG for {team.name}: {e}")


def _store_coaching_results(game, round_number, teams, results):
    """Store instructor coaching alerts."""
    try:
        from core.models.cc21_models import InstructorAlert
    except ImportError:
        return

    for team in teams:
        result = results.get(f'coaching_{team.id}', {})
        if result.get('success') and result.get('content'):
            try:
                InstructorAlert.objects.update_or_create(
                    game=game, team=team, round_number=round_number,
                    alert_type='coaching',
                    defaults={
                        'title': f'Round {round_number} Coaching Note',
                        'detail': result['content'],
                        'severity': 'info',
                        'teaching_note': result['content'],
                    },
                )
            except Exception as e:
                logger.error(f"Failed to store coaching alert for {team.name}: {e}")


def _store_outlook_results(game, round_number, results, outlook_calls):
    """Store enhanced market outlooks."""
    next_round = round_number + 1

    for call in outlook_calls:
        market_id = call.get('_market_id')
        base = call.get('_base_narrative', '')
        result = results.get(call['id'], {})

        if result.get('success') and result.get('content'):
            content = base + "\n\n" + result['content']
            level = 'standard'
        else:
            content = base
            level = 'basic'

        try:
            MarketIntelligenceBrief.objects.update_or_create(
                game=game, round_number=next_round,
                team=None, market_id=market_id,
                defaults={
                    'research_spend': Decimal('0'),
                    'brief_level': level,
                    'brief_content': content,
                },
            )
        except Exception as e:
            logger.error(f"Failed to store outlook for market {market_id}: {e}")


# ---------------------------------------------------------------------------
# Fallbacks
# ---------------------------------------------------------------------------

def _build_briefing_fields(game, round_number, team, llm_text=None):
    """
    Build the structured dict that matches StrategicBriefing model fields.
    If llm_text is provided, use it as the executive_summary and populate
    other fields from financial data. Otherwise build a deterministic fallback.
    """
    fin = RoundResultFinancials.objects.filter(
        game=game, team=team, round_number=round_number,
    ).first()
    prev_fin = RoundResultFinancials.objects.filter(
        game=game, team=team, round_number=round_number - 1,
    ).first()

    revenue = float(fin.total_revenue or 0) if fin else 0
    net_income = float(fin.net_income or 0) if fin else 0
    cash = float(getattr(fin, 'cash_closing', 0) or 0) if fin else 0
    equity = float(fin.total_equity or 0) if fin else 0
    debt = float(fin.total_debt or 0) if fin else 0
    share_price = float(fin.share_price or 0) if fin else 0
    gross_margin = float(fin.gross_margin_pct or 0) if fin else 0
    net_margin = float(fin.net_margin_pct or 0) if fin else 0
    roe = float(fin.roe or 0) if fin else 0

    prev_revenue = float(prev_fin.total_revenue or 0) if prev_fin else 0
    rev_change_pct = None
    if prev_revenue > 0:
        rev_change_pct = round((revenue - prev_revenue) / prev_revenue * 100, 1)

    # Executive summary
    if llm_text:
        executive_summary = llm_text
    else:
        direction = "grew" if (rev_change_pct or 0) > 0 else "declined"
        rev_line = (
            f"Revenue {direction} {abs(rev_change_pct):.1f}% to ${revenue:,.0f}."
            if rev_change_pct is not None
            else f"Revenue: ${revenue:,.0f}."
        )
        executive_summary = (
            f"**Quarter {round_number} Results**\n\n"
            f"{rev_line} Net income: ${net_income:,.0f}. "
            f"Cash position: ${cash:,.0f}."
        )
        if cash < 1_000_000:
            executive_summary += (
                "\n\nCash position below $1M — financial distress risk."
            )

    # Performance analysis
    performance_analysis = {
        'revenue': revenue,
        'net_income': net_income,
        'gross_margin_pct': round(gross_margin * 100, 1),
        'net_margin_pct': round(net_margin * 100, 1),
        'revenue_change_pct': rev_change_pct,
        'rd_expense': float(fin.rd_expense or 0) if fin else 0,
        'marketing_expense': float(fin.marketing_expense or 0) if fin else 0,
        'operating_income': float(fin.operating_income or 0) if fin else 0,
    }

    # Investment returns
    investment_returns = {
        'share_price': share_price,
        'roe': round(roe * 100, 1),
        'shareholder_return_cumulative': round(
            float(fin.shareholder_return_cumulative or 0) * 100, 1
        ) if fin else 0,
        'dividends_paid': float(fin.dividends_paid or 0) if fin else 0,
    }

    # Investor sentiment
    investor_sentiment = {
        'share_price_trend': 'up' if share_price > 40 else ('down' if share_price < 30 else 'stable'),
        'debt_to_equity': round(float(fin.debt_to_equity or 0), 3) if fin else 0,
        'cash_position': cash,
        'is_in_distress': team.is_in_distress,
    }

    # Competitive landscape
    coh = RoundResultCoherence.objects.filter(
        game=game, team=team, round_number=round_number,
    ).first()
    competitive_landscape = {
        'coherence_score': float(coh.blended_score) if coh else None,
        'coherence_breakdown': coh.breakdown if coh else {},
    }

    # Strategic recommendations
    recommendations = []
    if net_income < 0:
        recommendations.append("Reduce operating costs or increase revenue to restore profitability.")
    if cash < 5_000_000:
        recommendations.append("Shore up cash reserves — consider reducing dividends or raising capital.")
    if gross_margin < 0.2:
        recommendations.append("Gross margins are thin — review pricing or COGS structure.")
    if not recommendations:
        recommendations.append("Maintain current trajectory and explore growth opportunities.")
    strategic_recommendations = {'items': recommendations}

    # Risk alerts
    risk_alerts = []
    if cash < 1_000_000:
        risk_alerts.append({'severity': 'critical', 'message': 'Cash below $1M — financial distress imminent.'})
    if revenue > 0 and net_margin < -0.15:
        risk_alerts.append({'severity': 'warning', 'message': f'Net margin at {max(net_margin, -1)*100:.0f}% — losses unsustainable.'})
    elif revenue == 0 and net_income < 0:
        risk_alerts.append({'severity': 'warning', 'message': 'No revenue generated — all spending is a loss.'})
    if debt > equity and equity > 0:
        risk_alerts.append({'severity': 'warning', 'message': 'Debt exceeds equity — leverage risk elevated.'})

    return {
        'executive_summary': executive_summary,
        'performance_analysis': performance_analysis,
        'investment_returns': investment_returns,
        'investor_sentiment': investor_sentiment,
        'competitive_landscape': competitive_landscape,
        'strategic_recommendations': strategic_recommendations,
        'risk_alerts': risk_alerts,
    }


def _generate_fallback_briefing(game, round_number, team):
    """Deterministic briefing from financial data — no LLM required."""
    fin = RoundResultFinancials.objects.filter(
        game=game, team=team, round_number=round_number,
    ).first()

    if not fin:
        return f"**Quarter {round_number} Results**\n\nFinancial data pending."

    revenue = float(fin.total_revenue or 0)
    net_income = float(fin.net_income or 0)
    cash = float(fin.cash_closing or 0)

    prev = RoundResultFinancials.objects.filter(
        game=game, team=team, round_number=round_number - 1,
    ).first()

    if prev and prev.total_revenue and float(prev.total_revenue) > 0:
        change = (revenue - float(prev.total_revenue)) / float(prev.total_revenue)
        direction = "grew" if change > 0 else "declined"
        rev_line = f"Revenue {direction} {abs(change):.1%} to ${revenue:,.0f}."
    else:
        rev_line = f"Revenue: ${revenue:,.0f}."

    lines = [
        f"**Quarter {round_number} Results**",
        "",
        rev_line,
        f"Net income: ${net_income:,.0f}.",
        f"Cash position: ${cash:,.0f}.",
    ]

    if cash < 1_000_000:
        lines.append("\nCash position below $1M — financial distress risk.")

    lines.append("\nFull strategic analysis will be available shortly.")

    return "\n".join(lines)


def _generate_all_fallbacks(game, round_obj):
    """Generate template-based content for all teams when LLM is unavailable."""
    from core.models.cc27_models import StrategicBriefing

    teams = Team.objects.filter(game=game)
    round_number = round_obj.round_number

    for team in teams:
        briefing_data = _build_briefing_fields(
            game, round_number, team, llm_text=None,
        )
        try:
            StrategicBriefing.objects.update_or_create(
                game=game, team=team, round_number=round_number,
                defaults=briefing_data,
            )
        except Exception as e:
            logger.error(f"Fallback briefing failed for {team.name}: {e}")
