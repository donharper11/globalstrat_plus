"""
Group 6 (continued): Engine Result Models for Financials, Performance, Coherence, Leaderboard.
Created in CC-06. Tables 6.4-6.9 + MarketIntelligenceBrief (7.2).
"""
from django.db import models


class RoundResultProductMarket(models.Model):
    """Table 6.4: Per-product per-market results for a round."""
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.PROTECT, related_name='product_market_results')
    round_number = models.IntegerField()
    team = models.ForeignKey('core.Team', on_delete=models.PROTECT, related_name='product_market_results')
    team_product = models.ForeignKey('core.TeamProduct', on_delete=models.PROTECT, related_name='round_results')
    market = models.ForeignKey('core.MarketDefinition', on_delete=models.PROTECT, related_name='product_market_results')
    units_produced = models.IntegerField(default=0)
    units_sold = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    units_unsold = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    retail_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    distribution_strategy = models.CharField(max_length=30, default='', blank=True)
    channel_margin_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    channel_margin_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    gross_local_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    local_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    home_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_cogs = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    logistics_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tariff_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    inventory_holding_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        db_table = 'round_result_product_market'
        unique_together = [('game', 'round_number', 'team', 'team_product', 'market')]

    def __str__(self):
        return f"{self.team_product.name} in {self.market.name} R{self.round_number}"


class RoundResultFinancials(models.Model):
    """Table 6.5: Consolidated financial results per team per round."""
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.PROTECT, related_name='financial_results')
    round_number = models.IntegerField()
    team = models.ForeignKey('core.Team', on_delete=models.PROTECT, related_name='financial_results')
    # Income statement
    gross_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_channel_margin = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_cogs = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    gross_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    rd_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    marketing_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    strategy_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    research_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    admin_overhead = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    logistics_tariff_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    inventory_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    operating_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    interest_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    pre_tax_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    # Balance sheet
    cash_opening = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    cash_closing = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_assets = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_debt = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_equity = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    plant_book_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    inventory_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    # Cash flow
    operating_cash_flow = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    investing_cash_flow = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    financing_cash_flow = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    dividends_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    # Ratios
    share_price = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    roe = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    debt_to_equity = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    gross_margin_pct = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    net_margin_pct = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    shareholder_return_cumulative = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    repatriation_costs = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="Profit lost to cross-border consolidation friction",
    )

    class Meta:
        db_table = 'round_result_financials'
        unique_together = [('game', 'round_number', 'team')]

    def __str__(self):
        return f"Financials: {self.team.name} R{self.round_number}"


class RoundResultMarketRevenue(models.Model):
    """Table 6.6: Revenue per team per market per round."""
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.PROTECT, related_name='market_revenue_results')
    round_number = models.IntegerField()
    team = models.ForeignKey('core.Team', on_delete=models.PROTECT, related_name='market_revenue_results')
    market = models.ForeignKey('core.MarketDefinition', on_delete=models.PROTECT, related_name='revenue_results')
    local_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    home_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    market_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    market_share_pct = models.DecimalField(max_digits=5, decimal_places=4, default=0)

    class Meta:
        db_table = 'round_result_market_revenue'
        unique_together = [('game', 'round_number', 'team', 'market')]

    def __str__(self):
        return f"Revenue: {self.team.name} in {self.market.name} R{self.round_number}"


class RoundResultPerformanceIndex(models.Model):
    """Table 6.7: Performance index per team per round."""
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.PROTECT, related_name='performance_results')
    round_number = models.IntegerField()
    team = models.ForeignKey('core.Team', on_delete=models.PROTECT, related_name='performance_results')
    satisfaction_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    index_change = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    index_value = models.DecimalField(max_digits=7, decimal_places=2, default=0)

    class Meta:
        db_table = 'round_result_performance_index'
        unique_together = [('game', 'round_number', 'team')]

    def __str__(self):
        return f"Index: {self.team.name} R{self.round_number} = {self.index_value}"


class RoundResultCoherence(models.Model):
    """Table 6.8: Strategic coherence per team per round."""
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.PROTECT, related_name='coherence_results')
    round_number = models.IntegerField()
    team = models.ForeignKey('core.Team', on_delete=models.PROTECT, related_name='coherence_results')
    formula_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    rag_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    blended_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    breakdown = models.JSONField(default=dict)

    class Meta:
        db_table = 'round_result_coherence'
        unique_together = [('game', 'round_number', 'team')]

    def __str__(self):
        return f"Coherence: {self.team.name} R{self.round_number} = {self.blended_score}"


class LeaderboardEntry(models.Model):
    """Table 6.9: Leaderboard per round."""
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.PROTECT, related_name='leaderboard_entries')
    round_number = models.IntegerField()
    team = models.ForeignKey('core.Team', on_delete=models.PROTECT, related_name='leaderboard_entries')
    rank = models.IntegerField()
    performance_index = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    shareholder_return = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    market_share_summary = models.JSONField(default=dict)

    class Meta:
        db_table = 'leaderboard_entry'
        unique_together = [('game', 'round_number', 'team')]

    def __str__(self):
        return f"#{self.rank} {self.team.name} R{self.round_number}"


class MarketIntelligenceBrief(models.Model):
    """Table 7.2: Market outlook briefs (basic placeholder for CC-11 RAG)."""
    BRIEF_LEVEL_CHOICES = [
        ('basic', 'Basic'),
        ('standard', 'Standard'),
        ('detailed', 'Detailed'),
    ]

    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey('core.Game', on_delete=models.CASCADE, related_name='intelligence_briefs')
    round_number = models.IntegerField()
    team = models.ForeignKey('core.Team', on_delete=models.CASCADE, null=True, blank=True, related_name='intelligence_briefs')
    market = models.ForeignKey('core.MarketDefinition', on_delete=models.PROTECT, related_name='intelligence_briefs')
    research_spend = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    brief_level = models.CharField(max_length=20, choices=BRIEF_LEVEL_CHOICES, default='basic')
    brief_content = models.TextField(default='')
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'market_intelligence_brief'
        unique_together = [('game', 'round_number', 'team', 'market')]

    def __str__(self):
        team_label = self.team.name if self.team else 'Global'
        return f"Brief: {self.market.name} R{self.round_number} ({team_label})"
