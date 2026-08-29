"""Author a reference price per positioning tier (V2-023 revision).

The first form of the V2-023 repair scored every retail price against a single
scenario reference of $420. That made the positioning tiers incoherent: a
premium product at its own authored starting price of $700 was 1.667x the
reference, so price competitiveness clamped to zero and the high-price
elasticity removed 53% of its demand. Ultra-premium at $1,000 lost 73%. The
tiers were penalised for being the tiers the scenario author created, and the
only way to score well was to abandon them.

Each positioning now carries its own authored reference, seeded with the
starting prices the demo already used: budget $250, mainstream $420, premium
$700, ultra-premium $1,000. A product priced at its own tier's reference scores
exactly average competitiveness and carries no demand penalty, and equal
relative deviations are treated equally across tiers.

The single `reference_price` key is removed: leaving an unused key that once
decided scoring invites a future reader to trust it.

Reversible: the reverse restores the single key and removes the four.
"""
from django.db import migrations

LEGACY_KEY = 'reference_price'
LEGACY_VALUE = '420'
BY_POSITIONING = {
    'reference_price_budget': ('250', 'Budget reference price (V2-023)'),
    'reference_price_mainstream': ('420', 'Mainstream reference price (V2-023)'),
    'reference_price_premium': ('700', 'Premium reference price (V2-023)'),
    'reference_price_ultra_premium': ('1000', 'Ultra-premium reference price (V2-023)'),
}


def add_tiers(apps, schema_editor):
    Scenario = apps.get_model('core', 'Scenario')
    ScenarioConfig = apps.get_model('core', 'ScenarioConfig')
    for scenario in Scenario.objects.all():
        for key, (value, description) in BY_POSITIONING.items():
            ScenarioConfig.objects.get_or_create(
                scenario=scenario, config_key=key,
                defaults={'config_value': value, 'description': description},
            )
    ScenarioConfig.objects.filter(config_key=LEGACY_KEY).delete()


def restore_single(apps, schema_editor):
    Scenario = apps.get_model('core', 'Scenario')
    ScenarioConfig = apps.get_model('core', 'ScenarioConfig')
    for scenario in Scenario.objects.all():
        ScenarioConfig.objects.get_or_create(
            scenario=scenario, config_key=LEGACY_KEY,
            defaults={'config_value': LEGACY_VALUE,
                      'description': 'Retail price reference (V2-023)'},
        )
    ScenarioConfig.objects.filter(config_key__in=BY_POSITIONING).delete()


class Migration(migrations.Migration):

    dependencies = [('core', '0076_optimal_headcounts')]

    operations = [migrations.RunPython(add_tiers, restore_single)]
