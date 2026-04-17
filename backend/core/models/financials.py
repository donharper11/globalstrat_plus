from django.db import models


class TeamIncomeStatement(models.Model):
    statement_id = models.AutoField(primary_key=True)
    team_id = models.IntegerField(blank=True, null=True)
    round_id = models.IntegerField(blank=True, null=True)
    revenue = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    program_expenses = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True, db_column='csr_expenses')
    cogs = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    operating_costs = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    net_profit = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'team_income_statements'

    def __str__(self):
        return f"Income: Team {self.team_id}, Round {self.round_id}"


class TeamBalanceSheet(models.Model):
    balance_id = models.AutoField(primary_key=True)
    team_id = models.IntegerField(blank=True, null=True)
    round_id = models.IntegerField(blank=True, null=True)
    assets = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    liabilities = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    equity = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    retained_earnings = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    loan_balance = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True, default=0)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'team_balance_sheets'

    def __str__(self):
        return f"Balance: Team {self.team_id}, Round {self.round_id}"


class TeamCashFlow(models.Model):
    cashflow_id = models.AutoField(primary_key=True)
    team_id = models.IntegerField(blank=True, null=True)
    round_id = models.IntegerField(blank=True, null=True)
    cash_inflows = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    cash_outflows = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    operating_activities = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    investing_activities = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    financing_activities = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    net_cash_change = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'team_cash_flows'

    def __str__(self):
        return f"CashFlow: Team {self.team_id}, Round {self.round_id}"


class TeamResources(models.Model):
    resource_id = models.AutoField(primary_key=True)
    team_id = models.IntegerField(blank=True, null=True)
    round_id = models.IntegerField(blank=True, null=True)
    budget = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    resources_allocated = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'team_resources'

    def __str__(self):
        return f"Resources: Team {self.team_id}, Round {self.round_id}"


class FinancialRevenue(models.Model):
    revenue_id = models.AutoField(primary_key=True)
    round_id = models.IntegerField(blank=True, null=True)
    team_id = models.IntegerField(blank=True, null=True)
    program_id = models.IntegerField(blank=True, null=True)
    se_units = models.IntegerField(blank=True, null=True)
    revenue = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'financial_revenue'

    def __str__(self):
        return f"Revenue {self.revenue} (Team {self.team_id}, Round {self.round_id})"


class FinancialExpense(models.Model):
    expense_id = models.AutoField(primary_key=True)
    round_id = models.IntegerField(blank=True, null=True)
    team_id = models.IntegerField(blank=True, null=True)
    program_id = models.IntegerField(blank=True, null=True)
    expense_type = models.CharField(max_length=50, blank=True, null=True)
    cost_amount = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'financial_expenses'

    def __str__(self):
        return f"Expense {self.cost_amount} ({self.expense_type}, Team {self.team_id})"


class NewSalesByRound(models.Model):
    round_id = models.IntegerField(primary_key=True)
    customer_id = models.IntegerField()
    program_id = models.IntegerField()
    new_sales = models.IntegerField(blank=True, null=True)
    instance_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'new_sales_by_round'
        unique_together = (('round_id', 'customer_id', 'program_id'),)

    def __str__(self):
        return f"NewSales: Customer {self.customer_id}, Program {self.program_id}, Round {self.round_id}"
