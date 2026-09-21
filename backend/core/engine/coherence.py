"""
Engine Step 14: Strategic Coherence Scoring.
From 03-engine-logic.md Section 13.
CC-11: RAG-grounded coherence evaluation.
"""
import logging
import time
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings

from core.models.decisions import (
    DecisionMarketing, DecisionRDInvestment, DecisionSubmission,
    DecisionMarketEntry, DecisionFinancing,
)
from core.models.team_state import TeamMarketPresence, TeamProduct, TeamProductMarket
from core.models.scenario import SegmentPreference
from core.models.results_financials import RoundResultCoherence
from core.engine.utils import get_config
from core.engine.llm_runner import build_language_instruction
from core.utils.localization import get_team_language

logger = logging.getLogger('engine')

D = Decimal

# ── Alignment matrices (from spec Section 13) ──

PRICE_RANGES = {
    'budget': (100, 300),
    'mainstream': (250, 550),
    'premium': (500, 900),
    'ultra_premium': (800, 1500),
}

DISTRIBUTION_ALIGNMENT = {
    ('budget', 'mass_retail'): 1.0,
    ('budget', 'selective_retail'): 0.5,
    ('budget', 'exclusive_retail'): 0.0,
    ('budget', 'direct_online'): 0.7,
    ('budget', 'hybrid'): 0.6,
    ('mainstream', 'mass_retail'): 0.8,
    ('mainstream', 'selective_retail'): 1.0,
    ('mainstream', 'exclusive_retail'): 0.3,
    ('mainstream', 'direct_online'): 0.7,
    ('mainstream', 'hybrid'): 0.9,
    ('premium', 'mass_retail'): 0.2,
    ('premium', 'selective_retail'): 0.8,
    ('premium', 'exclusive_retail'): 1.0,
    ('premium', 'direct_online'): 0.7,
    ('premium', 'hybrid'): 0.8,
    ('ultra_premium', 'mass_retail'): 0.0,
    ('ultra_premium', 'selective_retail'): 0.5,
    ('ultra_premium', 'exclusive_retail'): 1.0,
    ('ultra_premium', 'direct_online'): 0.6,
    ('ultra_premium', 'hybrid'): 0.5,
}


