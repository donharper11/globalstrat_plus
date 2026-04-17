from django.db import models


class InstructorAlert(models.Model):
    """
    AI-generated alerts for the instructor about team behavior.
    Generated after each round advance and when significant decisions are locked.
    """
    game = models.ForeignKey('core.Game', on_delete=models.CASCADE, related_name='instructor_alerts')
    team = models.ForeignKey('core.Team', on_delete=models.CASCADE, related_name='instructor_alerts')
    round_number = models.IntegerField()
    alert_type = models.CharField(max_length=30, choices=[
        ('strategic', 'Strategic Concern'),
        ('financial', 'Financial Warning'),
        ('missed_opportunity', 'Missed Opportunity'),
        ('notable_move', 'Notable Decision'),
        ('learning_moment', 'Teaching Opportunity'),
        ('distress', 'Team in Distress'),
    ])
    severity = models.CharField(max_length=10, choices=[
        ('info', 'Informational'),
        ('watch', 'Watch'),
        ('concern', 'Concern'),
        ('critical', 'Critical'),
    ])
    title = models.CharField(max_length=300)
    detail = models.TextField()
    teaching_note = models.TextField(blank=True, default='')
    acknowledged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'instructor_alert'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.severity}] {self.title}"


class DecisionChangeLog(models.Model):
    """Tracks individual decision changes for team notification."""
    team = models.ForeignKey('core.Team', on_delete=models.CASCADE, related_name='change_logs')
    user = models.ForeignKey('core.User', on_delete=models.CASCADE, related_name='change_logs')
    round_number = models.IntegerField()
    page = models.CharField(max_length=50)
    change_description = models.CharField(max_length=500)
    change_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'decision_change_log'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.team.name} - {self.change_description}"
