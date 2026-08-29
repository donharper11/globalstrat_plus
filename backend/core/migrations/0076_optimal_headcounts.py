"""Author the staffing levels capability is scored against (V2-025).

Strategic capability is now multiplied by staffing adequacy: the mean of
`clamp01(headcount / optimal)` across the R&D, commercial and operations
pools. Before this, emptying all three pools saved $1,200,000 of payroll and
moved capability by exactly 0.0000, so stripping the firm was free index and
won 9 of 9 holdout cells independently of opponents.

`talent.py` has always read these three keys, but with hardcoded 60/40/50
fallbacks and no scenario ever authoring them. A silent default is tolerable
for a display score and not for a competition denominator, so the values are
written here and both consumers now fail closed without them.

60, 40 and 50 are exactly the fallbacks talent.py used, so the talent scores
this migration touches are unchanged by it.

Reversible: the reverse removes only rows this migration would have added.
"""
from django.db import migrations

DEFAULTS = {
    'optimal_rd_headcount': ('60', 'R&D headcount that scores full staffing adequacy (V2-025)'),
    'optimal_commercial_headcount': ('40', 'Commercial headcount that scores full staffing adequacy (V2-025)'),
    'optimal_operations_headcount': ('50', 'Operations headcount that scores full staffing adequacy (V2-025)'),
}


def add_optima(apps, schema_editor):
    Scenario = apps.get_model('core', 'Scenario')
    ScenarioConfig = apps.get_model('core', 'ScenarioConfig')
    for scenario in Scenario.objects.all():
        for key, (value, description) in DEFAULTS.items():
            ScenarioConfig.objects.get_or_create(
                scenario=scenario, config_key=key,
                defaults={'config_value': value, 'description': description},
            )


def remove_optima(apps, schema_editor):
    ScenarioConfig = apps.get_model('core', 'ScenarioConfig')
    for key, (value, _) in DEFAULTS.items():
        ScenarioConfig.objects.filter(
            config_key=key, config_value=value).delete()


class Migration(migrations.Migration):

    dependencies = [('core', '0075_high_price_elasticity')]

    operations = [migrations.RunPython(add_optima, remove_optima)]
