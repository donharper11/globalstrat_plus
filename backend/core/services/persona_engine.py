"""
Post-Round AI Persona Reaction Engine.

After each round advances, evaluates outcomes and generates contextual messages
from 5 AI personas via the DashScope (Qwen) LLM API.
"""
import logging
import os
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import requests
from django.utils import timezone

from core.models import (
    Team, Round, SimulationState,
    TeamIncomeStatement, TeamBalanceSheet, TeamCashFlow,
    Program, ProgramType,
    Score,
    # TODO: GlobalStrat — update to use new scenario models (CC-3)
    # Removed: Segment, SegmentPreference
    LeaderboardScore, TeamPerformance,
    TriggeredEvent,
)
# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# Removed: ESGScorecard, BCorpMilestone, BCorpCertification, Competitor, EthicalDecision
from core.models.messaging import Message
from core.services.textbook_retrieval import (
    get_context_for_persona, get_context_for_student_query,
)

logger = logging.getLogger(__name__)

from core.engine.llm_runner import build_language_instruction
from core.utils.localization import get_team_language

from django.conf import settings
DASHSCOPE_MODEL = getattr(settings, 'DASHSCOPE_MODEL', 'qwen3-max-preview')
DASHSCOPE_BASE_URL = getattr(settings, 'DASHSCOPE_COMPATIBLE_URL',
    'https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions')
MAX_TOKENS = 500
TEMPERATURE = 0.8
LLM_TIMEOUT = 10  # seconds
INTER_CALL_DELAY = 0.5  # seconds between LLM calls
MAX_MESSAGES_PER_TEAM = 3

SEVERITY_NONE = 'NONE'
SEVERITY_LOW = 'LOW'
SEVERITY_MEDIUM = 'MEDIUM'
SEVERITY_HIGH = 'HIGH'

SEVERITY_PRIORITY = {SEVERITY_HIGH: 3, SEVERITY_MEDIUM: 2, SEVERITY_LOW: 1, SEVERITY_NONE: 0}

# Persona priority for tie-breaking (higher = more important)
PERSONA_PRIORITY = {
    'board_chair': 5,
    'cfo': 4,
    'regulatory': 3,
    'stakeholder': 2,
    'sustainability': 1,
}

ESCALATION_NOTES = {
    1: "This is Round 1 — the very beginning. Send only a welcome message.",
    2: "Early game. Teams are just getting started. Only flag critical issues.",
    3: "Early game. Keep observations calm and constructive.",
    4: "Mid-game. Patterns are emerging. Reference multi-round trends where relevant.",
    5: "Mid-game. Stakes are rising. Be more direct about concerns.",
    6: "Mid-game. Halfway point. Teams should have clear strategies by now.",
    7: "Mid-game. Strategies should be maturing. Reference competitive positioning.",
    8: "Late game. Time is running short. B-Corp deadlines loom. Sharpen your tone.",
    9: "Late game. Only 2 rounds left. Urgency is appropriate.",
    10: "Final round. This is the last chance. Maximum urgency. Speak to what the team's record will show.",
}

SEVERITY_TONE = {
    SEVERITY_LOW: "Brief, calm acknowledgment. One short paragraph.",
    SEVERITY_MEDIUM: "Substantive concern with specific data references. 1-2 paragraphs.",
    SEVERITY_HIGH: "Pointed challenge demanding attention. 2-3 paragraphs. Direct and urgent.",
}


@dataclass
class ReactionDecision:
    severity: str = SEVERITY_NONE
    trigger_reason: str = ''
    data_context: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Persona definitions
# ---------------------------------------------------------------------------

PERSONAS = {
    'cfo': {
        'name': 'Victoria Chen',
        'title': 'Chief Financial Officer',
        'personality': (
            'Numbers-driven, direct, pragmatic. Not hostile but does not sugarcoat. '
            'Speaks in financial terms. References specific figures from the data.'
        ),
        'avatar': '/static/avatars/cfo_victoria_chen.png',
    },
    'sustainability': {
        'name': 'Dr. Marcus Webb',
        'title': 'External Sustainability Consultant',
        'personality': (
            'Passionate about ESG but realistic. Encourages but also challenges greenwashing. '
            'Academic but accessible. References environmental science and sustainability frameworks.'
        ),
        'avatar': '/static/avatars/sustainability_marcus_webb.png',
    },
    'stakeholder': {
        'name': 'Amara Okafor',
        'title': 'Segment Relations Officer',
        'personality': (
            'Empathetic, politically aware, speaks for the stakeholders who cannot speak for themselves. '
            'Brings human stories to data. References community impact and social responsibility.'
        ),
        'avatar': '/static/avatars/stakeholder_amara_okafor.png',
    },
    'regulatory': {
        'name': 'Jonathan Park',
        'title': 'Regulatory Affairs Director',
        'personality': (
            'Formal, measured, legalistic. Not threatening but carries authority. '
            'References compliance frameworks and governance standards.'
        ),
        'avatar': '/static/avatars/regulatory_jonathan_park.png',
    },
    'board_chair': {
        'name': 'Eleanor Whitfield',
        'title': 'Chairperson of the Board',
        'personality': (
            'Strategic, big-picture, commanding. Speaks rarely but with weight. '
            'Compares team to competitors. Increasingly urgent toward endgame.'
        ),
        'avatar': '/static/avatars/board_chair_eleanor_whitfield.png',
    },
}


# ---------------------------------------------------------------------------
# Helper: fetch data for a team/round
# ---------------------------------------------------------------------------

def _get_team_name(team_id):
    team = Team.objects.filter(team_id=team_id).first()
    return team.team_name if team and team.team_name else f"Team {team_id}"


