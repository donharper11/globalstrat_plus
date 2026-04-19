from django.db import models


class ScoreType(models.Model):
    score_type_id = models.AutoField(primary_key=True)
    score_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'score_types'

    def __str__(self):
        return self.score_name


class Score(models.Model):
    score_id = models.AutoField(primary_key=True)
    team_id = models.IntegerField(blank=True, null=True)
    round_id = models.IntegerField(blank=True, null=True)
    stakeholder_id = models.IntegerField(blank=True, null=True)
    score_type_id = models.IntegerField(blank=True, null=True)
    score = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    feedback = models.TextField(blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'scores'

    def __str__(self):
        return f"Score {self.score} (Team {self.team_id}, Round {self.round_id})"


class LeaderboardMetric(models.Model):
    metric_id = models.AutoField(primary_key=True)
    metric_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'leaderboard_metrics'

    def __str__(self):
        return self.metric_name


class LeaderboardScore(models.Model):
    leaderboard_id = models.AutoField(primary_key=True)
    team_id = models.IntegerField(blank=True, null=True)
    round_id = models.IntegerField(blank=True, null=True)
    metric_id = models.IntegerField(blank=True, null=True)
    score = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'leaderboard_scores'

    def __str__(self):
        return f"Leaderboard: Team {self.team_id}, Score {self.score}"


class TeamPerformance(models.Model):
    performance_id = models.AutoField(primary_key=True)
    team_id = models.IntegerField(blank=True, null=True)
    total_score = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    average_stakeholder_satisfaction = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    ethical_alignment = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'team_performance'

    def __str__(self):
        return f"Performance: Team {self.team_id}, Total {self.total_score}"
