"""CC-5 §5.5 Group B: Promote Financials ghosts (6 of 7 models).

Promotes 6 Financials ghost models and creates their physical tables via
SeparateDatabaseAndState (CC-3.5 pattern). Also retroactively aligns
Group A Meta options state (0044 recorded options={} while models declare
managed=True) so makemigrations produces no further diff.

Promoted (6):
- TeamIncomeStatement → team_income_statements
- TeamBalanceSheet → team_balance_sheets
- TeamCashFlow → team_cash_flows
- TeamResources → team_resources
- FinancialRevenue → financial_revenue
- FinancialExpense → financial_expenses

HALTED pending schema clarification (1): NewSalesByRound — round_id as
primary_key=True conflicts with unique_together on (round_id, customer_id,
program_id). See promotion_questions.md.

TeamIncomeStatement.program_expenses maps to DB column csr_expenses via
db_column='csr_expenses'. All FKs are plain IntegerField columns (no
ForeignKey constraints).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0044_cc05_promote_group_a_gamification_scoring'),
    ]

    operations = [
        migrations.AlterModelOptions(name='achievement', options={'managed': True}),
        migrations.AlterModelOptions(name='gamificationbadge', options={'managed': True}),
        migrations.AlterModelOptions(name='playerprogress', options={'managed': True}),
        migrations.AlterModelOptions(name='teamachievement', options={'managed': True}),
        migrations.AlterModelOptions(name='teambadge', options={'managed': True}),
        migrations.AlterModelOptions(name='scoretype', options={'managed': True}),
        migrations.AlterModelOptions(name='score', options={'managed': True}),
        migrations.AlterModelOptions(name='leaderboardmetric', options={'managed': True}),
        migrations.AlterModelOptions(name='leaderboardscore', options={'managed': True}),
        migrations.AlterModelOptions(name='teamperformance', options={'managed': True}),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(name='teamincomestatement', options={'managed': True}),
                migrations.AlterModelOptions(name='teambalancesheet', options={'managed': True}),
                migrations.AlterModelOptions(name='teamcashflow', options={'managed': True}),
                migrations.AlterModelOptions(name='teamresources', options={'managed': True}),
                migrations.AlterModelOptions(name='financialrevenue', options={'managed': True}),
                migrations.AlterModelOptions(name='financialexpense', options={'managed': True}),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS team_income_statements (
                            statement_id SERIAL PRIMARY KEY,
                            team_id INTEGER NULL,
                            round_id INTEGER NULL,
                            revenue NUMERIC(20, 2) NULL,
                            csr_expenses NUMERIC(20, 2) NULL,
                            cogs NUMERIC(20, 2) NULL,
                            operating_costs NUMERIC(20, 2) NULL,
                            net_profit NUMERIC(20, 2) NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS team_income_statements_team_round_idx
                            ON team_income_statements (team_id, round_id);

                        CREATE TABLE IF NOT EXISTS team_balance_sheets (
                            balance_id SERIAL PRIMARY KEY,
                            team_id INTEGER NULL,
                            round_id INTEGER NULL,
                            assets NUMERIC(20, 2) NULL,
                            liabilities NUMERIC(20, 2) NULL,
                            equity NUMERIC(20, 2) NULL,
                            retained_earnings NUMERIC(20, 2) NULL,
                            loan_balance NUMERIC(20, 2) NULL DEFAULT 0,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS team_balance_sheets_team_round_idx
                            ON team_balance_sheets (team_id, round_id);

                        CREATE TABLE IF NOT EXISTS team_cash_flows (
                            cashflow_id SERIAL PRIMARY KEY,
                            team_id INTEGER NULL,
                            round_id INTEGER NULL,
                            cash_inflows NUMERIC(20, 2) NULL,
                            cash_outflows NUMERIC(20, 2) NULL,
                            operating_activities NUMERIC(20, 2) NULL,
                            investing_activities NUMERIC(20, 2) NULL,
                            financing_activities NUMERIC(20, 2) NULL,
                            net_cash_change NUMERIC(20, 2) NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS team_cash_flows_team_round_idx
                            ON team_cash_flows (team_id, round_id);

                        CREATE TABLE IF NOT EXISTS team_resources (
                            resource_id SERIAL PRIMARY KEY,
                            team_id INTEGER NULL,
                            round_id INTEGER NULL,
                            budget NUMERIC(10, 2) NULL,
                            resources_allocated NUMERIC(10, 2) NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS team_resources_team_round_idx
                            ON team_resources (team_id, round_id);

                        CREATE TABLE IF NOT EXISTS financial_revenue (
                            revenue_id SERIAL PRIMARY KEY,
                            round_id INTEGER NULL,
                            team_id INTEGER NULL,
                            program_id INTEGER NULL,
                            se_units INTEGER NULL,
                            revenue NUMERIC(20, 2) NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL
                        );
                        CREATE INDEX IF NOT EXISTS financial_revenue_team_round_idx
                            ON financial_revenue (team_id, round_id);

                        CREATE TABLE IF NOT EXISTS financial_expenses (
                            expense_id SERIAL PRIMARY KEY,
                            round_id INTEGER NULL,
                            team_id INTEGER NULL,
                            program_id INTEGER NULL,
                            expense_type VARCHAR(50) NULL,
                            cost_amount NUMERIC(20, 2) NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL
                        );
                        CREATE INDEX IF NOT EXISTS financial_expenses_team_round_idx
                            ON financial_expenses (team_id, round_id);
                    """,
                    reverse_sql="""
                        DROP TABLE IF EXISTS financial_expenses;
                        DROP TABLE IF EXISTS financial_revenue;
                        DROP TABLE IF EXISTS team_resources;
                        DROP TABLE IF EXISTS team_cash_flows;
                        DROP TABLE IF EXISTS team_balance_sheets;
                        DROP TABLE IF EXISTS team_income_statements;
                    """,
                ),
            ],
        ),
    ]
