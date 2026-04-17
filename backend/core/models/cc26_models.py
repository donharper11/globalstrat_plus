"""
CC-26: AI Capital Markets Models.

AI investor funds that evaluate teams based on different investment philosophies,
trade shares, and drive share price through sentiment-weighted demand.
"""
from decimal import Decimal
from django.db import models


class AIInvestorFund(models.Model):
    """
    An AI-driven investment fund that evaluates and trades company shares.
    Three funds with different investment philosophies.
    """
    scenario = models.ForeignKey(
        'core.Scenario', on_delete=models.CASCADE, related_name='investor_funds',
    )
    name = models.CharField(max_length=200)
    name_zh = models.CharField(max_length=200, blank=True, default='')
    code = models.CharField(max_length=30)
    description = models.TextField()
    description_zh = models.TextField(blank=True, default='')
    investment_philosophy = models.CharField(max_length=30, choices=[
        ('growth', 'Growth — chases revenue growth, R&D, expansion'),
        ('value', 'Value — wants low debt, strong margins, dividends'),
        ('esg', 'ESG — weights sustainability, governance, social impact'),
    ])
    initial_holding_pct = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.10'),
    )
    max_holding_pct = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.20'),
    )
    min_holding_pct = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.02'),
    )
    trade_aggressiveness = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal('0.30'),
        help_text='Fraction of target change executed per round (0-1)',
    )
    profile = models.JSONField(
        null=True, blank=True,
        help_text="Fund strategy profile for student-facing display",
    )

    class Meta:
        db_table = 'ai_investor_fund'
        unique_together = [('scenario', 'code')]

    def __str__(self):
        return f"{self.name} ({self.investment_philosophy})"


class AIInvestorPreference(models.Model):
    """
    What each fund looks for in a company. Uses same preference model
    as segment preferences — feature code, ideal value, weight, tolerance.
    """
    fund = models.ForeignKey(
        AIInvestorFund, on_delete=models.CASCADE, related_name='preferences',
    )
    feature_code = models.CharField(max_length=50)
    feature_label = models.CharField(max_length=200)
    ideal_value = models.DecimalField(max_digits=5, decimal_places=2)
    weight = models.DecimalField(max_digits=5, decimal_places=4)
    tolerance = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('2.50'),
    )

    class Meta:
        db_table = 'ai_investor_preference'
        unique_together = [('fund', 'feature_code')]

    def __str__(self):
        return f"{self.fund.name}: {self.feature_label} (w={self.weight})"


class AIInvestorHolding(models.Model):
    """
    Tracks each fund's shareholding in each team, per round.
    Creates a full audit trail of investor behavior.
    """
    game = models.ForeignKey(
        'core.Game', on_delete=models.CASCADE, related_name='investor_holdings',
    )
    fund = models.ForeignKey(
        AIInvestorFund, on_delete=models.CASCADE, related_name='holdings',
    )
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='investor_holdings',
    )
    round_number = models.IntegerField()
    shares_held = models.IntegerField()
    holding_pct = models.DecimalField(max_digits=7, decimal_places=4)
    satisfaction_score = models.DecimalField(max_digits=5, decimal_places=4)
    action = models.CharField(max_length=10, choices=[
        ('buy', 'Bought shares'),
        ('sell', 'Sold shares'),
        ('hold', 'Held position'),
        ('initial', 'Initial allocation'),
    ])
    shares_traded = models.IntegerField(default=0)
    trade_reason = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        db_table = 'ai_investor_holding'
        unique_together = [('game', 'fund', 'team', 'round_number')]
        ordering = ['round_number', 'fund']

    def __str__(self):
        return f"{self.fund.name} → {self.team.name} R{self.round_number}: {self.action}"


class SharePriceHistory(models.Model):
    """Records share price each round with the components that drove it."""
    game = models.ForeignKey(
        'core.Game', on_delete=models.CASCADE, related_name='share_price_history',
    )
    team = models.ForeignKey(
        'core.Team', on_delete=models.CASCADE, related_name='share_price_history',
    )
    round_number = models.IntegerField()
    book_value_per_share = models.DecimalField(max_digits=15, decimal_places=2)
    sentiment_multiplier = models.DecimalField(max_digits=5, decimal_places=4)
    share_price = models.DecimalField(max_digits=15, decimal_places=2)
    total_shares_outstanding = models.IntegerField()
    market_cap = models.DecimalField(max_digits=15, decimal_places=2)
    velocity_satisfaction = models.DecimalField(max_digits=5, decimal_places=4)
    granite_satisfaction = models.DecimalField(max_digits=5, decimal_places=4)
    greenhorizon_satisfaction = models.DecimalField(max_digits=5, decimal_places=4)
    aggregate_demand = models.DecimalField(max_digits=5, decimal_places=4)

    class Meta:
        db_table = 'share_price_history'
        unique_together = [('game', 'team', 'round_number')]

    def __str__(self):
        return f"{self.team.name} R{self.round_number}: ${self.share_price}"