def _get_financials(team_id, round_number):
    """Get current and previous round financials."""
    # Get round_ids for current and previous
    current = TeamIncomeStatement.objects.filter(
        team_id=team_id, round_id__isnull=False
    ).order_by('-round_id').first()

    statements = TeamIncomeStatement.objects.filter(
        team_id=team_id
    ).order_by('-round_id')[:2]

    balance = TeamBalanceSheet.objects.filter(
        team_id=team_id
    ).order_by('-balance_id').first()

    cashflow = TeamCashFlow.objects.filter(
        team_id=team_id
    ).order_by('-cashflow_id').first()

    return {
        'income_statements': [
            {
                'round_id': s.round_id,
                'revenue': float(s.revenue or 0),
                'program_expenses': float(s.program_expenses or 0),
                'operating_costs': float(s.operating_costs or 0),
                'net_income': float((s.revenue or 0) - (s.program_expenses or 0) - (s.operating_costs or 0)),
            }
            for s in statements
        ],
        'balance_sheet': {
            'assets': float(balance.assets or 0) if balance else 0,
            'liabilities': float(balance.liabilities or 0) if balance else 0,
        } if balance else None,
        'cash_flow': {
            'inflows': float(cashflow.cash_inflows or 0) if cashflow else 0,
            'outflows': float(cashflow.cash_outflows or 0) if cashflow else 0,
        } if cashflow else None,
    }


def _get_esg_data(team_id, round_number):
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    return []


def _get_active_programs(team_id):
    """Get active programs with their types."""
    programs = Program.objects.filter(team_id=team_id, status='Active')
    result = []
    for p in programs:
        pt = ProgramType.objects.filter(program_type_id=p.program_type_id).first()
        result.append({
            'program_id': p.program_id,
            'program_name': p.program_name or f"Program {p.program_id}",
            'program_type': pt.program_type_name if pt else 'Unknown',
            'program_type_id': p.program_type_id,
        })
    return result


def _get_stakeholder_scores(team_id, round_number):
    """Get stakeholder alignment scores for current and previous rounds."""
    # Get latest two sets of scores
    scores = Score.objects.filter(
        team_id=team_id, score_type_id=3
    ).order_by('-round_id')

    # Group by round
    by_round = {}
    for s in scores:
        rid = s.round_id
        if rid not in by_round:
            by_round[rid] = []
        # TODO: GlobalStrat — update to use new scenario models (CC-3)
        # Segment model removed — using placeholder name
        by_round[rid].append({
            'segment_id': s.segment_id,
            'segment_name': f"Segment {s.segment_id}",
            'score': float(s.score or 0),
        })

    # Return latest two rounds
    sorted_rounds = sorted(by_round.keys(), reverse=True)[:2]
    return {rid: by_round[rid] for rid in sorted_rounds}


def _get_competitor_scores(round_number):
    """Get competitor scores for comparison."""
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Removed: Competitor model
    return []


def _get_leaderboard(team_id, round_number):
    """Get leaderboard positions for all teams."""
    # Get latest ESG total scores
    latest_scores = {}
    for ls in LeaderboardScore.objects.filter(
        metric_id__in=LeaderboardScore.objects.filter(
            metric_id__isnull=False
        ).values_list('metric_id', flat=True).distinct()
    ).order_by('-round_id'):
        key = (ls.team_id, ls.metric_id)
        if key not in latest_scores:
            latest_scores[key] = float(ls.score or 0)

    # Aggregate by team
    team_totals = {}
    for (tid, mid), score in latest_scores.items():
        team_totals[tid] = team_totals.get(tid, 0) + score

    # Rank
    ranked = sorted(team_totals.items(), key=lambda x: x[1], reverse=True)
    result = []
    for rank, (tid, total) in enumerate(ranked, 1):
        team = Team.objects.filter(team_id=tid).first()
        result.append({
            'rank': rank,
            'team_id': tid,
            'team_name': team.team_name if team and team.team_name else f"Team {tid}",
            'total_score': total,
            'is_current_team': tid == team_id,
        })
    return result


def _get_bcorp_status(team_id, game_id=1):
    """Get B-Corp milestone and certification status."""
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Removed: BCorpMilestone, BCorpCertification models
    return {
        'certified': False,
        'milestones_total': 0,
    }


def _get_triggered_events(round_number, team_id):
    """Get events triggered in the current round."""
    events = TriggeredEvent.objects.filter(
        team_id=team_id
    ).order_by('-triggered_event_id')[:5]
    return [
        {
            'event_id': e.event_id,
            'response_status': 'resolved' if e.resolved else 'pending',
        }
        for e in events
    ]


def _get_ethical_decisions(team_id):
    """Get team's ethical decision alignment scores."""
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Removed: EthicalDecision model
    return []


def _get_governance_programs(team_id):
    """Check if team has active governance programs (type_id=3)."""
    return Program.objects.filter(
        team_id=team_id, status='Active', program_type_id=3
    ).count()


def _get_environmental_programs(team_id):
    """Check if team has active environmental programs (type_id=1)."""
    return Program.objects.filter(
        team_id=team_id, status='Active', program_type_id=1
    ).count()


def _starting_cash():
    """Get starting cash (initial assets from first balance sheet or default)."""
    return 100000.0


# ---------------------------------------------------------------------------
# should_react() per persona
# ---------------------------------------------------------------------------

