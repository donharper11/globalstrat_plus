"""
Group 3: Game Instance Models (adapted from BECSR, spec 04-data-model.md 3.1-3.4)
Plus retained BECSR infrastructure models (managed=False).
"""
from django.db import models
from django.conf import settings


# ---------------------------------------------------------------------------
# Group 3: Game Instance (managed=True, new schema)
# ---------------------------------------------------------------------------

class Game(models.Model):
    STATUS_CHOICES = [
        ('setup', 'Setup'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]

    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(
        'core.Scenario', on_delete=models.PROTECT, related_name='games',
    )
    section_id = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=200)
    current_round = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='setup')
    round_deadline = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='created_games',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'game'

    def __str__(self):
        return self.name


class Team(models.Model):
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey(Game, on_delete=models.PROTECT, related_name='teams')
    name = models.CharField(max_length=200)
    firm_starter_profile = models.ForeignKey(
        'core.FirmStarterProfile', on_delete=models.PROTECT,
        related_name='teams',
    )
    performance_index = models.DecimalField(max_digits=7, decimal_places=2)
    cash_on_hand = models.DecimalField(max_digits=15, decimal_places=2)
    total_debt = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_equity = models.DecimalField(max_digits=15, decimal_places=2)
    shares_outstanding = models.IntegerField(default=1000000)
    share_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    home_market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='home_teams',
        help_text="Team's country of origin. Affects trust, cultural distance, repatriation costs.",
    )
    is_in_distress = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'team'

    def __str__(self):
        return self.name

    # Backward-compat properties for CC-1 services still referencing old field names
    @property
    def team_id(self):
        return self.id

    @property
    def team_name(self):
        return self.name


class TeamMember(models.Model):
    ROLE_CHOICES = [
        ('leader', 'Leader'),
        ('member', 'Member'),
    ]

    id = models.BigAutoField(primary_key=True)
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name='members')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='team_memberships',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'team_member'
        unique_together = [('team', 'user')]

    def __str__(self):
        return f"{self.user} — {self.team.name} ({self.role})"


class Round(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('processed', 'Processed'),
    ]

    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey(Game, on_delete=models.PROTECT, related_name='rounds')
    round_number = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    opened_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    # CC-32H: Two-phase processing status
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Not yet processed'),
            ('PROCESSING', 'Phase 1 in progress'),
            ('RESULTS_AVAILABLE', 'Numbers ready, narratives pending'),
            ('FULLY_COMPLETE', 'All content generated'),
            ('FAILED', 'Processing failed'),
        ],
        default='PENDING',
    )
    narrative_generated = models.BooleanField(default=False)
    narrative_error = models.TextField(blank=True, default='')
    phase_1_duration = models.FloatField(null=True, blank=True)
    phase_2_duration = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = 'round'
        unique_together = [('game', 'round_number')]

    def __str__(self):
        return f"Round {self.round_number} (Game {self.game_id})"

    # Backward-compat property for CC-1 services
    @property
    def round_id(self):
        return self.id


# ---------------------------------------------------------------------------
# BECSR Infrastructure (managed=False — retained from CC-1)
# These are legacy models mapping to raw SQL tables.
# They will be adapted or replaced in future CC sessions.
# ---------------------------------------------------------------------------

class User(models.Model):
    user_id = models.AutoField(primary_key=True)
    username = models.CharField(unique=True, max_length=255)
    password_hash = models.TextField()
    role = models.CharField(max_length=50, blank=True, null=True)
    team_id = models.IntegerField(blank=True, null=True)
    email = models.CharField(max_length=200, blank=True, null=True)
    student_id = models.CharField(max_length=50, blank=True, null=True)
    display_name = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'users'

    def __str__(self):
        return self.username


class SimulationState(models.Model):
    state_id = models.AutoField(primary_key=True)
    current_round_id = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'simulation_state'

    def __str__(self):
        return f"State {self.state_id} — Round {self.current_round_id}"


class SimulationSettings(models.Model):
    setting_id = models.AutoField(primary_key=True)
    setting_name = models.CharField(max_length=255)
    setting_value = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'simulation_settings'

    def __str__(self):
        return self.setting_name


class SimulationParameters(models.Model):
    parameter_id = models.AutoField(primary_key=True)
    parameter_name = models.CharField(max_length=255)
    parameter_value = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'simulation_parameters'

    def __str__(self):
        return self.parameter_name
