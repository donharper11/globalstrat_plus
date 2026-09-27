"""
Reasoning Score Aggregator.

Composes individual dimension scores into:
- reasoning_score_deterministic (R40-safe, dims 1-3)
- reasoning_score_full (includes dim 4)
- overall_band assignment
- Template-based student feedback

Pure function — no I/O, no database access.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.engine.reasoning_coherence import CoherenceExtResult
from core.engine.reasoning_responsiveness import ResponsivenessResult
from core.engine.reasoning_trajectory import TrajectoryResult
from core.engine.reasoning_justification import JustificationResult


# ── Weight configuration ──

DETERMINISTIC_WEIGHTS = {
    'coherence_ext': 0.40,
    'responsiveness': 0.30,
    'trajectory': 0.30,
}

FULL_WEIGHTS = {
    'coherence_ext': 0.30,
    'responsiveness': 0.25,
    'trajectory': 0.20,
    'justification': 0.25,
}

# ── Band thresholds ──

BAND_STRONG = 70.0
BAND_DEVELOPING = 40.0


@dataclass
class AggregatedScore:
    reasoning_score_deterministic: float  # 0-100, R40-safe
    reasoning_score_full: Optional[float]  # 0-100 or None
    overall_band: str  # strong / developing / needs_attention
    feedback_student: Dict  # Per-dimension qualitative feedback
    feedback_judge: Dict  # Per-dimension numeric + evidence


def _assign_band(score: float) -> str:
    if score >= BAND_STRONG:
        return 'strong'
    elif score >= BAND_DEVELOPING:
        return 'developing'
    return 'needs_attention'


def _dimension_band(score: float) -> str:
    """Per-dimension band for student feedback (no raw scores)."""
    return _assign_band(score)


# ── Template feedback messages ──

STUDENT_FEEDBACK_TEMPLATES = {
    'coherence_ext': {
        'strong': 'Your strategic decisions show strong internal consistency across domains.',
        'developing': 'Some of your decisions may not fully align with each other. Review how your R&D, market, and financial choices work together.',
        'needs_attention': 'Your decisions appear contradictory in several areas. Consider how each choice supports your overall strategy.',
    },
    'responsiveness': {
        'strong': 'You responded well to market events and adjusted your strategy appropriately.',
        'developing': 'You acknowledged some events but could have adjusted more decisively in affected areas.',
        'needs_attention': 'Important market events appear to have been overlooked. Review active events before making decisions.',
    },
    'trajectory': {
        'strong': 'Your strategy shows consistent execution with a clear direction over time.',
        'developing': 'Your strategic direction has shifted somewhat between rounds. Consider whether changes are deliberate.',
        'needs_attention': 'Your strategy appears inconsistent across rounds. Frequent reversals may confuse stakeholders.',
    },
    'justification': {
        'strong': 'Your reasoning demonstrates deep analysis with framework-grounded arguments.',
        'developing': 'Your justification references data but could explore more tradeoffs and frameworks.',
        'needs_attention': 'Consider providing more detailed reasoning for your decisions, referencing data and strategic frameworks.',
    },
}

STUDENT_FEEDBACK_TEMPLATES_ZH = {
    'coherence_ext': {
        'strong': '您的战略决策在各领域之间表现出很强的内部一致性。',
        'developing': '您的某些决策可能未完全对齐。请审视研发、市场和财务选择如何协同运作。',
        'needs_attention': '您的决策在多个领域存在矛盾。请考虑每个选择如何支持整体战略。',
    },
    'responsiveness': {
        'strong': '您对市场事件做出了良好的回应，并适当调整了战略。',
        'developing': '您注意到了一些事件，但在受影响的领域可以做出更果断的调整。',
        'needs_attention': '重要的市场事件似乎被忽视了。请在做出决策前审查活跃事件。',
    },
    'trajectory': {
        'strong': '您的战略表现出一致的执行力和明确的方向。',
        'developing': '您的战略方向在各轮之间有所变化。请考虑这些变化是否经过深思熟虑。',
        'needs_attention': '您的战略在各轮之间显得不一致。频繁的方向改变可能会使利益相关者困惑。',
    },
    'justification': {
        'strong': '您的推理展示了深入的分析和基于框架的论证。',
        'developing': '您的论述引用了数据，但可以探索更多权衡和框架。',
        'needs_attention': '请考虑为您的决策提供更详细的推理，引用数据和战略框架。',
    },
}


def compose_scores(
    coherence: CoherenceExtResult,
    responsiveness: ResponsivenessResult,
    trajectory: TrajectoryResult,
    justification: Optional[JustificationResult] = None,
    language: str = 'en',
) -> AggregatedScore:
    """
    Compose dimension scores into aggregated results.

    Args:
        coherence: Extended coherence result
        responsiveness: Signal responsiveness result
        trajectory: Strategic trajectory result
        justification: LLM justification result (None if Phase 2 not done)
        language: 'en' or 'zh-CN' for feedback language
    """
    # Deterministic score (R40-safe)
    det_score = (
        coherence.score * DETERMINISTIC_WEIGHTS['coherence_ext']
        + responsiveness.score * DETERMINISTIC_WEIGHTS['responsiveness']
        + trajectory.score * DETERMINISTIC_WEIGHTS['trajectory']
    )

    # Full score (if justification available)
    if justification is not None:
        full_score = (
            coherence.score * FULL_WEIGHTS['coherence_ext']
            + responsiveness.score * FULL_WEIGHTS['responsiveness']
            + trajectory.score * FULL_WEIGHTS['trajectory']
            + justification.score * FULL_WEIGHTS['justification']
        )
    else:
        full_score = None

    # Band based on deterministic score
    band_score = full_score if full_score is not None else det_score
    overall_band = _assign_band(band_score)

    # Build student feedback (qualitative, no raw scores)
    templates = (
        STUDENT_FEEDBACK_TEMPLATES_ZH if language == 'zh-CN'
        else STUDENT_FEEDBACK_TEMPLATES
    )

    feedback_student = {
        'overall_band': overall_band,
        'dimensions': {
            'coherence_ext': {
                'band': _dimension_band(coherence.score),
                'feedback': templates['coherence_ext'][_dimension_band(coherence.score)],
            },
            'responsiveness': {
                'band': _dimension_band(responsiveness.score),
                'feedback': templates['responsiveness'][_dimension_band(responsiveness.score)],
            },
            'trajectory': {
                'band': _dimension_band(trajectory.score),
                'feedback': templates['trajectory'][_dimension_band(trajectory.score)],
                'pattern': trajectory.pattern,
            },
        },
    }

    if justification is not None:
        feedback_student['dimensions']['justification'] = {
            'band': _dimension_band(justification.score),
            'feedback': templates['justification'][_dimension_band(justification.score)],
            'depth': justification.depth_label,
        }

    # Build judge feedback (full numeric breakdown)
    feedback_judge = {
        'reasoning_score_deterministic': round(det_score, 2),
        'reasoning_score_full': round(full_score, 2) if full_score is not None else None,
        'dimensions': {
            'coherence_ext': {
                'score': coherence.score,
                'sub_scores': coherence.sub_scores,
                'signals': coherence.signals,
            },
            'responsiveness': {
                'score': responsiveness.score,
                'events_relevant': responsiveness.events_relevant,
                'events_addressed': responsiveness.events_addressed,
                'details': [
                    {
                        'event': d.event_name,
                        'addressed': d.addressed,
                        'response_filed': d.response_filed,
                        'changes': d.relevant_changes,
                        'score': d.score,
                    }
                    for d in responsiveness.details
                ],
            },
            'trajectory': {
                'score': trajectory.score,
                'pattern': trajectory.pattern,
                'stability': trajectory.stability_score,
                'feedback': trajectory.feedback,
            },
        },
    }

    if justification is not None:
        feedback_judge['dimensions']['justification'] = {
            'score': justification.score,
            'depth': justification.depth_label,
            'evidence': justification.evidence,
            'feedback': justification.feedback,
        }

    return AggregatedScore(
        reasoning_score_deterministic=round(det_score, 2),
        reasoning_score_full=round(full_score, 2) if full_score is not None else None,
        overall_band=overall_band,
        feedback_student=feedback_student,
        feedback_judge=feedback_judge,
    )