def _should_react_cfo(team_id, round_number):
    """CFO reacts to financial concerns."""
    financials = _get_financials(team_id, round_number)
    data = {'financials': financials, 'team_name': _get_team_name(team_id)}

    if not financials['income_statements']:
        return ReactionDecision(SEVERITY_NONE)

    current = financials['income_statements'][0]
    previous = financials['income_statements'][1] if len(financials['income_statements']) > 1 else None
    triggers = []

    # Net loss
    if current['net_income'] < 0:
        triggers.append(('HIGH', f"Net loss of ${abs(current['net_income']):,.0f} posted this round"))

    # Cash below 20% of starting
    if financials['balance_sheet']:
        cash = financials['balance_sheet']['assets'] - financials['balance_sheet']['liabilities']
        starting = _starting_cash()
        if cash < starting * 0.20:
            triggers.append(('HIGH', f"Cash position at ${cash:,.0f} — below 20% of starting capital"))

    # Program spending growth > 2x revenue growth
    if previous and previous['revenue'] > 0 and current['revenue'] > 0:
        rev_growth = (current['revenue'] - previous['revenue']) / previous['revenue']
        csr_growth = 0
        if previous['program_expenses'] > 0:
            csr_growth = (current['program_expenses'] - previous['program_expenses']) / previous['program_expenses']
        if csr_growth > rev_growth * 2 and csr_growth > 0.1:
            triggers.append(('MEDIUM', f"Program spending growth ({csr_growth:.0%}) outpacing revenue growth ({rev_growth:.0%}) by more than 2x"))

    # Program costs > 60% of cash
    if financials['balance_sheet']:
        cash = financials['balance_sheet']['assets'] - financials['balance_sheet']['liabilities']
        if cash > 0 and current['program_expenses'] > cash * 0.60:
            triggers.append(('MEDIUM', f"Program costs consuming {current['program_expenses']/cash:.0%} of available cash"))

    if not triggers:
        # Positive acknowledgment if profitable
        if current['net_income'] > 0:
            triggers.append(('LOW', f"Profitable round with ${current['net_income']:,.0f} net income"))

    if not triggers:
        return ReactionDecision(SEVERITY_NONE)

    # Pick highest severity trigger
    triggers.sort(key=lambda t: SEVERITY_PRIORITY.get(t[0], 0), reverse=True)
    best = triggers[0]
    return ReactionDecision(
        severity=best[0],
        trigger_reason=best[1],
        data_context=data,
    )


def _should_react_sustainability(team_id, round_number):
    """Sustainability advisor reacts to ESG trends."""
    esg_data = _get_esg_data(team_id, round_number)
    programs = _get_active_programs(team_id)
    bcorp = _get_bcorp_status(team_id)
    data = {
        'esg_scorecards': esg_data,
        'active_programs': programs,
        'bcorp_status': bcorp,
        'team_name': _get_team_name(team_id),
    }

    if not esg_data:
        return ReactionDecision(SEVERITY_NONE)

    current = esg_data[0]
    previous = esg_data[1] if len(esg_data) > 1 else None
    triggers = []

    # Any pillar dropping
    if previous:
        for pillar in ['environmental', 'social', 'governance']:
            if current[pillar] < previous[pillar] and previous[pillar] > 0:
                drop = previous[pillar] - current[pillar]
                triggers.append(('MEDIUM', f"{pillar.title()} score dropped from {previous[pillar]:.1f} to {current[pillar]:.1f} (-{drop:.1f})"))

    # Imbalance (highest > 2x lowest)
    pillars = [current['environmental'], current['social'], current['governance']]
    non_zero = [p for p in pillars if p > 0]
    if len(non_zero) >= 2:
        if max(non_zero) > min(non_zero) * 2:
            triggers.append(('MEDIUM', f"ESG imbalance detected — highest pillar ({max(non_zero):.1f}) is more than 2x the lowest ({min(non_zero):.1f})"))

    # No environmental programs
    env_count = _get_environmental_programs(team_id)
    if env_count == 0:
        triggers.append(('MEDIUM', "No active environmental programs"))

    if not triggers:
        # Positive if all pillars growing
        if previous and all(current[p] >= previous[p] for p in ['environmental', 'social', 'governance']):
            triggers.append(('LOW', "All ESG pillars holding steady or improving"))

    if not triggers:
        return ReactionDecision(SEVERITY_NONE)

    triggers.sort(key=lambda t: SEVERITY_PRIORITY.get(t[0], 0), reverse=True)
    best = triggers[0]
    return ReactionDecision(severity=best[0], trigger_reason=best[1], data_context=data)


def _should_react_stakeholder(team_id, round_number):
    """Segment relations reacts to satisfaction and adoption."""
    scores_by_round = _get_stakeholder_scores(team_id, round_number)
    competitors = _get_competitor_scores(round_number)
    data = {
        'stakeholder_scores': scores_by_round,
        'competitors': competitors,
        'team_name': _get_team_name(team_id),
    }

    if not scores_by_round:
        return ReactionDecision(SEVERITY_NONE)

    # Get current round scores
    current_round_id = max(scores_by_round.keys())
    current_scores = scores_by_round[current_round_id]
    previous_round_id = min(scores_by_round.keys()) if len(scores_by_round) > 1 else None
    previous_scores = scores_by_round.get(previous_round_id, []) if previous_round_id and previous_round_id != current_round_id else []

    prev_map = {s['segment_id']: s['score'] for s in previous_scores}
    triggers = []

    for s in current_scores:
        # Below 15 danger zone
        if s['score'] < 15:
            triggers.append(('HIGH', f"{s['segment_name']} satisfaction critically low at {s['score']:.1f}"))

        # Dropped > 20% round-over-round
        prev_score = prev_map.get(s['segment_id'])
        if prev_score and prev_score > 0:
            drop_pct = (prev_score - s['score']) / prev_score
            if drop_pct > 0.20:
                triggers.append(('MEDIUM', f"{s['segment_name']} satisfaction dropped {drop_pct:.0%} (from {prev_score:.1f} to {s['score']:.1f})"))

    if not triggers:
        # Positive acknowledgment
        avg = sum(s['score'] for s in current_scores) / max(len(current_scores), 1)
        if avg > 50:
            triggers.append(('LOW', f"Average stakeholder satisfaction at {avg:.1f} — solid position"))

    if not triggers:
        return ReactionDecision(SEVERITY_NONE)

    triggers.sort(key=lambda t: SEVERITY_PRIORITY.get(t[0], 0), reverse=True)
    best = triggers[0]
    return ReactionDecision(severity=best[0], trigger_reason=best[1], data_context=data)


