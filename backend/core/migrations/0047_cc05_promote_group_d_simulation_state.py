"""CC-5 §5.5 Group D: Promote Simulation State ghosts (3 models).

Models promoted:
- SimulationState → simulation_state
- SimulationSettings → simulation_settings
- SimulationParameters → simulation_parameters

Authorized by CC-5 Amendment A1 rule #2 (live runtime reference):
- round_engine.py, r_and_d.py, persona_engine.py, views/course.py all call
  SimulationState
- budget.py, r_and_d.py, round_engine.py call SimulationParameters
- SimulationSettings has viewset-only usage but shares the subsystem — the
  three models form a cohesive settings/state triple.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0046_cc05_promote_group_c_programs'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(name='simulationstate', options={'managed': True}),
                migrations.AlterModelOptions(name='simulationsettings', options={'managed': True}),
                migrations.AlterModelOptions(name='simulationparameters', options={'managed': True}),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS simulation_state (
                            state_id SERIAL PRIMARY KEY,
                            current_round_id INTEGER NULL,
                            status VARCHAR(50) NULL,
                            last_updated TIMESTAMP WITH TIME ZONE NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS simulation_state_instance_id_idx
                            ON simulation_state (instance_id);

                        CREATE TABLE IF NOT EXISTS simulation_settings (
                            setting_id SERIAL PRIMARY KEY,
                            setting_name VARCHAR(255) NOT NULL,
                            setting_value TEXT NULL,
                            description TEXT NULL
                        );

                        CREATE TABLE IF NOT EXISTS simulation_parameters (
                            parameter_id SERIAL PRIMARY KEY,
                            parameter_name VARCHAR(255) NOT NULL,
                            parameter_value TEXT NULL,
                            description TEXT NULL,
                            updated_at TIMESTAMP WITH TIME ZONE NULL
                        );
                    """,
                    reverse_sql="""
                        DROP TABLE IF EXISTS simulation_parameters;
                        DROP TABLE IF EXISTS simulation_settings;
                        DROP TABLE IF EXISTS simulation_state;
                    """,
                ),
            ],
        ),
    ]
