from django.db import models


class ProgramType(models.Model):
    program_type_id = models.AutoField(primary_key=True)
    program_type_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    base_cost = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    unit_price = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    cogs_per_unit = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    economy_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'program_types'

    def __str__(self):
        return self.program_type_name


class Program(models.Model):
    program_id = models.AutoField(primary_key=True)
    program_name = models.CharField(max_length=255)
    program_type_id = models.IntegerField()
    round_launched = models.IntegerField()
    status = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    modified_at = models.DateTimeField(blank=True, null=True)
    # numeric in PG — no FK to teams (per CLAUDE.md)
    team_id = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    # R&D development time fields
    development_status = models.CharField(max_length=20, default='ready')
    development_rounds_total = models.IntegerField(default=0)
    development_rounds_remaining = models.IntegerField(default=0)
    r_and_d_investment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    development_started_round = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'programs'

    def __str__(self):
        return self.program_name


class ProgramPortfolio(models.Model):
    program_portfolio_id = models.AutoField(primary_key=True)
    program_portfolio_name = models.CharField(max_length=100)
    program_portfolio_notes = models.TextField()
    program_id = models.IntegerField()
    round_launched = models.IntegerField(blank=True, null=True)
    round_modified = models.IntegerField(blank=True, null=True)
    modified_status = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'program_portfolio'

    def __str__(self):
        return self.program_portfolio_name


class ProgramFeature(models.Model):
    program_feature_id = models.AutoField(primary_key=True)
    feature_id = models.IntegerField()
    program_id = models.IntegerField()
    feature_value = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    program_portfolio_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'program_features'

    def __str__(self):
        return f"Feature {self.feature_id} = {self.feature_value} (Program {self.program_id})"


class Decision(models.Model):
    decision_id = models.AutoField(primary_key=True)
    team_id = models.IntegerField(blank=True, null=True)
    round_id = models.IntegerField(blank=True, null=True)
    feature_id = models.IntegerField(blank=True, null=True)
    feature_value = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    budget_allocation = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'decisions'

    def __str__(self):
        return f"Decision {self.decision_id}: Team {self.team_id}, Round {self.round_id}"
