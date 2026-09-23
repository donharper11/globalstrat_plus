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

    # W-CE2-08's residue, closed as W-CE3-08's second half. An alert is
    # written in the language stored at processing time, so every alert
    # written before an instructor set their language stayed English for
    # ever and the panel was permanently mixed. The alert cannot be
    # re-rendered from what it stores -- unlike a coherence breakdown, the
    # row keeps no numbers, only the finished sentence -- so the inputs are
    # stored here: {'key': …, 'language': …, 'values': {…}}.
    #
    # It is a rendering input, not a computed outcome, and it is excluded
    # from both manifest sections with that justification, so no hashed value
    # changes and the envelope stays where it is. Empty for an alert written
    # before this field existed, and for one whose text a model wrote; both
    # are then served exactly as stored.
    render_context = models.JSONField(blank=True, null=True, default=None)

    # Which side of the Phase-1/Phase-2 boundary wrote this row. Engine alerts
    # are part of the round's deterministic output and are hashed; narrative
    # alerts are Phase-2 prose and are not. Before this they shared one table
    # and one manifest section, so a coaching note arriving after resolution
    # changed a hashed section.
    SOURCE_CHOICES = [('engine', 'Deterministic engine'),
                      ('narrative', 'Phase-2 narrative')]
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES,
                              default='engine')

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
