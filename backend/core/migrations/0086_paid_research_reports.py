"""Market research becomes a paid mechanic.

Two things land together, because either alone is incoherent: the table that
records what a team bought and was charged, and the authored prices that say
what a purchase costs.

The prices are seeded at a uniform placeholder into every existing scenario.
They are a balance lever, not a constant (R3) -- calibration moves them later
as a data-only change, which is exactly what authoring them per scenario is
for. The figure is deliberately round and deliberately the same for every
report: it is a placeholder awaiting calibration, not a considered price, and a
uniform number makes that obvious to whoever reads it next.

Numbered 0086 rather than 0085 because `crv2-10-stage5-price-band` holds
`0085_price_band_blank_price` on a parallel branch. Both depend on 0084, so
merging the two branches produces two leaf nodes and needs a merge migration --
a visible, deliberate integration step rather than a silent filename collision.
"""
from django.db import migrations, models
import django.db.models.deletion


# Keys authored identically in all three scenario YAMLs.
RESEARCH_PRICES = {
    'research_report_price_segments': (
        '50000', 'Price of the segment report (placeholder, awaiting calibration)'),
    'research_report_price_products': (
        '50000', 'Price of the product report (placeholder, awaiting calibration)'),
    'research_report_price_markets': (
        '50000', 'Price of the market report (placeholder, awaiting calibration)'),
    'research_report_price_channels': (
        '50000', 'Price of the channel report (placeholder, awaiting calibration)'),
    'research_report_price_stakeholders': (
        '50000', 'Price of the stakeholder report (placeholder, awaiting calibration)'),
    'research_analyst_query_price': (
        '50000', 'Price of one analyst query, charged per question asked '
                 '(placeholder, awaiting calibration)'),
}


def add_prices(apps, schema_editor):
    Scenario = apps.get_model('core', 'Scenario')
    ScenarioConfig = apps.get_model('core', 'ScenarioConfig')
    for scenario in Scenario.objects.all():
        for key, (value, description) in RESEARCH_PRICES.items():
            ScenarioConfig.objects.get_or_create(
                scenario=scenario, config_key=key,
                defaults={'config_value': value, 'description': description},
            )


def remove_prices(apps, schema_editor):
    """Remove only the rows this migration would have added.

    A scenario whose price has since been calibrated to a different value keeps
    it: reversing the migration must not silently discard an authored decision.
    """
    ScenarioConfig = apps.get_model('core', 'ScenarioConfig')
    for key, (value, _description) in RESEARCH_PRICES.items():
        ScenarioConfig.objects.filter(
            config_key=key, config_value=value).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0084_product_level_demand'),
    ]

    operations = [
        migrations.CreateModel(
            name='DecisionResearchPurchase',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('report_type', models.CharField(choices=[
                    ('segments', 'Segment report'),
                    ('products', 'Product report'),
                    ('markets', 'Market report'),
                    ('channels', 'Channel report'),
                    ('stakeholders', 'Stakeholder report'),
                    ('analyst_query', 'Analyst query'),
                ], max_length=32)),
                ('scope_key', models.CharField(
                    blank=True, default='',
                    help_text="Market code, '' for a whole-game report, or the "
                              'query ordinal for an analyst query.',
                    max_length=40)),
                ('price', models.DecimalField(
                    decimal_places=2,
                    help_text='The authored price charged, frozen at purchase.',
                    max_digits=15)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('market', models.ForeignKey(
                    blank=True,
                    help_text='Set only for a market-scoped report.',
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='research_purchases',
                    to='core.marketdefinition')),
                ('submission', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='research_purchases',
                    to='core.decisionsubmission')),
            ],
            options={
                'db_table': 'decision_research_purchase',
                'ordering': ['id'],
                'unique_together': {('submission', 'report_type', 'scope_key')},
            },
        ),
        migrations.RunPython(add_prices, remove_prices),
    ]
