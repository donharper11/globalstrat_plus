"""Give every existing scenario a high-price demand elasticity (V2-023 rework).

The reference-price repair alone left the exploit intact above the clamp
point. Price competitiveness is a bounded preference feature: it reaches its
floor at 1.5x the reference and stays there, so beyond roughly $630 on a $420
reference, raising price stopped reducing demand while revenue kept
multiplying by price. Adoption now also carries an absolute elasticity:

    high_price_multiplier = (retail_price / reference_price) ** -elasticity

applied when the price is above the reference.

1.5 is strictly greater than 1, as the rules disposition requires -- at
exactly 1 revenue would be flat above the reference rather than falling, and
below 1 it would still grow. At 1.5 the pure elasticity term leaves revenue
falling as p^-0.5, a decline rather than a collapse.

Scenario YAML carries the value for fresh loads; scenarios already in a
database need it written to them, or the next round will fail closed before
any competitive write.

Reversible: the reverse removes only rows this migration would have added.
"""
from django.db import migrations

CONFIG_KEY = 'high_price_elasticity'
DEFAULT_ELASTICITY = '1.5'
DESCRIPTION = ('Demand elasticity applied above the reference price; must be '
               '> 1 so revenue cannot grow without bound (V2-023)')


def add_elasticity(apps, schema_editor):
    Scenario = apps.get_model('core', 'Scenario')
    ScenarioConfig = apps.get_model('core', 'ScenarioConfig')
    for scenario in Scenario.objects.all():
        ScenarioConfig.objects.get_or_create(
            scenario=scenario, config_key=CONFIG_KEY,
            defaults={'config_value': DEFAULT_ELASTICITY,
                      'description': DESCRIPTION},
        )


def remove_elasticity(apps, schema_editor):
    ScenarioConfig = apps.get_model('core', 'ScenarioConfig')
    ScenarioConfig.objects.filter(
        config_key=CONFIG_KEY, config_value=DEFAULT_ELASTICITY).delete()


class Migration(migrations.Migration):

    dependencies = [('core', '0074_reference_price')]

    operations = [migrations.RunPython(add_elasticity, remove_elasticity)]
