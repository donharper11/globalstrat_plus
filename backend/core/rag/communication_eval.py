"""
CC-32A: LLM evaluation engine for stakeholder communications.

Builds evaluation prompts from team context, sends to DashScope/Qwen,
parses structured JSON evaluation, and calculates coherence contribution.
"""
import json
import logging
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from core.engine.llm_runner import build_language_instruction
from core.utils.localization import get_team_language

logger = logging.getLogger(__name__)


def evaluate_communication(team_comm):
    """
    Submit communication to LLM for evaluation and store results.
    Returns the evaluation dict or None on failure.
    """
    prompt = build_evaluation_prompt(team_comm)

    # RAG enhancement
    rag_context = get_rag_context_for_evaluation(team_comm)

    if rag_context:
        prompt += f"\n\nRELEVANT FRAMEWORKS FROM KNOWLEDGE BASE:\n{rag_context}"

    # Call LLM
    evaluation = _call_llm_evaluation(prompt)

    if evaluation is None:
        # Fallback: generate a basic evaluation without LLM
        evaluation = _fallback_evaluation(team_comm)

    # Calculate coherence contribution
    overall_score = float(evaluation.get('overall_score', 0))
    coherence_weight = float(team_comm.assignment.coherence_weight)
    coherence_contribution = Decimal(str(round(overall_score * coherence_weight * 100, 2)))

    # Store results
    team_comm.evaluation = evaluation
    team_comm.coherence_contribution = coherence_contribution
    team_comm.is_draft = False
    team_comm.submitted_at = timezone.now()
    team_comm.save()

    return evaluation


def build_evaluation_prompt(team_comm):
    """Build the LLM prompt for evaluating a team communication."""
    assignment = team_comm.assignment
    game = team_comm.game
    team = team_comm.team
    round_obj = team_comm.round

    # Gather the team's actual decisions and state
    context = _gather_team_context(team, game, round_obj)

    # Build criteria description
    criteria_text = "\n".join([
        f"- {c['criterion']} (weight {c['weight']}): {c['description']}"
        for c in (assignment.evaluation_criteria or [])
    ])

    # CC-35: Inject situation-specific strategy context
    strategy_block = ''
    try:
        from core.engine.strategy_advisory import build_strategy_context
        strategy_ctx = build_strategy_context(team, game, round_obj.round_number)
        if strategy_ctx:
            strategy_block = f"\n\n{strategy_ctx}\n"
    except Exception:
        pass

    prompt = f"""You are evaluating a business simulation team's stakeholder communication.

CONTEXT — What this team has ACTUALLY done (their real decisions and results):
{json.dumps(context, indent=2, default=str)}
{strategy_block}
ASSIGNMENT:
Audience: {assignment.get_audience_display()}
Prompt given to the team: {assignment.prompt_text}
Word limit: {assignment.word_limit}

THE TEAM'S COMMUNICATION:
\"\"\"
{team_comm.content}
\"\"\"

EVALUATION CRITERIA:
{criteria_text}

INSTRUCTIONS:
1. Score each criterion from 0.0 to 1.0
2. For strategic_consistency, compare what the team WROTE against what they ACTUALLY DID. Flag any contradictions specifically. If they claim "aggressive ESG investment" but their ESG spend is $0, that's a 0.0 on consistency.
3. For stakeholder_awareness, assess whether they addressed the specific concerns of {assignment.get_audience_display()}.
4. Provide 2-3 specific strengths and 2-3 specific gaps.
5. Flag any consistency contradictions between the communication and actual decisions.
6. Note any relevant strategic frameworks referenced or missing.
7. Provide brief overall feedback (2-3 sentences).

Respond ONLY in JSON format:
{{
    "overall_score": <float 0-1>,
    "criteria_scores": {{
        "<criterion>": {{"score": <float 0-1>, "feedback": "<1-2 sentences>"}}
    }},
    "strengths": ["...", "..."],
    "gaps": ["...", "..."],
    "consistency_flags": ["...", "..."],
    "framework_references": ["...", "..."],
    "overall_feedback": "..."
}}"""

    language = get_team_language(team)
    prompt += build_language_instruction(language)
    if language == 'zh-CN':
        prompt += "\n评估标准与英文版相同。请用简体中文给出评分和反馈。注意：学生使用中文撰写沟通内容。请根据中文商业写作标准评估清晰度和专业性。"

    return prompt


def get_rag_context_for_evaluation(team_comm):
    """Retrieve relevant frameworks from RAG corpus to inform evaluation."""
    try:
        from core.rag.embeddings import get_embedding
        from core.rag.client import search_articles

        assignment = team_comm.assignment
        queries = [
            f"{assignment.get_audience_display()} communication strategy international business",
            f"stakeholder management {assignment.audience.lower()} global expansion",
        ]

        if 'expansion' in assignment.code:
            queries.append("market entry strategy justification board memo")
        elif 'investor' in assignment.code:
            queries.append("investor relations shareholder letter ESG reporting")
        elif 'crisis' in assignment.code:
            queries.append("crisis communication corporate reputation management")
        elif 'employee' in assignment.code:
            queries.append("internal communication change management global workforce")
        elif 'review' in assignment.code:
            queries.append("strategic review performance assessment leadership")

        all_results = []
        for q in queries[:3]:
            embedding = get_embedding(q)
            results = search_articles(embedding, limit=3)
            all_results.extend(results)

        if not all_results:
            return None

        # Deduplicate and format
        seen = set()
        context_parts = []
        for r in all_results:
            text = r.get('text', '')[:400]
            if text not in seen:
                seen.add(text)
                source = r.get('title', r.get('source', 'Unknown'))
                context_parts.append(f"[{source}]: {text}")

        return "\n\n".join(context_parts[:5])

    except Exception as e:
        logger.warning(f"RAG context retrieval failed: {e}")
        return None


