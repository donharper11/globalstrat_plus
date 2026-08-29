"""Give every existing scenario a retail price reference (V2-023).

Price competitiveness now scores `team_retail_price / reference_price` instead
of `team_price / average_of_positioning_group_including_self`, and scoring
refuses to run without a positive reference. Scenario YAML carries the value
for fresh loads; scenarios already in a database need it written to them, or
the next round will fail closed before any competitive write.

$420 is the established baseline price of the competition scenario -- the price
at which the old relative formula and the new absolute one agree, so a team
playing the documented baseline scores as it did before the change.

Reversible: the reverse removes only rows this migration would have added.
"""
from django.db import migrations

CONFIG_KEY = 'reference_price'
DEFAULT_PRICE = '420'
DESCRIPTION = 'Retail price that scores as exactly average competitiveness (V2-023)'


def add_reference(apps, schema_editor):
    Scenario = apps.get_model('core', 'Scenario')
    ScenarioConfig = apps.get_model('core', 'ScenarioConfig')
    for scenario in Scenario.objects.all():
        ScenarioConfig.objects.get_or_create(
            scenario=scenario, config_key=CONFIG_KEY,
            defaults={'config_value': DEFAULT_PRICE,
                      'description': DESCRIPTION},
        )


def remove_reference(apps, schema_editor):
    ScenarioConfig = apps.get_model('core', 'ScenarioConfig')
    ScenarioConfig.objects.filter(
        config_key=CONFIG_KEY, config_value=DEFAULT_PRICE).delete()


class Migration(migrations.Migration):

    dependencies = [('core', '0073_rd_spend_target')]

    operations = [migrations.RunPython(add_reference, remove_reference)]
