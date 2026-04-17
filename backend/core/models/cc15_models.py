"""
CC-15: New Feature Page Models.

TeamFrameworkAnalysis — stores student framework analyses (Porter, PESTLE, SWOT, etc.)
ForecastScenario — stores what-if projection scenarios
"""
from django.db import models


class TeamFrameworkAnalysis(models.Model):
    FRAMEWORK_CHOICES = [
        ('porter', 'Porter\'s Five Forces'),
        ('pestle', 'PESTLE Analysis'),
        ('swot', 'SWOT Analysis'),
        ('entry_matrix', 'Market Entry Decision Matrix'),
        ('ansoff', 'Ansoff Growth Matrix'),
    ]

    id = models.BigAutoField(primary_key=True)
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='framework_analyses',
    )
    round_number = models.IntegerField()
    framework_type = models.CharField(max_length=50, choices=FRAMEWORK_CHOICES)
    market = models.ForeignKey(
        'core.MarketDefinition', on_delete=models.PROTECT,
        null=True, blank=True, related_name='framework_analyses',
    )
    analysis_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'team_framework_analysis'

    def __str__(self):
        return f"{self.team.name} — {self.framework_type} R{self.round_number}"


class ForecastScenario(models.Model):
    id = models.BigAutoField(primary_key=True)
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='forecast_scenarios',
    )
    round_number = models.IntegerField()
    name = models.CharField(max_length=200)
    parameters = models.JSONField(default=dict)
    projected_results = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'forecast_scenario'

    def __str__(self):
        return f"{self.team.name} — {self.name} R{self.round_number}"
