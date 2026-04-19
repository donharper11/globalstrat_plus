"""CC-5 §5.5: Promote NewSalesByRound with corrected PK schema.

Resolution of the schema halt flagged in promotion_questions.md (Option R1):
The prior declaration set ``round_id`` as ``primary_key=True`` alongside a
``unique_together = (('round_id', 'customer_id', 'program_id'),)`` — these
are mutually inconsistent (the single-column PK restricts to one row per
round, while the composite unique implies many rows per round keyed by
customer and program).

Fix: replace the round_id PK with a new ``sales_id AutoField`` surrogate
PK, keep ``round_id`` as a plain ``IntegerField NOT NULL``, and keep the
composite ``unique_together`` constraint — the same pattern used by
``financial_revenue`` and other per-round-per-entity tables.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0049_cc05_promote_group_f_instructor'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterUniqueTogether(
                    name='newsalesbyround',
                    unique_together=set(),
                ),
                migrations.RemoveField(
                    model_name='newsalesbyround',
                    name='round_id',
                ),
                migrations.AddField(
                    model_name='newsalesbyround',
                    name='sales_id',
                    field=models.AutoField(primary_key=True, serialize=False),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name='newsalesbyround',
                    name='round_id',
                    field=models.IntegerField(default=0),
                    preserve_default=False,
                ),
                migrations.AlterUniqueTogether(
                    name='newsalesbyround',
                    unique_together={('round_id', 'customer_id', 'program_id')},
                ),
                migrations.AlterModelOptions(
                    name='newsalesbyround',
                    options={'managed': True},
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS new_sales_by_round (
                            sales_id SERIAL PRIMARY KEY,
                            round_id INTEGER NOT NULL,
                            customer_id INTEGER NOT NULL,
                            program_id INTEGER NOT NULL,
                            new_sales INTEGER NULL,
                            instance_id INTEGER NULL,
                            CONSTRAINT new_sales_by_round_round_customer_program_uniq
                                UNIQUE (round_id, customer_id, program_id)
                        );
                        CREATE INDEX IF NOT EXISTS new_sales_by_round_round_id_idx
                            ON new_sales_by_round (round_id);
                    """,
                    reverse_sql="DROP TABLE IF EXISTS new_sales_by_round;",
                ),
            ],
        ),
    ]