def calculate_coherence(context, skip_rag=True):
    """
    For each team, score across 5 dimensions:
    1. Positioning-Price Alignment
    2. Distribution-Positioning Alignment
    3. Entry Mode-Market Risk Alignment
    4. R&D-Market Alignment
    5. Financial Prudence
    Normalize to 0-100. The stored score is the formula score and nothing else.

    R31: this function writes `RoundResultCoherence`, which is graded,
    published and inside the hashed `coherence` manifest section, so it has no
    route to a language model. `skip_rag` survives only so the existing caller
    keeps working; it no longer selects anything, and asking for the old
    behaviour is refused outright rather than quietly ignored -- a caller that
    believes retrieval is being graded when it is not is its own defect. The
    model's view of a round is Phase-2 instructor commentary
    (`update_coherence_with_rag`), which writes no competitive field.
    """
    if not skip_rag:
        raise RuntimeError(
            'R31: calculate_coherence() cannot blend a model score. The stored '
            'coherence score is graded and hashed, and a language model must '
            'not reach it. Call it with skip_rag=True (the default); retrieval '
            'commentary is produced in Phase 2 by update_coherence_with_rag().')
    game = context.game
    current_round = context.round_number

    for team in context.teams:
        submission = DecisionSubmission.objects.filter(
            team=team, round__round_number=current_round, round__game=game,
        ).first()

        coherence_score = 0.0
        max_possible = 0.0
        breakdown = {}

        # 1. Positioning-Price Alignment
        pp_score, pp_max, pp_details = _score_positioning_price(team, submission)
        coherence_score += pp_score
        max_possible += pp_max
        breakdown['positioning_price'] = {'score': pp_score / max(pp_max, 1), 'details': pp_details}

        # 2. Distribution-Positioning Alignment
        dp_score, dp_max, dp_details = _score_distribution_positioning(team, submission)
        coherence_score += dp_score
        max_possible += dp_max
        breakdown['distribution_positioning'] = {'score': dp_score / max(dp_max, 1), 'details': dp_details}

        # 3. Entry Mode-Market Risk Alignment
        em_score, em_max, em_details = _score_entry_mode_risk(team, context)
        coherence_score += em_score
        max_possible += em_max
        breakdown['entry_mode_risk'] = {'score': em_score / max(em_max, 1), 'details': em_details}

        # 4. R&D-Market Alignment
        # R10 / V2-053: the R&D market-alignment component is retired with the
        # decision it scored. It read DecisionRDInvestment rows, which after R9
        # change no product, so it credited an intention rather than a
        # capability. It contributed to both the numerator and the denominator,
        # so removing it leaves the surviving components' ratio untouched --
        # nothing needs re-weighting here.
        #
        # Whether a team's *delivered* platform features match segment demand
        # is still scored, by the market outcomes those features produce.

        # 5. Financial Prudence
        fp_score, fp_details = _score_financial_prudence(team, context)
        coherence_score += fp_score
        max_possible += 1.0
        breakdown['financial_prudence'] = fp_details

        # 6. Budget Discipline — penalizes teams that exceed operating budget
        bd_score, bd_details = _score_budget_discipline(team, submission, context)
        coherence_score += bd_score
        max_possible += 1.0
        breakdown['budget_discipline'] = bd_details

        # 7. CC-32C: Governance-Tax Consistency
        gt_score, gt_details = _score_governance_tax_consistency(team, context)
        coherence_score += gt_score
        max_possible += 1.0
        breakdown['governance_tax'] = gt_details

        # Normalize to 0-100
        if max_possible > 0:
            formula_score = D(str(round((coherence_score / max_possible) * 100, 2)))
        else:
            formula_score = D('50.00')

        # R31 (2026-09-16): the communication score does NOT reach this number.
        # It was scored by a language model at submit time, and this row is
        # graded (services/grading.py), published, and inside the hashed
        # `coherence` manifest section -- so blending it in put model output
        # into a competitive result and contradicted V2-016's closure, which
        # records that a model cannot reach a graded number. The evaluation
        # survives on TeamCommunication as feedback for the student and the
        # instructor; it is not graded, and it is not in this row.
        #
        # Nor does a model's retrieval score. A second blend lived here until
        # 2026-09-21 -- six tenths formula, four tenths model -- behind a
        # `skip_rag=False` that was also the default argument. Production never
        # took it, but one forgotten argument was all that stood between a
        # model and a graded number, so the branch is gone rather than guarded.
        # `rag_score` stays in the row, always empty: the column is part of the
        # hashed section's shape, and removing it would move the envelope.
        RoundResultCoherence.objects.update_or_create(
            game=game, round_number=current_round, team=team,
            defaults={
                'formula_score': formula_score,
                'rag_score': None,
                'blended_score': formula_score,
                'breakdown': breakdown,
            },
        )

        context.log.append(f'Coherence: {team.name} = {formula_score}/100')


def update_coherence_with_rag(game, round_number, team, rag_text):
    """Record a Phase-2 retrieval evaluation as instructor commentary.

    It does not write `RoundResultCoherence`, and there is no configuration in
    which it does. That row is inside the competitive hash *and* is read by
    services/grading.py, so writing it from Phase 2 made the stored round
    disagree with the manifest that certified it (V2-015) and made a student's
    mark depend on whether an external service answered (V2-016). A default-off
    switch was not enough — a supported configuration could still turn it back
    on — so the write is gone rather than gated, and
    `require_safe_rag_configuration()` refuses to resolve a round while the
    legacy flag is set.

    Including retrieval in a grade remains a legitimate rules choice. It
    belongs in Phase 1, inside the transaction the manifest hashes, and it is
    not this function.
    """
    import json

    coherence_record = RoundResultCoherence.objects.filter(
        game=game, round_number=round_number, team=team,
    ).first()
    if not coherence_record:
        return

    try:
        text = rag_text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        parsed = json.loads(text)
        rag_score_val = float(parsed.get('score', 50))
        rag_feedback = parsed.get('feedback', '')
    except (json.JSONDecodeError, ValueError, KeyError):
        return  # Can't parse — nothing to say, and nothing to change.

    # What the score *would* have been, shown to instructors as context. It is
    # computed here and stored nowhere near the graded row.
    formula_score = float(coherence_record.formula_score)
    blended_val = 0.6 * formula_score + 0.4 * rag_score_val

    _record_rag_commentary(game, round_number, team, rag_score_val, rag_feedback,
                           blended_val)