def _should_react_regulatory(team_id, round_number):
    """Regulatory affairs reacts to governance and compliance."""
    esg_data = _get_esg_data(team_id, round_number)
    events = _get_triggered_events(round_number, team_id)
    decisions = _get_ethical_decisions(team_id)
    gov_programs = _get_governance_programs(team_id)
    data = {
        'esg_scorecards': esg_data,
        'triggered_events': events,
        'ethical_decisions': decisions,
        'governance_programs': gov_programs,
        'team_name': _get_team_name(team_id),
    }

    if not esg_data:
        return ReactionDecision(SEVERITY_NONE)

    current = esg_data[0]
    triggers = []

    # Governance below 40
    if current['governance'] < 40 and current['governance'] > 0:
        triggers.append(('HIGH', f"Governance pillar at {current['governance']:.1f} — below regulatory comfort threshold of 40"))

    # No governance programs
    if gov_programs == 0:
        triggers.append(('MEDIUM', "No active governance programs — regulatory exposure is elevated"))

    # Events fired this round
    if events:
        triggers.append(('MEDIUM', f"{len(events)} regulatory/compliance event(s) triggered this round"))

    if not triggers:
        if current['governance'] >= 60:
            triggers.append(('LOW', f"Governance score at {current['governance']:.1f} — in good standing"))

    if not triggers:
        return ReactionDecision(SEVERITY_NONE)

    triggers.sort(key=lambda t: SEVERITY_PRIORITY.get(t[0], 0), reverse=True)
    best = triggers[0]
    return ReactionDecision(severity=best[0], trigger_reason=best[1], data_context=data)


def _should_react_board_chair(team_id, round_number):
    """Board chair reacts to overall position and competitive standing."""
    leaderboard = _get_leaderboard(team_id, round_number)
    bcorp = _get_bcorp_status(team_id)
    perf = TeamPerformance.objects.filter(team_id=team_id).first()
    data = {
        'leaderboard': leaderboard,
        'bcorp_status': bcorp,
        'team_performance': {
            'total_score': float(perf.total_score or 0) if perf else 0,
            'avg_satisfaction': float(perf.average_stakeholder_satisfaction or 0) if perf else 0,
        },
        'team_name': _get_team_name(team_id),
    }

    # Round 1: welcome message only
    if round_number == 1:
        return ReactionDecision(
            severity=SEVERITY_MEDIUM,
            trigger_reason="Welcome message — simulation begins",
            data_context=data,
        )

    triggers = []

    # Find team's rank
    team_rank = None
    total_teams = len(leaderboard) if leaderboard else 0
    for entry in leaderboard:
        if entry.get('is_current_team'):
            team_rank = entry['rank']
            break

    # Last place for 2+ rounds (simplified: just check if last now)
    if team_rank and team_rank == total_teams and total_teams > 1:
        triggers.append(('HIGH', f"Team is ranked last ({team_rank} of {total_teams})"))

    # Late game: No B-Corp progress
    total_rounds = _get_total_rounds()
    if round_number >= total_rounds - 3 and not bcorp.get('certified'):
        triggers.append(('MEDIUM', f"Round {round_number} of {total_rounds} — B-Corp certification not yet achieved"))

    # Endgame pressure (last 2 rounds)
    if round_number >= total_rounds - 1:
        triggers.append(('HIGH', f"Round {round_number} of {total_rounds} — final stretch. Legacy is being written now."))

    if not triggers:
        # Acknowledge strong position
        if team_rank and team_rank == 1 and total_teams > 1:
            triggers.append(('LOW', f"Leading the pack — ranked 1st of {total_teams} teams"))
        elif team_rank:
            triggers.append(('LOW', f"Currently ranked {team_rank} of {total_teams}"))

    if not triggers:
        return ReactionDecision(SEVERITY_NONE)

    triggers.sort(key=lambda t: SEVERITY_PRIORITY.get(t[0], 0), reverse=True)
    best = triggers[0]
    return ReactionDecision(severity=best[0], trigger_reason=best[1], data_context=data)


# Map persona keys to their should_react functions
TRIGGER_FUNCTIONS = {
    'cfo': _should_react_cfo,
    'sustainability': _should_react_sustainability,
    'stakeholder': _should_react_stakeholder,
    'regulatory': _should_react_regulatory,
    'board_chair': _should_react_board_chair,
}


# ---------------------------------------------------------------------------
# Escalation filter: which severities are active per round
# ---------------------------------------------------------------------------

def _active_severities(round_number):
    """Return set of active severities based on round number."""
    if round_number <= 1:
        return set()  # Round 1 = welcome only from board chair
    elif round_number <= 3:
        return {SEVERITY_HIGH}
    elif round_number <= 6:
        return {SEVERITY_MEDIUM, SEVERITY_HIGH}
    else:
        return {SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH}


