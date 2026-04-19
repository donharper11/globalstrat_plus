"""
Instructor override models (CC-04 Amendment A1 §3).

Two tables let an instructor reshape, on a per-class basis:
  1. The progressive-disclosure unlock round for an individual decision field
     (CC-2 §8 baseline schedule).
  2. The resilience-score weight assigned to one of six resilience dimensions
     (scenario ResilienceParameters baseline weights).

Class-instance scope: in this codebase the class instance is `Game`. Each Game
corresponds to one run of the simulation for one section (course offering).
"""
from django.conf import settings
from django.db import models

from core.models.core import Game


class ClassProgressiveDisclosureOverride(models.Model):
    """
    Instructor-set override of the default progressive disclosure unlock round
    for a specific field, scoped to a single class (Game).

    Baseline schedule lives in CC-2 §8 and is mirrored in
    `core.utils.disclosure.DEFAULT_UNLOCK_ROUNDS`. This table captures
    deviations.
    """

    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name='disclosure_overrides',
        help_text="The Game (class instance) this override applies to.",
    )
    field_path = models.CharField(
        max_length=200,
        help_text="Dot-notation field path, e.g. 'sourcing.payment_terms'.",
    )
    override_unlock_round = models.IntegerField(
        help_text="Round at which the field unlocks for this class.",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='created_disclosure_overrides',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(max_length=500, blank=True)

    class Meta:
        db_table = 'class_progressive_disclosure_override'
        unique_together = [('game', 'field_path')]
        indexes = [
            models.Index(fields=['game']),
        ]

    def __str__(self):
        return f"{self.game} {self.field_path} -> round {self.override_unlock_round}"


class ClassResilienceWeightOverride(models.Model):
    """
    Instructor-set override of resilience score weights for a specific class.
    Baseline weights live in the scenario's ResilienceParameters row; the
    combined weight set (overrides + non-overridden scenario defaults) must
    sum to 1.0 (±0.01) — enforced at serializer level (see CC-04 A1 §3.3).
    """

    WEIGHT_CHOICES = [
        ('multi_sourcing', 'Multi-sourcing'),
        ('geographic_diversity', 'Geographic Diversity'),
        ('buffer_inventory_adequacy', 'Buffer Inventory Adequacy'),
        ('modal_flexibility', 'Modal Flexibility'),
        ('tier_2_visibility', 'Tier-2 Visibility'),
        ('supplier_financial_health', 'Supplier Financial Health'),
    ]

    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name='resilience_weight_overrides',
    )
    weight_name = models.CharField(max_length=50, choices=WEIGHT_CHOICES)
    override_value = models.DecimalField(max_digits=4, decimal_places=3)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='created_weight_overrides',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(max_length=500, blank=True)

    class Meta:
        db_table = 'class_resilience_weight_override'
        unique_together = [('game', 'weight_name')]

    def __str__(self):
        return f"{self.game} {self.weight_name} -> {self.override_value}"