def _record_rag_commentary(game, round_number, team, score, feedback, blended):
    """Keep the RAG evaluation visible to instructors without scoring with it."""
    try:
        from core.models.cc21_models import InstructorAlert
        InstructorAlert.objects.update_or_create(
            game=game, team=team, round_number=round_number,
            alert_type='coherence_rag',
            defaults={
                'title': f'Round {round_number} coherence commentary',
                'detail': feedback or '',
                'severity': 'info',
                'teaching_note': (
                    f'Retrieval-grounded evaluation scored {score:.0f}/100. '
                    f'Blended with the formula score this would be '
                    f'{blended:.0f}/100; the published coherence score is the '
                    f'formula score unless COMPETITION_RAG_AFFECTS_COHERENCE '
                    f'is enabled.'),
                'source': 'narrative',
            },
        )
    except Exception:
        logger.exception('Could not record RAG commentary for %s', team)


def communication_feedback_total(game, team, current_round):
    """The stored communication contributions, for display only.

    Retained deliberately after R31 severed this from grading, so the figure an
    instructor sees has one definition. Two things it is not: it is not summed
    into `blended_score`, and it is not written into the hashed coherence row.

    Its old name said `coherence`, and its old comment claimed the value was
    "already on a 0-100ish scale". It never was: each contribution is
    `overall_score` (0-1) x the assignment weight x 100, and the five authored
    assignments weigh 0.26 in total, so the sum caps near 26 against a formula
    score that runs to 100. Blending the two therefore *lowered* a team's
    coherence whenever a student did the assignment -- most for the strongest
    teams. Recorded here because the arithmetic is the reason the severed path
    could never have been simply re-weighted.
    """
    try:
        from core.models.cc32_models import TeamCommunication
        from django.db.models import Sum

        result = TeamCommunication.objects.filter(
            game=game, team=team, is_draft=False,
            round__round_number__lte=current_round,
        ).aggregate(total=Sum('coherence_contribution'))
        return float(result['total'] or 0)
    except Exception:
        return 0.0


def _score_positioning_price(team, submission):
    """Score 1.0 if within range, 0.5 if within 20% outside, 0.0 if further."""
    score = 0.0
    max_possible = 0.0
    details = []

    if not submission:
        return score, max_possible, details

    for md in (submission.marketing_decisions.all()
               .select_related('team_product', 'market')
               .order_by('team_product__name', 'market__code')):
        # A product that was not offered for sale has no price to judge its
        # positioning against, so it is not scored either way -- neither
        # credited nor penalised, and it does not enter `max_possible`.
        if md.retail_price is None:
            continue
        positioning = md.team_product.positioning
        price = float(md.retail_price)
        price_range = PRICE_RANGES.get(positioning, (0, 9999))
        min_p, max_p = price_range

        if min_p <= price <= max_p:
            s = 1.0
            aligned = True
        elif price < min_p * 0.8 or price > max_p * 1.2:
            s = 0.0
            aligned = False
        else:
            s = 0.5
            aligned = False

        score += s
        max_possible += 1.0
        details.append({
            'product': md.team_product.name,
            'market': md.market.name,
            'price': price,
            'range': f'{min_p}-{max_p}',
            'aligned': aligned,
        })

    return score, max_possible, details


def _score_distribution_positioning(team, submission):
    """Score from alignment matrix."""
    score = 0.0
    max_possible = 0.0
    details = []

    if not submission:
        return score, max_possible, details

    for md in (submission.marketing_decisions.all()
               .select_related('team_product', 'market')
               .order_by('team_product__name', 'market__code')):
        pos = md.team_product.positioning
        dist = md.distribution_strategy
        alignment = DISTRIBUTION_ALIGNMENT.get((pos, dist), 0.5)
        score += alignment
        max_possible += 1.0
        details.append({
            'product': md.team_product.name,
            'market': md.market.name,
            'positioning': pos,
            'distribution': dist,
            'alignment': alignment,
        })

    return score, max_possible, details