def _call_llm_evaluation(prompt):
    """Call DashScope/Qwen for communication evaluation."""
    if not getattr(settings, 'DASHSCOPE_API_KEY', None):
        return None

    try:
        import dashscope
        from dashscope import Generation
        dashscope.api_key = settings.DASHSCOPE_API_KEY

        response = Generation.call(
            model=settings.DASHSCOPE_MODEL,
            messages=[
                {'role': 'system', 'content': (
                    'You are an expert evaluator of executive communications in a global '
                    'business simulation. You compare what teams write to what they actually '
                    'did. Respond ONLY in valid JSON format.'
                )},
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=1500,
            temperature=0.2,
        )

        text = response.output.text.strip()
        # Strip markdown code fences if present
        if text.startswith('```'):
            text = text.split('\n', 1)[1] if '\n' in text else text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

        return json.loads(text)

    except Exception as e:
        logger.error(f"LLM evaluation call failed: {e}")
        return None


def _fallback_evaluation(team_comm):
    """Generate a basic evaluation when LLM is unavailable."""
    word_count = team_comm.word_count
    word_limit = team_comm.assignment.word_limit

    # Simple heuristic: word count relative to limit
    length_score = min(word_count / max(word_limit * 0.5, 1), 1.0)
    base_score = round(0.4 + 0.3 * length_score, 2)

    criteria_scores = {}
    for c in (team_comm.assignment.evaluation_criteria or []):
        criteria_scores[c['criterion']] = {
            'score': base_score,
            'feedback': 'Automated evaluation unavailable. Score based on submission completeness.',
        }

    return {
        'overall_score': base_score,
        'criteria_scores': criteria_scores,
        'strengths': ['Communication submitted within word limit'] if word_count <= word_limit else [],
        'gaps': ['LLM evaluation unavailable — detailed feedback not generated'],
        'consistency_flags': [],
        'framework_references': [],
        'overall_feedback': (
            'This communication was evaluated using a fallback heuristic because the AI evaluator '
            'was unavailable. The score reflects submission completeness only.'
        ),
    }


def _gather_team_context(team, game, round_obj):
    """Gather the team's actual decisions and state for evaluation prompt."""
    from core.models.team_state import TeamMarketPresence
    from core.models.decisions import DecisionSubmission, DecisionESG
    from core.models.results_financials import RoundResultFinancials
    from core.models.cc31_models import TeamGovernanceCommitment

    context = {}

    # Home market
    if team.home_market:
        context['home_market'] = team.home_market.name
    else:
        context['home_market'] = 'Unknown'

    # Active markets
    presences = TeamMarketPresence.objects.filter(
        team=team, status='active',
    ).select_related('market', 'entry_mode')
    context['active_markets'] = [
        {'market': p.market.name, 'entry_mode': p.entry_mode.name}
        for p in presences
    ]

    # Financial summary
    financials = RoundResultFinancials.objects.filter(
        team=team, round_number=round_obj.round_number - 1,
    ).first()
    if financials:
        context['financial_summary'] = {
            'revenue': float(financials.total_revenue),
            'net_income': float(financials.net_income),
            'cash_on_hand': float(team.cash_on_hand),
            'total_debt': float(team.total_debt),
        }
    else:
        context['financial_summary'] = {
            'cash_on_hand': float(team.cash_on_hand),
            'total_debt': float(team.total_debt),
        }

    # ESG commitments
    sub = DecisionSubmission.objects.filter(
        team=team, round__game=game, round__round_number=round_obj.round_number,
    ).first()
    if sub:
        try:
            esg = sub.esg
            if esg:
                context['esg'] = {
                    'environmental_investment': float(esg.environmental_investment or 0),
                    'social_investment': float(esg.social_investment or 0),
                    'governance_commitments': esg.governance_commitments or [],
                }
        except Exception:
            pass

        # Talent decisions
        try:
            talent = sub.talent
            if talent:
                context['talent'] = {
                    'rd_headcount': talent.rd_headcount,
                    'rd_salary_level': talent.rd_salary_level,
                    'commercial_headcount': talent.commercial_headcount,
                    'commercial_salary_level': talent.commercial_salary_level,
                    'operations_headcount': talent.operations_headcount,
                    'operations_salary_level': talent.operations_salary_level,
                }
        except Exception:
            pass

    # Active governance commitments (CC-31J)
    gov_commitments = TeamGovernanceCommitment.objects.filter(
        game=game, team=team, is_active=True,
    ).select_related('commitment_type')
    if gov_commitments.exists():
        context['active_governance_commitments'] = [
            tgc.commitment_type.name for tgc in gov_commitments
        ]

    # Performance index
    context['share_price'] = float(team.share_price)
    context['performance_index'] = float(team.performance_index)

    return context
