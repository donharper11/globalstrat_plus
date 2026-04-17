"""
CC-16: Talent & Workforce Models.

DecisionTalent — Per-round talent investment decisions.
TeamTalentState — Cumulative talent state tracking per pool per round.
"""
from django.db import models


class DecisionTalent(models.Model):
    """Per-round talent investment decisions. One record per submission."""
    SALARY_LEVEL_CHOICES = [
        (1, 'Below Market ($60K/yr)'),
        (2, 'Market Rate ($90K/yr)'),
        (3, 'Above Market ($120K/yr)'),
        (4, 'Premium ($160K/yr)'),
        (5, 'Top of Market ($220K/yr)'),
    ]

    id = models.BigAutoField(primary_key=True)
    submission = models.OneToOneField(
        'core.DecisionSubmission', on_delete=models.CASCADE,
        related_name='talent',
    )

    # R&D Talent Pool
    rd_headcount = models.IntegerField(default=50)
    rd_salary_level = models.IntegerField(default=3, choices=SALARY_LEVEL_CHOICES)
    rd_training_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Commercial Talent Pool
    commercial_headcount = models.IntegerField(default=30)
    commercial_salary_level = models.IntegerField(default=3, choices=SALARY_LEVEL_CHOICES)
    commercial_training_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Operations Talent Pool
    operations_headcount = models.IntegerField(default=40)
    operations_salary_level = models.IntegerField(default=3, choices=SALARY_LEVEL_CHOICES)
    operations_training_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        db_table = 'decision_talent'

    def __str__(self):
        return f"Talent decisions for {self.submission}"


class TeamTalentState(models.Model):
    """Tracks cumulative talent state for each talent pool per round."""
    POOL_CHOICES = [
        ('rd', 'R&D'),
        ('commercial', 'Commercial'),
        ('operations', 'Operations'),
    ]

    id = models.BigAutoField(primary_key=True)
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='talent_states',
    )
    talent_pool = models.CharField(max_length=30, choices=POOL_CHOICES)
    headcount = models.IntegerField(default=0)
    salary_level = models.IntegerField(default=3)
    cumulative_training = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    talent_level = models.DecimalField(max_digits=5, decimal_places=2, default=3.00)
    turnover_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.1000)
    round_number = models.IntegerField()

    class Meta:
        db_table = 'team_talent_state'
        unique_together = [('team', 'talent_pool', 'round_number')]

    def __str__(self):
        return f"{self.team.name} — {self.talent_pool} R{self.round_number} (level {self.talent_level})"