def _score_entry_mode_risk(team, context):
    """Entry mode vs market risk alignment."""
    score = 0.0
    max_possible = 0.0
    details = []

    high_threshold = get_config(
        context.scenario, 'high_commitment_threshold', default=5000000.0,
    )

    presences = (TeamMarketPresence.objects.filter(
        team=team, status='active',
    ).select_related('entry_mode', 'market')).order_by('market__code')

    for presence in presences:
        risk = float(presence.market.regulatory_difficulty)
        control = float(presence.entry_mode.control_level)
        investment = float(presence.initial_investment)

        if risk > 7 and control > 7:
            s = 0.8 if investment > high_threshold else 0.3
        elif risk > 7 and control <= 4:
            s = 1.0  # Prudent entry in risky market
        elif risk <= 3 and control > 7:
            s = 0.7  # Overkill but safe
        else:
            s = 0.8  # Moderate match

        score += s
        max_possible += 1.0
        details.append({
            'market': presence.market.name,
            'risk': risk,
            'control': control,
            'score': s,
        })

    return score, max_possible, details


def _score_financial_prudence(team, context):
    """Score based on debt-to-equity ratio."""
    financials = getattr(context, 'financials', {}).get(team.id, {})
    d2e = float(financials.get('debt_to_equity', 0))

    if d2e < 1.0:
        score = 1.0
        feedback = 'Conservative leverage. Strong financial position.'
    elif d2e < 2.0:
        score = 0.6
        feedback = 'Moderate leverage. Manageable but watch debt growth.'
    else:
        score = 0.2
        feedback = 'High leverage. Risk of financial distress.'

    return score, {
        'score': score,
        'debt_to_equity': d2e,
        'feedback': feedback,
    }


def _score_budget_discipline(team, submission, context):
    """
    Score based on whether total spending stays within the operating budget.
    Operating budget = base amount + 20% of prior round net profit.
    Over-budget spending is penalized proportionally.
    """
    budget_base = float(get_config(context.scenario, 'budget_base_amount', default=5000000))
    budget_pct = float(get_config(context.scenario, 'budget_profit_pct', default=0.20))

    from core.models.results_financials import RoundResultFinancials
    prev_fin = RoundResultFinancials.objects.filter(
        game=context.game, team=team, round_number=context.round_number - 1,
    ).first()
    prev_profit = max(float(prev_fin.net_income or 0), 0) if prev_fin else 0
    operating_budget = budget_base + prev_profit * budget_pct

    # Calculate actual total spending from budget allocation
    total_allocated = 0.0
    if submission:
        from core.models.decisions import DecisionBudgetAllocation
        try:
            ba = submission.budget_allocation
            total_allocated = float(ba.rd_budget + ba.marketing_budget + ba.strategy_budget)
        except DecisionBudgetAllocation.DoesNotExist:
            pass

    if operating_budget <= 0:
        return 1.0, {
            'score': 1.0,
            'operating_budget': 0,
            'total_allocated': total_allocated,
            'over_pct': 0,
            'feedback': 'No operating budget baseline (first round).',
        }

    over_pct = max((total_allocated - operating_budget) / operating_budget, 0)

    if over_pct <= 0:
        score = 1.0
        feedback = 'Spending within operating budget. Good fiscal discipline.'
    elif over_pct <= 0.10:
        score = 0.8
        feedback = f'Slightly over budget ({over_pct:.0%}). Minor overspend.'
    elif over_pct <= 0.25:
        score = 0.5
        feedback = f'Over budget by {over_pct:.0%}. Spending discipline is weak.'
    elif over_pct <= 0.50:
        score = 0.3
        feedback = f'Significantly over budget ({over_pct:.0%}). Reckless spending erodes stakeholder confidence.'
    else:
        score = 0.0
        feedback = f'Massively over budget ({over_pct:.0%}). No spending discipline.'

    return score, {
        'score': score,
        'operating_budget': operating_budget,
        'total_allocated': total_allocated,
        'over_pct': round(over_pct, 4),
        'feedback': feedback,
    }


