"""CC-5 §5.5 Group C: Promote Programs & Portfolio ghosts (5 models).

Models promoted:
- ProgramType → program_types
- Program → programs
- ProgramPortfolio → program_portfolio
- ProgramFeature → program_features
- Decision → decisions

All FKs are plain IntegerField (except Program.team_id which is
DECIMAL(10,0) by explicit design per model comment: "numeric in PG — no FK
to teams"). No Django ForeignKey constraints. CREATE TABLE mirrors
declarations exactly.

Authorized by CC-5 Amendment A1 rule #2 (live runtime reference):
round_engine.py, budget.py, r_and_d.py, persona_engine.py,
gamification_engine.py, strategic_tools.py all call these models.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_cc05_promote_group_b_financials'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(name='programtype', options={'managed': True}),
                migrations.AlterModelOptions(name='program', options={'managed': True}),
                migrations.AlterModelOptions(name='programportfolio', options={'managed': True}),
                migrations.AlterModelOptions(name='programfeature', options={'managed': True}),
                migrations.AlterModelOptions(name='decision', options={'managed': True}),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS program_types (
                            program_type_id SERIAL PRIMARY KEY,
                            program_type_name VARCHAR(255) NOT NULL,
                            description TEXT NULL,
                            base_cost NUMERIC(20, 2) NULL,
                            unit_price NUMERIC(20, 2) NULL,
                            cogs_per_unit NUMERIC(20, 2) NULL,
                            economy_id INTEGER NULL
                        );

                        CREATE TABLE IF NOT EXISTS programs (
                            program_id SERIAL PRIMARY KEY,
                            program_name VARCHAR(255) NOT NULL,
                            program_type_id INTEGER NOT NULL,
                            round_launched INTEGER NOT NULL,
                            status VARCHAR(50) NOT NULL,
                            description TEXT NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL,
                            modified_at TIMESTAMP WITH TIME ZONE NULL,
                            team_id NUMERIC(10, 0) NULL,
                            instance_id INTEGER NULL,
                            development_status VARCHAR(20) NOT NULL DEFAULT 'ready',
                            development_rounds_total INTEGER NOT NULL DEFAULT 0,
                            development_rounds_remaining INTEGER NOT NULL DEFAULT 0,
                            r_and_d_investment NUMERIC(12, 2) NOT NULL DEFAULT 0,
                            development_started_round INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS programs_team_id_idx ON programs (team_id);
                        CREATE INDEX IF NOT EXISTS programs_program_type_id_idx ON programs (program_type_id);

                        CREATE TABLE IF NOT EXISTS program_portfolio (
                            program_portfolio_id SERIAL PRIMARY KEY,
                            program_portfolio_name VARCHAR(100) NOT NULL,
                            program_portfolio_notes TEXT NOT NULL,
                            program_id INTEGER NOT NULL,
                            round_launched INTEGER NULL,
                            round_modified INTEGER NULL,
                            modified_status VARCHAR(50) NULL,
                            status VARCHAR(50) NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL
                        );
                        CREATE INDEX IF NOT EXISTS program_portfolio_program_id_idx
                            ON program_portfolio (program_id);

                        CREATE TABLE IF NOT EXISTS program_features (
                            program_feature_id SERIAL PRIMARY KEY,
                            feature_id INTEGER NOT NULL,
                            program_id INTEGER NOT NULL,
                            feature_value NUMERIC(10, 4) NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL,
                            program_portfolio_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS program_features_program_id_idx
                            ON program_features (program_id);

                        CREATE TABLE IF NOT EXISTS decisions (
                            decision_id SERIAL PRIMARY KEY,
                            team_id INTEGER NULL,
                            round_id INTEGER NULL,
                            feature_id INTEGER NULL,
                            feature_value NUMERIC(10, 2) NULL,
                            budget_allocation NUMERIC(10, 2) NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS decisions_team_round_idx
                            ON decisions (team_id, round_id);
                    """,
                    reverse_sql="""
                        DROP TABLE IF EXISTS decisions;
                        DROP TABLE IF EXISTS program_features;
                        DROP TABLE IF EXISTS program_portfolio;
                        DROP TABLE IF EXISTS programs;
                        DROP TABLE IF EXISTS program_types;
                    """,
                ),
            ],
        ),
    ]
