from django.db import models


class Achievement(models.Model):
    achievement_id = models.AutoField(primary_key=True)
    achievement_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    criteria = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'achievements'

    def __str__(self):
        return self.achievement_name


class GamificationBadge(models.Model):
    badge_id = models.AutoField(primary_key=True)
    badge_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    criteria = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'gamification_badges'

    def __str__(self):
        return self.badge_name


class PlayerProgress(models.Model):
    progress_id = models.AutoField(primary_key=True)
    game_id = models.IntegerField()
    round_number = models.IntegerField()
    team_id = models.IntegerField()
    milestone_id = models.IntegerField(blank=True, null=True)
    achieved_at = models.DateTimeField(blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'player_progress'

    def __str__(self):
        return f"Progress: Team {self.team_id}, Round {self.round_number}"


class TeamAchievement(models.Model):
    team_achievement_id = models.AutoField(primary_key=True)
    team_id = models.IntegerField(blank=True, null=True)
    achievement_id = models.IntegerField(blank=True, null=True)
    round_id = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'team_achievements'

    def __str__(self):
        return f"Team {self.team_id} — Achievement {self.achievement_id}"


class TeamBadge(models.Model):
    team_badge_id = models.AutoField(primary_key=True)
    team_id = models.IntegerField(blank=True, null=True)
    badge_id = models.IntegerField(blank=True, null=True)
    round_id = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'team_badges'

    def __str__(self):
        return f"Team {self.team_id} — Badge {self.badge_id}"