def _score_governance_tax_consistency(team, context):
    """
    CC-32C: Penalize teams that have an Anti-Corruption governance commitment
    but use an aggressive tax structure with anti_corruption_conflict=True.
    Full score (1.0) if no conflict; penalized (0.0) if blatant hypocrisy.
    """
    from core.models.cc32c_models import TeamTaxStructure
    from core.models.cc31_models import TeamGovernanceCommitment

    tts = TeamTaxStructure.objects.filter(
        game=context.game, team=team,
    ).select_related('current_structure').first()

    structure = tts.current_structure if tts else None

    if not structure or not structure.anti_corruption_conflict:
        return 1.0, {
            'score': 1.0,
            'feedback': 'No governance-tax conflict detected.',
        }

    has_anti_corruption = TeamGovernanceCommitment.objects.filter(
        game=context.game, team=team,
        commitment_type__code='anti_corruption',
        is_active=True,
    ).exists()

    if has_anti_corruption:
        return 0.0, {
            'score': 0.0,
            'feedback': (
                'Anti-corruption commitment conflicts with aggressive tax optimization. '
                'Stakeholders view this as hypocritical — coherence heavily penalized.'
            ),
        }

    # Aggressive structure without anti-corruption commitment: mild concern
    return 0.7, {
        'score': 0.7,
        'feedback': (
            'Aggressive tax optimization without governance commitments — '
            'raises moderate stakeholder concerns.'
        ),
    }


def _get_strategy_context_for_coherence(team, context):
    """CC-35: Build strategy context for coherence RAG evaluation."""
    try:
        from core.engine.strategy_advisory import build_strategy_context
        ctx = build_strategy_context(team, team.game, context.current_round)
        if ctx:
            return f"{ctx}\n\n"
    except Exception:
        pass
    return ''


# ---------------------------------------------------------------------------
# CC-11: RAG-grounded coherence scoring
# ---------------------------------------------------------------------------

def _calculate_rag_coherence(context, team, formula_score):
    """
    Use the RAG knowledge base + LLM to evaluate strategic coherence.
    Returns: (rag_score: float 0-100 or None, feedback: str or None)
    """
    rag_enabled = get_config(context.scenario, 'rag_enabled', False, bool)
    if not rag_enabled:
        return None, None

    from django.conf import settings
    from core.engine import llm_runner
    if not llm_runner.llm_configured():
        return None, None

    try:
        decision_summary = _compile_decision_summary(team, context)

        from core.rag.embeddings import get_embedding
        from core.rag.client import search_articles

        # Build queries based on team's key decisions
        queries = []
        for presence in TeamMarketPresence.objects.filter(team=team, status='active').order_by('id'):
            queries.append(
                f"market entry strategy for {presence.market.name} "
                f"using {presence.entry_mode.name if presence.entry_mode else 'direct'}"
            )
        if team.total_debt and team.total_debt > 0:
            queries.append("financing strategy debt equity international expansion")

        if not queries:
            queries.append("international business strategy competitive advantage")

        # Search for each query
        all_results = []
        for q in queries[:3]:
            embedding = get_embedding(q)
            results = search_articles(embedding, limit=3)
            all_results.extend(results)
            time.sleep(0.1)  # Brief delay between embedding calls

        if not all_results:
            return None, None

        # Deduplicate by source
        seen_sources = set()
        unique_results = []
        for r in all_results:
            if r['source'] not in seen_sources:
                seen_sources.add(r['source'])
                unique_results.append(r)

        framework_context = '\n\n'.join([
            f"[{r.get('title', 'Research')}]: {r['text'][:400]}"
            for r in unique_results[:5]
        ])

        # LLM evaluation
        time.sleep(0.5)  # Rate limit delay

        result_text = llm_runner.chat_completion(
            model=llm_runner.model_for_purpose('coherence_rag'),
            messages=[
                {
                    'role': 'system',
                    'content': (
                        "You are a strategy professor evaluating student team decisions "
                        "in a global business simulation. Evaluate how well their strategic "
                        "decisions align with established frameworks and best practices from "
                        "the provided research.\n\n"
                        "Respond in this EXACT JSON format:\n"
                        '{"score": <integer 0-100>, "feedback": "<2-3 sentences>"}\n\n'
                        "Score guide:\n"
                        "80-100: Decisions strongly align with strategic frameworks\n"
                        "60-79: Mostly aligned with some gaps\n"
                        "40-59: Partial alignment, significant strategic mismatches\n"
                        "20-39: Poor alignment with established frameworks\n"
                        "0-19: Decisions contradict fundamental strategic principles\n\n"
                        "Be specific in feedback. Do not be generic."
                    ),
                },
                {
                    'role': 'user',
                    'content': (
                        f"Team decisions this round:\n{decision_summary}\n\n"
                        f"Relevant strategic frameworks:\n{framework_context}\n\n"
                        + _get_strategy_context_for_coherence(team, context)
                        + "Evaluate the strategic coherence of these decisions."
                        + build_language_instruction(get_team_language(team))
                    ),
                },
            ],
            max_tokens=200,
            temperature=0.2,
        )
        if result_text is None:
            return None, None

        import json
        result_text = result_text.strip()
        # Clean potential markdown wrapping
        if result_text.startswith('```'):
            result_text = result_text.split('\n', 1)[1].rsplit('```', 1)[0].strip()

        result = json.loads(result_text)
        rag_score = max(0, min(100, int(result.get('score', 50))))
        feedback = result.get('feedback', '')

        return rag_score, feedback

    except Exception as e:
        context.log.append(f'RAG coherence failed for {team.name}: {e}')
        return None, None


