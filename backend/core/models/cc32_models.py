"""
CC-32A: Stakeholder Communication Layer.

Models:
- CommunicationAssignment (scenario-configured prompts)
- TeamCommunication (team submissions + LLM evaluations)
"""
from django.db import models


class CommunicationAssignment(models.Model):
    """
    Scenario-configured communication prompts triggered by
    specific decisions, events, or round milestones.
    """
    TRIGGER_CHOICES = [
        ('ROUND_MILESTONE', 'Fires at a specific round'),
        ('DECISION_BASED', 'Fires when team makes a specific decision'),
        ('EVENT_BASED', 'Fires when a specific event type hits the team'),
    ]

    AUDIENCE_CHOICES = [
        ('BOARD', 'Board of Directors'),
        ('EMPLOYEES', 'All Employees'),
        ('INVESTORS', 'Investor Community'),
        ('REGULATORS', 'Regulatory Authorities'),
        ('PUBLIC', 'Press / Public Statement'),
        ('PARTNER', 'Alliance / JV Partner'),
    ]

    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(
        'core.Scenario', on_delete=models.CASCADE,
        related_name='comm_assignments',
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    name_zh = models.CharField(max_length=200, blank=True, default='')

    trigger_type = models.CharField(max_length=30, choices=TRIGGER_CHOICES)
    trigger_condition = models.JSONField(
        help_text="E.g., {'round': 2} or {'event_category': ['GEOPOLITICAL', 'SANCTIONS']}",
    )

    audience = models.CharField(max_length=50, choices=AUDIENCE_CHOICES)
    prompt_text = models.TextField(
        help_text="Scenario/context shown to students explaining what to communicate and why",
    )
    prompt_text_zh = models.TextField(blank=True, default='')
    word_limit = models.IntegerField(default=300)

    evaluation_criteria = models.JSONField(
        help_text="List of {criterion, weight, description} dicts for LLM evaluation",
    )

    is_mandatory = models.BooleanField(default=False)
    coherence_weight = models.DecimalField(
        max_digits=4, decimal_places=2, default=0.05,
        help_text="How much this communication contributes to the coherence score",
    )
    display_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'communication_assignment'
        unique_together = ('scenario', 'code')
        ordering = ['display_order']

    def __str__(self):
        return f"{self.name} ({self.trigger_type})"


class TeamCommunication(models.Model):
    """
    A team's submitted communication for a specific assignment.
    """
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.CASCADE, related_name='communications')
    team = models.ForeignKey('core.Team', on_delete=models.CASCADE, related_name='communications')
    round = models.ForeignKey('core.Round', on_delete=models.CASCADE, related_name='communications')
    assignment = models.ForeignKey(
        CommunicationAssignment, on_delete=models.CASCADE,
        related_name='submissions',
    )

    content = models.TextField(default='', help_text="The team's drafted communication")
    word_count = models.IntegerField(default=0)

    submitted_at = models.DateTimeField(null=True, blank=True)
    is_draft = models.BooleanField(default=True)

    evaluation = models.JSONField(
        null=True, blank=True,
        help_text="LLM evaluation results: overall_score, criteria_scores, strengths, gaps, etc.",
    )
    coherence_contribution = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        help_text="Points added to coherence score based on evaluation quality",
    )

    class Meta:
        db_table = 'team_communication'
        unique_together = ('game', 'team', 'round', 'assignment')

    def __str__(self):
        status = 'Draft' if self.is_draft else 'Submitted'
        return f"{self.team.name} — {self.assignment.name} ({status})"
