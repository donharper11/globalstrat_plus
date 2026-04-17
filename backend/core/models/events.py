from django.db import models


class TriggeredEvent(models.Model):
    triggered_event_id = models.AutoField(primary_key=True)
    event_id = models.IntegerField(blank=True, null=True)
    round_id = models.IntegerField(blank=True, null=True)
    team_id = models.IntegerField(blank=True, null=True)
    resolved = models.BooleanField(blank=True, null=True)
    resolution_details = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'triggered_events'

    def __str__(self):
        return f"TriggeredEvent {self.triggered_event_id}: Event {self.event_id}, Team {self.team_id}"
