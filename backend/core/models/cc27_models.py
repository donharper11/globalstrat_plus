"""
CC-27: Strategic Briefing Models.

Auto-generated strategic briefings delivered to each team after round processing.
Read status tracked per-user so each team member sees the splash independently.
"""
from django.db import models


class StrategicBriefing(models.Model):
    """
    Auto-generated strategic briefing delivered to each team after round processing.
    One briefing per team per round.
    """
    game = models.ForeignKey(
        'core.Game', on_delete=models.CASCADE, related_name='strategic_briefings',
    )
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='strategic_briefings',
    )
    round_number = models.IntegerField()

    executive_summary = models.TextField()
    performance_analysis = models.JSONField()
    investment_returns = models.JSONField()
    investor_sentiment = models.JSONField()
    competitive_landscape = models.JSONField()
    strategic_recommendations = models.JSONField()
    risk_alerts = models.JSONField(default=list)

    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'strategic_briefing'
        unique_together = [('game', 'team', 'round_number')]
        ordering = ['-round_number']

    def __str__(self):
        return f"Briefing: {self.team.name} R{self.round_number}"


class BriefingReadStatus(models.Model):
    """
    Per-user read tracking for strategic briefings.
    Each student independently marks briefings as read.
    """
    briefing = models.ForeignKey(
        StrategicBriefing, on_delete=models.CASCADE, related_name='read_statuses',
    )
    user = models.ForeignKey(
        'core.User', on_delete=models.CASCADE, related_name='briefing_reads',
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'briefing_read_status'
        unique_together = [('briefing', 'user')]

    def __str__(self):
        return f"{self.user} read {self.briefing}"