def _compile_decision_summary(team, context):
    """Compile a human-readable summary of team's decisions this round."""
    summary_parts = []

    # R&D investments
    rd_decisions = (DecisionRDInvestment.objects.filter(
        submission__team=team,
        submission__round__round_number=context.round_number,
    ).select_related('feature', 'team_platform')).order_by('team_platform__name', 'feature__code', 'method')

    if rd_decisions.exists():
        investments = [
            f"  - {d.feature.name}: ${float(d.amount):,.0f} ({d.method})"
            for d in rd_decisions
        ]
        summary_parts.append("R&D Investments:\n" + '\n'.join(investments))

    # Market entries
    entries = (DecisionMarketEntry.objects.filter(
        submission__team=team,
        submission__round__round_number=context.round_number,
    ).select_related('market', 'entry_mode')).order_by('market__code', 'action')

    if entries.exists():
        entry_lines = [
            f"  - {d.action.title()} {d.market.name} via "
            f"{d.entry_mode.name if d.entry_mode else 'N/A'} "
            f"(${float(d.initial_investment):,.0f})"
            for d in entries
        ]
        summary_parts.append("Market Entry:\n" + '\n'.join(entry_lines))

    # Marketing highlights
    marketing = (DecisionMarketing.objects.filter(
        submission__team=team,
        submission__round__round_number=context.round_number,
    ).select_related('team_product', 'market')).order_by('team_product__name', 'market__code')

    if marketing.exists():
        mktg_lines = [
            f"  - {d.team_product.name} in {d.market.name}: "
            f"{('$%s' % format(float(d.retail_price), ',.0f')) if d.retail_price is not None else 'not offered'}, "
            f"promo ${float(d.promotion_budget):,.0f}, "
            f"{d.distribution_strategy}, {d.production_volume} units"
            for d in marketing
        ]
        summary_parts.append("Marketing:\n" + '\n'.join(mktg_lines))

    # Financing
    financing = DecisionFinancing.objects.filter(
        submission__team=team,
        submission__round__round_number=context.round_number,
    ).first()

    if financing:
        fin_parts = []
        if financing.new_debt and financing.new_debt > 0:
            fin_parts.append(f"Raised ${float(financing.new_debt):,.0f} debt")
        if financing.debt_repayment and financing.debt_repayment > 0:
            fin_parts.append(f"Repaid ${float(financing.debt_repayment):,.0f}")
        if financing.dividend_per_share and financing.dividend_per_share > 0:
            fin_parts.append(f"Dividend: ${float(financing.dividend_per_share):.2f}/share")
        if fin_parts:
            summary_parts.append("Financing: " + ', '.join(fin_parts))

    return '\n\n'.join(summary_parts) if summary_parts else "No significant decisions this round."