# ---------------------------------------------------------------------------
# LLM prompt building and API call
# ---------------------------------------------------------------------------

def _build_system_prompt(persona_key, team_name, round_number, severity):
    persona = PERSONAS[persona_key]
    total_rounds = _get_total_rounds()
    escalation_note = ESCALATION_NOTES.get(round_number, f"Round {round_number} of {total_rounds}.")
    severity_desc = SEVERITY_TONE.get(severity, SEVERITY_TONE[SEVERITY_MEDIUM])

    if round_number == 1 and persona_key == 'board_chair':
        return (
            f"You are {persona['name']}, {persona['title']} in a corporate social responsibility simulation.\n\n"
            f"Personality: {persona['personality']}\n\n"
            f"You are writing a welcome message to the team \"{team_name}\" at the start of Round 1 of {total_rounds}.\n\n"
            "Rules:\n"
            "- Stay in character at all times\n"
            "- Welcome the team to the simulation\n"
            "- Set expectations: they are recovering from governance scandals and must rebuild trust\n"
            "- Mention stakeholders, ESG performance, and B-Corp certification as key objectives\n"
            "- Keep it to 2 paragraphs\n"
            "- Do not use bullet points or lists — write in natural prose\n"
            "- Do not use markdown formatting (no asterisks, bold, italic, headers, etc.) — write in plain text only\n"
            "- Never break the fourth wall or mention this is a simulation\n"
        )

    return (
        f"You are {persona['name']}, {persona['title']} in a corporate social responsibility simulation.\n\n"
        f"Personality: {persona['personality']}\n\n"
        f"You are writing a message to the team \"{team_name}\" after Round {round_number} of {total_rounds}.\n\n"
        "Rules:\n"
        "- Stay in character at all times\n"
        "- Reference specific numbers from the data provided\n"
        "- Keep your message to 2-3 paragraphs maximum\n"
        "- Do not use bullet points or lists — write in natural prose\n"
        "- Do not use markdown formatting (no asterisks, bold, italic, headers, etc.) — write in plain text only\n"
        f"- Match your tone to the severity: {severity_desc}\n"
        "- Never break the fourth wall or mention this is a simulation\n"
        f"- If severity is LOW, keep it to one short paragraph\n"
        f"- Round {round_number}/10 context: {escalation_note}\n"
    )


def _build_user_prompt(round_number, trigger_reason, data_context,
                       persona_key=None):
    # Format data as readable text
    data_text = ''
    for key, value in data_context.items():
        if key == 'team_name':
            continue
        if isinstance(value, list):
            data_text += f"\n{key.replace('_', ' ').title()}:\n"
            for item in value:
                if isinstance(item, dict):
                    data_text += '  ' + ', '.join(f"{k}: {v}" for k, v in item.items()) + '\n'
                else:
                    data_text += f"  {item}\n"
        elif isinstance(value, dict):
            data_text += f"\n{key.replace('_', ' ').title()}:\n"
            for k, v in value.items():
                data_text += f"  {k}: {v}\n"
        else:
            data_text += f"{key}: {value}\n"

    # Retrieve relevant textbook excerpts for this persona + trigger
    textbook_section = ''
    if persona_key and trigger_reason:
        try:
            excerpts = get_context_for_persona(persona_key, trigger_reason)
            if excerpts:
                textbook_section = (
                    f"\nRelevant course material:\n{excerpts}\n"
                )
        except Exception as e:
            logger.debug(f"Textbook retrieval skipped: {e}")

    return (
        f"Here is the team's data for Round {round_number}:\n"
        f"{data_text}\n"
        f"The trigger for this message: {trigger_reason}\n"
        f"{textbook_section}\n"
        "Write your message to the team."
    )


def build_prompt(persona_key, team_id, round_number, reaction):
    """Build the full messages array for the LLM call."""
    team_name = _get_team_name(team_id)
    system_prompt = _build_system_prompt(persona_key, team_name, round_number, reaction.severity)
    user_prompt = _build_user_prompt(
        round_number, reaction.trigger_reason, reaction.data_context,
        persona_key=persona_key,
    )

    # Append language instruction based on team's language preference
    team = Team.objects.filter(team_id=team_id).first()
    if team:
        language = get_team_language(team)
        lang_instruction = build_language_instruction(language)
        if lang_instruction:
            user_prompt += lang_instruction

    return [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt},
    ]


def call_llm(messages):
    """Call DashScope API (OpenAI-compatible) and return the response text."""
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    if not api_key:
        logger.warning("DASHSCOPE_API_KEY not set — skipping LLM call")
        return None

    try:
        response = requests.post(
            DASHSCOPE_BASE_URL,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': DASHSCOPE_MODEL,
                'messages': messages,
                'max_tokens': MAX_TOKENS,
                'temperature': TEMPERATURE,
            },
            timeout=LLM_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        text = data['choices'][0]['message']['content'].strip()
        # Strip any markdown formatting that slipped through
        text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text)  # *italic*, **bold**, ***both***
        text = re.sub(r'_{1,3}(.+?)_{1,3}', r'\1', text)     # _italic_, __bold__
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)  # # headers
        return text
    except requests.exceptions.Timeout:
        logger.warning("DashScope API timed out")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"DashScope API error: {e}")
        return None
    except (KeyError, IndexError) as e:
        logger.warning(f"Unexpected DashScope response format: {e}")
        return None


# ---------------------------------------------------------------------------
# Message persistence
# ---------------------------------------------------------------------------

MAX_REPLIES_PER_THREAD = 3
MAX_CONSULTATIONS_PER_ROUND = 10


