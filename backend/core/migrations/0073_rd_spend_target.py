"""Give every existing scenario an R&D spend target (V2-021).

Strategic capability now scores `rd_spend / rd_spend_target` instead of
`rd_spend / team_declared_rd_budget`, and scoring refuses to run without a
positive target. Scenario YAML carries the value for fresh loads; scenarios
already in a database need it written to them, or the next round will fail
closed.

$2,000,000 is the value the competition scenario is initialised at — the same
figure `load_demo` scripts as a competent R&D budget, so a team playing the
documented baseline scores 1.0 exactly as it did before the change.

Reversible: the reverse removes only rows this migration would have added.
"""
from django.db import migrations

CONFIG_KEY = 'rd_spend_target'
DEFAULT_TARGET = '2000000'
DESCRIPTION = 'R&D spend that earns full strategic-capability credit (V2-021)'


def add_target(apps, schema_editor):
    Scenario = apps.get_model('core', 'Scenario')
    ScenarioConfig = apps.get_model('core', 'ScenarioConfig')
    for scenario in Scenario.objects.all():
        ScenarioConfig.objects.get_or_create(
            scenario=scenario, config_key=CONFIG_KEY,
            defaults={'config_value': DEFAULT_TARGET,
                      'description': DESCRIPTION},
        )


def remove_target(apps, schema_editor):
    ScenarioConfig = apps.get_model('core', 'ScenarioConfig')
    ScenarioConfig.objects.filter(
        config_key=CONFIG_KEY, config_value=DEFAULT_TARGET).delete()


class Migration(migrations.Migration):

    dependencies = [('core', '0072_truncate_guard_authorization')]

    operations = [migrations.RunPython(add_target, remove_target)]
