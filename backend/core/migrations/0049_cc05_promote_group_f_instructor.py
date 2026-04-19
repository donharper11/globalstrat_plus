"""CC-5 §5.5 Group F: Promote Instructor Tools ghosts (5 models).

Models promoted:
- InstructorAction → instructor_actions
- InstructorEvaluation → instructor_evaluations
- InstructorNote → instructor_notes
- InstructorFeedbackTemplate → instructor_feedback_templates
- InstructorScenarioCustomization → instructor_scenario_customization

Authorized by CC-5 Amendment A1 rule #2 (live runtime reference via
viewsets): all five have instructor viewset bindings in
core/views/instructor.py. CC-16 will extend InstructorScenarioCustomization
(flagged EXTEND in instructor_panel_audit.md) — the underlying table must
exist for that work to proceed.

This closes the Group 1–F promotion sequence (NewSalesByRound in Group B
remains halted pending schema clarification — see promotion_questions.md).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0048_cc05_promote_group_e_messaging_events'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(name='instructoraction', options={'managed': True}),
                migrations.AlterModelOptions(name='instructorevaluation', options={'managed': True}),
                migrations.AlterModelOptions(name='instructornote', options={'managed': True}),
                migrations.AlterModelOptions(name='instructorfeedbacktemplate', options={'managed': True}),
                migrations.AlterModelOptions(name='instructorscenariocustomization', options={'managed': True}),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS instructor_actions (
                            action_id SERIAL PRIMARY KEY,
                            user_id INTEGER NULL,
                            action_type VARCHAR(255) NULL,
                            action_details TEXT NULL,
                            team_id INTEGER NULL,
                            round_id INTEGER NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL
                        );
                        CREATE INDEX IF NOT EXISTS instructor_actions_user_id_idx
                            ON instructor_actions (user_id);

                        CREATE TABLE IF NOT EXISTS instructor_evaluations (
                            evaluation_id SERIAL PRIMARY KEY,
                            instructor_id INTEGER NULL,
                            team_id INTEGER NULL,
                            round_id INTEGER NULL,
                            evaluation_score NUMERIC(5, 2) NULL,
                            comments TEXT NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS instructor_evaluations_team_round_idx
                            ON instructor_evaluations (team_id, round_id);

                        CREATE TABLE IF NOT EXISTS instructor_notes (
                            note_id SERIAL PRIMARY KEY,
                            user_id INTEGER NULL,
                            team_id INTEGER NULL,
                            round_id INTEGER NULL,
                            note_text TEXT NOT NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL,
                            instance_id INTEGER NULL
                        );
                        CREATE INDEX IF NOT EXISTS instructor_notes_team_round_idx
                            ON instructor_notes (team_id, round_id);

                        CREATE TABLE IF NOT EXISTS instructor_feedback_templates (
                            template_id SERIAL PRIMARY KEY,
                            template_name VARCHAR(255) NOT NULL,
                            feedback_text TEXT NOT NULL,
                            created_by INTEGER NULL,
                            created_at TIMESTAMP WITH TIME ZONE NULL
                        );

                        CREATE TABLE IF NOT EXISTS instructor_scenario_customization (
                            customization_id SERIAL PRIMARY KEY,
                            instructor_id INTEGER NULL,
                            config_id INTEGER NULL,
                            modified_event TEXT NULL,
                            modified_challenge TEXT NULL
                        );
                        CREATE INDEX IF NOT EXISTS instructor_scenario_customization_instructor_idx
                            ON instructor_scenario_customization (instructor_id);
                    """,
                    reverse_sql="""
                        DROP TABLE IF EXISTS instructor_scenario_customization;
                        DROP TABLE IF EXISTS instructor_feedback_templates;
                        DROP TABLE IF EXISTS instructor_notes;
                        DROP TABLE IF EXISTS instructor_evaluations;
                        DROP TABLE IF EXISTS instructor_actions;
                    """,
                ),
            ],
        ),
    ]