def _save_persona_message(persona_key, team_id, round_number, severity, source,
                          message_body, parent_message_id=None, thread_root_id=None):
    """Write a persona message to the messages table."""
    persona = PERSONAS[persona_key]

    avatar = persona['avatar']

    msg = Message.objects.create(
        sender_name=persona['name'],
        sender_title=persona['title'],
        sender_type='ai_persona',
        persona_key=persona_key,
        recipient_type='Team',
        recipient_id=team_id,
        subject=f"Message from {persona['name']}",
        message_body=message_body,
        round_number=round_number,
        severity=severity,
        source=source,
        avatar_image=avatar,
        parent_message_id=parent_message_id,
        thread_root_id=thread_root_id,
        created_at=timezone.now(),
    )
    # If this is a root message, set thread_root_id to itself
    if thread_root_id is None and parent_message_id is None:
        msg.thread_root_id = msg.message_id
        msg.save()
    return msg


def _save_student_message(team_id, round_number, message_body,
                          parent_message_id, thread_root_id):
    """Write a student reply to the messages table."""
    team_name = _get_team_name(team_id)
    msg = Message.objects.create(
        sender_name=team_name,
        sender_type='student',
        recipient_type='Team',
        recipient_id=team_id,
        subject='Team reply',
        message_body=message_body,
        round_number=round_number,
        source='student_reply',
        parent_message_id=parent_message_id,
        thread_root_id=thread_root_id,
        created_at=timezone.now(),
    )
    return msg


def _get_current_round():
    """Get the current round number."""
    state = SimulationState.objects.filter(status='active').first()
    if state and state.current_round_id:
        current_round = Round.objects.filter(round_id=state.current_round_id).first()
        if current_round:
            return current_round.round_number or 1
    return 1


def _get_total_rounds():
    """Get the total number of rounds from the active scenario."""
    from core.models.scenario import Scenario
    scenario = Scenario.objects.filter(is_active=True).first()
    return scenario.num_rounds if scenario else 10


def _get_thread_messages(thread_root_id):
    """Get all messages in a thread ordered chronologically."""
    return list(
        Message.objects.filter(thread_root_id=thread_root_id)
        .order_by('created_at')
    )


def _count_student_replies_in_thread(thread_root_id):
    """Count student replies in a thread."""
    return Message.objects.filter(
        thread_root_id=thread_root_id,
        sender_type='student',
    ).count()


def _count_consultations_this_round(team_id, round_number):
    """Count student-initiated messages this round (consultations + replies)."""
    return Message.objects.filter(
        recipient_id=team_id,
        round_number=round_number,
        sender_type='student',
    ).count()


def _build_team_context(team_id, round_number):
    """Build a context summary of the team's current state."""
    team_name = _get_team_name(team_id)
    financials = _get_financials(team_id, round_number)
    esg_data = _get_esg_data(team_id, round_number)
    leaderboard = _get_leaderboard(team_id, round_number)
    programs = _get_active_programs(team_id)
    events = _get_triggered_events(round_number, team_id)

    total_rounds = _get_total_rounds()
    context_text = f"Team: {team_name}\nRound: {round_number}/{total_rounds}\n"

    context_text += f"\nActive Programs: {len(programs)}\n"
    for p in programs:
        context_text += f"  - {p['program_name']} ({p['program_type']})\n"

    if esg_data:
        latest = esg_data[0]
        context_text += f"\nESG Scores: E={latest['environmental']:.1f}, S={latest['social']:.1f}, G={latest['governance']:.1f}\n"

    if financials['income_statements']:
        inc = financials['income_statements'][0]
        context_text += f"\nFinancials: Revenue=${inc['revenue']:,.0f}, Program Expenses=${inc['program_expenses']:,.0f}, Net Income=${inc['net_income']:,.0f}\n"

    if leaderboard:
        context_text += "\nLeaderboard:\n"
        for entry in leaderboard:
            marker = " ← your team" if entry.get('is_current_team') else ""
            context_text += f"  #{entry['rank']} {entry['team_name']} ({entry['total_score']:.0f}){marker}\n"

    if events:
        context_text += f"\nRecent events: {len(events)} triggered\n"

    return context_text


def _build_conversation_prompt(persona_key, team_id, round_number, thread_messages,
                               trigger_data=None):
    """Build the LLM messages array including full thread history."""
    team_name = _get_team_name(team_id)
    persona = PERSONAS[persona_key]
    context_text = _build_team_context(team_id, round_number)

    system_prompt = (
        f"You are {persona['name']}, {persona['title']}.\n\n"
        f"Personality: {persona['personality']}\n\n"
        f"You are in a conversation with team \"{team_name}\" during Round {round_number} of {_get_total_rounds()}.\n\n"
        f"Current team context:\n{context_text}\n\n"
        "Rules:\n"
        "- Stay in character at all times\n"
        "- Reference specific numbers from the team data where relevant\n"
        "- Keep your response to 2-3 paragraphs maximum\n"
        "- Do not use bullet points or lists — write in natural prose\n"
        "- Do not use markdown formatting (no asterisks, bold, italic, headers, etc.) — write in plain text only\n"
        "- Never break the fourth wall or mention this is a simulation\n"
        "- Remember what you said earlier in this conversation — maintain consistency\n"
        "- Give specific, actionable advice when asked\n"
    )

    # Retrieve textbook context for the latest student message in the thread
    latest_student_text = ''
    for msg in reversed(thread_messages):
        if msg.sender_type == 'student' and msg.message_body:
            latest_student_text = msg.message_body
            break

    if latest_student_text:
        try:
            textbook_ctx = get_context_for_student_query(latest_student_text)
            if textbook_ctx:
                system_prompt += (
                    f"\nRelevant course material:\n{textbook_ctx}\n\n"
                    "You may reference these course concepts when appropriate, "
                    "but weave them naturally into your advice.\n"
                )
        except Exception as e:
            logger.debug(f"Textbook retrieval skipped for thread: {e}")

    # Append language instruction based on team's language preference
    team = Team.objects.filter(team_id=team_id).first()
    if team:
        language = get_team_language(team)
        lang_instruction = build_language_instruction(language)
        if lang_instruction:
            system_prompt += lang_instruction

    llm_messages = [{'role': 'system', 'content': system_prompt}]

    # Add thread history as alternating assistant/user messages
    for msg in thread_messages:
        if msg.sender_type == 'ai_persona':
            role = 'assistant'
        elif msg.sender_type == 'student':
            role = 'user'
        else:
            continue
        llm_messages.append({'role': role, 'content': msg.message_body or ''})

    return llm_messages


