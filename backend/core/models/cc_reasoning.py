"""
Strategic Reasoning Evaluator Models.

Two models:
- RoundResultReasoningAnalysis: per-team per-round reasoning quality scores
- CompetitionReasoningAggregate: cross-round aggregate for competition judging
"""
from django.db import models


class RoundResultReasoningAnalysis(models.Model):
    """Per-team per-round reasoning quality analysis.

    Dimensions 1-3 are deterministic (Phase 1), dimension 4 is LLM-based (Phase 2).
    reasoning_score_deterministic is R40-safe for competition grading.
    reasoning_score_full includes LLM dimension and is excluded from competition grading.
    """
    PATTERN_CHOICES = [
        ('consistent', 'Consistent Executor'),
        ('reactive', 'Reactive Adjuster'),
        ('aggressive', 'Aggressive Expander'),
        ('conservative', 'Conservative Optimizer'),
        ('erratic', 'Erratic'),
    ]
    BAND_CHOICES = [
        ('strong', 'Strong'),
        ('developing', 'Developing'),
        ('needs_attention', 'Needs Attention'),
    ]

    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey(
        'core.Game', on_delete=models.PROTECT,
        related_name='reasoning_analyses',
    )
    team = models.ForeignKey(
        'core.Team', on_delete=models.PROTECT,
        related_name='reasoning_analyses',
    )
    round_number = models.IntegerField()

    # Aggregate scores
    reasoning_score_deterministic = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='R40-safe aggregate of dims 1-3 (0-100)',
    )
    reasoning_score_full = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Full aggregate including LLM dim 4 (0-100). Excluded from competition grading.',
    )

    # Per-dimension scores (0-100)
    coherence_ext_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Dim 1: Extended coherence (5 sub-dimensions)',
    )
    responsiveness_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Dim 2: Signal responsiveness',
    )
    trajectory_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Dim 3: Strategic trajectory consistency',
    )
    justification_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Dim 4: LLM justification quality (Phase 2, MODEL_DERIVED)',
    )

    # Breakdowns (JSON detail)
    coherence_ext_breakdown = models.JSONField(default=dict)
    responsiveness_breakdown = models.JSONField(default=dict)
    trajectory_breakdown = models.JSONField(default=dict)
    justification_breakdown = models.JSONField(null=True, blank=True)

    # Classification
    trajectory_pattern = models.CharField(
        max_length=30, choices=PATTERN_CHOICES, default='consistent',
    )
    overall_band = models.CharField(
        max_length=20, choices=BAND_CHOICES, default='developing',
    )

    # Feedback (populated in Phase 2 or via templates)
    feedback_student = models.JSONField(
        null=True, blank=True,
        help_text='Per-dimension qualitative feedback for students (no raw scores)',
    )
    feedback_judge = models.JSONField(
        null=True, blank=True,
        help_text='Per-dimension numeric + evidence for instructors/judges',
    )

    # Metadata
    engine_version = models.CharField(max_length=20, default='1.0')
    phase2_completed = models.BooleanField(default=False)

    class Meta:
        db_table = 'round_result_reasoning_analysis'
        unique_together = [('game', 'round_number', 'team')]

    def __str__(self):
        return (
            f"Reasoning: {self.team.name} R{self.round_number} "
            f"= {self.reasoning_score_deterministic} ({self.overall_band})"
        )


class CompetitionReasoningAggregate(models.Model):
    """Cross-round reasoning aggregate for competition judging."""
    TREND_CHOICES = [
        ('improving', 'Improving'),
        ('stable', 'Stable'),
        ('declining', 'Declining'),
    ]

    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey(
        'core.Game', on_delete=models.PROTECT,
        related_name='reasoning_aggregates',
    )
    team = models.ForeignKey(
        'core.Team', on_delete=models.PROTECT,
        related_name='reasoning_aggregates',
    )

    aggregate_reasoning_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Avg deterministic reasoning score across rounds',
    )
    rounds_evaluated = models.IntegerField(default=0)

    # Per-dimension averages
    avg_coherence_ext = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    avg_responsiveness = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    avg_trajectory = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Pattern analysis
    dominant_pattern = models.CharField(max_length=30, default='consistent')
    pattern_consistency = models.DecimalField(
        max_digits=3, decimal_places=2, default=0,
        help_text='0-1, how consistently one pattern held across rounds',
    )
    score_trend = models.CharField(
        max_length=15, choices=TREND_CHOICES, default='stable',
    )

    # Full round-level detail for drill-down
    round_by_round = models.JSONField(default=dict)

    class Meta:
        db_table = 'competition_reasoning_aggregate'
        unique_together = [('game', 'team')]

    def __str__(self):
        return (
            f"ReasoningAgg: {self.team.name} "
            f"= {self.aggregate_reasoning_score} ({self.dominant_pattern})"
        )