# ---------------------------------------------------------------------------
# Main orchestration: post-round reactions
# ---------------------------------------------------------------------------

def generate_persona_reactions(team_id, round_number):
    """
    Generate AI persona reactions for a team after a round completes.
    Returns list of created Message objects.
    """
    created_messages = []

    # Round 1: only board chair welcome
    if round_number == 1:
        reaction = _should_react_board_chair(team_id, round_number)
        if reaction.severity != SEVERITY_NONE:
            prompt = build_prompt('board_chair', team_id, round_number, reaction)
            body = call_llm(prompt)
            if body:
                msg = _save_persona_message(
                    'board_chair', team_id, round_number,
                    reaction.severity, 'post_round_reaction', body,
                )
                created_messages.append(msg)
        return created_messages

    # Collect reactions from all personas
    active_sevs = _active_severities(round_number)
    reactions = []

    for persona_key, trigger_fn in TRIGGER_FUNCTIONS.items():
        try:
            decision = trigger_fn(team_id, round_number)
            if decision.severity != SEVERITY_NONE and decision.severity in active_sevs:
                reactions.append((persona_key, decision))
        except Exception as e:
            logger.warning(f"Persona {persona_key} trigger failed for team {team_id}: {e}")

    if not reactions:
        return created_messages

    # Sort by severity (desc) then persona priority (desc)
    reactions.sort(
        key=lambda r: (SEVERITY_PRIORITY.get(r[1].severity, 0), PERSONA_PRIORITY.get(r[0], 0)),
        reverse=True,
    )

    # Apply message cap
    selected = reactions[:MAX_MESSAGES_PER_TEAM]

    # Generate messages — parallelize LLM calls within this team
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _generate_one(persona_key, reaction):
        prompt = build_prompt(persona_key, team_id, round_number, reaction)
        body = call_llm(prompt)
        return (persona_key, reaction, body)

    with ThreadPoolExecutor(max_workers=MAX_MESSAGES_PER_TEAM) as executor:
        futures = {
            executor.submit(_generate_one, pk, rxn): pk
            for pk, rxn in selected
        }
        for future in as_completed(futures):
            try:
                persona_key, reaction, body = future.result()
                if body:
                    msg = _save_persona_message(
                        persona_key, team_id, round_number,
                        reaction.severity, 'post_round_reaction', body,
                    )
                    created_messages.append(msg)
            except Exception as e:
                pk = futures[future]
                logger.warning(f"Failed to generate message for persona {pk}, team {team_id}: {e}")

    return created_messages


# ---------------------------------------------------------------------------
# Threaded conversation: reply to existing thread
# ---------------------------------------------------------------------------

def reply_to_thread(team_id, message_id, reply_text):
    """
    Student replies to a persona message. The persona replies back in character
    with full thread context. Returns dict with student_message, persona_response,
    or error string.
    """
    # Find the target message
    target_msg = Message.objects.filter(message_id=message_id).first()
    if not target_msg:
        return {'error': 'Message not found'}

    if target_msg.recipient_id != team_id:
        return {'error': 'Message does not belong to this team'}

    # Determine thread root
    thread_root_id = target_msg.thread_root_id or target_msg.message_id

    # Check reply cap (3 student replies per thread)
    student_replies = _count_student_replies_in_thread(thread_root_id)
    if student_replies >= MAX_REPLIES_PER_THREAD:
        return {'error': f'Maximum {MAX_REPLIES_PER_THREAD} replies per conversation reached'}

    # Check consultation limit (10 per round)
    round_number = _get_current_round()
    consultations_used = _count_consultations_this_round(team_id, round_number)
    if consultations_used >= MAX_CONSULTATIONS_PER_ROUND:
        return {'error': f'Consultation limit reached ({MAX_CONSULTATIONS_PER_ROUND} per round)'}

    # Determine persona from the thread root
    root_msg = Message.objects.filter(message_id=thread_root_id).first()
    persona_key = root_msg.persona_key if root_msg else target_msg.persona_key
    if not persona_key or persona_key not in PERSONAS:
        return {'error': 'Cannot determine persona for this thread'}

    # Save student reply
    student_msg = _save_student_message(
        team_id, round_number, reply_text,
        parent_message_id=message_id,
        thread_root_id=thread_root_id,
    )

    # Get full thread history
    thread_messages = _get_thread_messages(thread_root_id)

    # Build prompt with full conversation context
    llm_messages = _build_conversation_prompt(
        persona_key, team_id, round_number, thread_messages,
    )

    # Call LLM
    body = call_llm(llm_messages)
    if not body:
        return {
            'error': 'Advisor is temporarily unavailable',
            'student_message': {
                'message_id': student_msg.message_id,
                'message_body': student_msg.message_body,
            },
        }

    # Save persona response
    persona_msg = _save_persona_message(
        persona_key, team_id, round_number,
        SEVERITY_MEDIUM, 'thread_reply', body,
        parent_message_id=student_msg.message_id,
        thread_root_id=thread_root_id,
    )

    persona = PERSONAS[persona_key]
    return {
        'student_message': {
            'message_id': student_msg.message_id,
            'message_body': student_msg.message_body,
            'created_at': student_msg.created_at.isoformat() if student_msg.created_at else None,
        },
        'persona_response': {
            'message_id': persona_msg.message_id,
            'persona_key': persona_key,
            'persona_name': persona['name'],
            'persona_title': persona['title'],
            'message_body': persona_msg.message_body,
            'avatar_image': persona_msg.avatar_image,
            'created_at': persona_msg.created_at.isoformat() if persona_msg.created_at else None,
        },
    }


# ---------------------------------------------------------------------------
# New consultation: student-initiated fresh thread
# ---------------------------------------------------------------------------

def start_consultation(team_id, persona_key, question):
    """
    Student starts a new conversation with a persona.
    Returns dict with student_message and persona_response, or error.
    """
    if persona_key not in PERSONAS:
        return {'error': f'Invalid persona. Valid: {list(PERSONAS.keys())}'}

    round_number = _get_current_round()

    # Check consultation limit
    consultations_used = _count_consultations_this_round(team_id, round_number)
    if consultations_used >= MAX_CONSULTATIONS_PER_ROUND:
        return {'error': f'Consultation limit reached ({MAX_CONSULTATIONS_PER_ROUND} per round)'}

    persona = PERSONAS[persona_key]
    team_name = _get_team_name(team_id)
    context_text = _build_team_context(team_id, round_number)

    # Create the student's opening message first (as thread root)
    student_msg = Message.objects.create(
        sender_name=team_name,
        sender_type='student',
        recipient_type='Team',
        recipient_id=team_id,
        subject=f"Consultation with {persona['name']}",
        message_body=question,
        round_number=round_number,
        source='consultation',
        persona_key=persona_key,
        created_at=timezone.now(),
    )
    # Set as its own thread root
    student_msg.thread_root_id = student_msg.message_id
    student_msg.save()

    # Retrieve textbook context for the student's question
    textbook_section = ''
    try:
        textbook_ctx = get_context_for_student_query(question)
        if textbook_ctx:
            textbook_section = (
                f"\nRelevant course material:\n{textbook_ctx}\n\n"
                "You may reference these course concepts when appropriate, "
                "but weave them naturally into your advice.\n"
            )
    except Exception as e:
        logger.debug(f"Textbook retrieval skipped for consultation: {e}")

    # Build LLM prompt
    system_prompt = (
        f"You are {persona['name']}, {persona['title']}.\n\n"
        f"Personality: {persona['personality']}\n\n"
        f"A team member from \"{team_name}\" is consulting you for advice during Round {round_number} of {_get_total_rounds()}.\n\n"
        f"Current team context:\n{context_text}\n\n"
        f"{textbook_section}"
        "Rules:\n"
        "- Stay in character at all times\n"
        "- Give specific, actionable advice based on the data\n"
        "- Reference specific numbers where relevant\n"
        "- Keep your response to 2-3 paragraphs\n"
        "- Do not use bullet points or lists — write in natural prose\n"
        "- Do not use markdown formatting (no asterisks, bold, italic, headers, etc.) — write in plain text only\n"
        "- Never break the fourth wall or mention this is a simulation\n"
    )

    # Append language instruction based on team's language preference
    team = Team.objects.filter(team_id=team_id).first()
    if team:
        language = get_team_language(team)
        lang_instruction = build_language_instruction(language)
        if lang_instruction:
            system_prompt += lang_instruction

    llm_messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': question},
    ]

    body = call_llm(llm_messages)
    if not body:
        return {
            'error': 'Advisor is temporarily unavailable',
            'student_message': {
                'message_id': student_msg.message_id,
                'message_body': student_msg.message_body,
                'thread_root_id': student_msg.thread_root_id,
            },
        }

    # Save persona response
    persona_msg = _save_persona_message(
        persona_key, team_id, round_number,
        SEVERITY_MEDIUM, 'consultation', body,
        parent_message_id=student_msg.message_id,
        thread_root_id=student_msg.thread_root_id,
    )

    return {
        'student_message': {
            'message_id': student_msg.message_id,
            'message_body': student_msg.message_body,
            'thread_root_id': student_msg.thread_root_id,
            'created_at': student_msg.created_at.isoformat() if student_msg.created_at else None,
        },
        'persona_response': {
            'message_id': persona_msg.message_id,
            'persona_key': persona_key,
            'persona_name': persona['name'],
            'persona_title': persona['title'],
            'message_body': persona_msg.message_body,
            'avatar_image': persona_msg.avatar_image,
            'thread_root_id': persona_msg.thread_root_id,
            'created_at': persona_msg.created_at.isoformat() if persona_msg.created_at else None,
        },
    }


def get_consultation_usage(team_id):
    """Return consultation usage for the current round."""
    round_number = _get_current_round()
    used = _count_consultations_this_round(team_id, round_number)
    return {
        'round_number': round_number,
        'used': used,
        'limit': MAX_CONSULTATIONS_PER_ROUND,
        'remaining': max(0, MAX_CONSULTATIONS_PER_ROUND - used),
    }
