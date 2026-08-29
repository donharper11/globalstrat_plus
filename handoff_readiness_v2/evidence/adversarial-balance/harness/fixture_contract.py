"""Every decision family the scenario claims must be reachable and legal.

The value-conservation probe reported trade finance and sourcing as
"unexercisable in this scenario" and I wrote that up as a shipped-scenario gap.
It was neither. `setup_test_game` takes the *first available* scenario when
none is named, which is `clean_energy_tech_2026`; that scenario declares no
suppliers and no trade-finance instruments, while `consumer_electronics_2026`
declares twelve suppliers and a full instrument catalogue and the loader
creates both. The probe had selected a fixture that could not express the
mechanisms it was sent to test, and called the result a property of the
product.

This contract makes that failure impossible to repeat quietly: it asserts, for
the scenario a probe is actually using, that each decision family it claims has
at least one legal value to choose. A family with nothing to choose is a
fixture that cannot test it, and the probe must say so before it measures
rather than after.
"""

FAMILIES = {
    'sourcing': {
        'model': 'core.Supplier',
        'why': 'SourcingAllocation.supplier is a required FK; with no Supplier '
               'rows no allocation can be written at all.',
    },
    'logistics': {
        'model': 'core.ShippingLane',
        'why': 'Logistics decisions name a lane.',
    },
    'trade_finance': {
        'model': 'core.TradeFinanceInstrument',
        'why': 'buyer_payment_instrument is validated against this catalogue, '
               'so an empty catalogue leaves the field with no legal value.',
    },
    'compliance': {
        'model': 'core.ComplianceRegime',
        'why': 'Compliance enforcement needs at least one regime.',
    },
}


def check(scenario):
    """Return {family: {'rows': n, 'reachable': bool, 'why': str}}."""
    from django.apps import apps
    result = {}
    for family, spec in FAMILIES.items():
        model = apps.get_model(spec['model'])
        rows = model.objects.filter(scenario=scenario).count()
        result[family] = {'model': spec['model'], 'rows': rows,
                          'reachable': rows > 0, 'why': spec['why']}
    return result


def scenario_supporting(families):
    """The loaded scenario that can express every named family, or None.

    Prefers a scenario that satisfies all of them so one fixture exercises the
    whole set, rather than silently testing a subset.
    """
    from core.models import Scenario
    best = None
    for scenario in Scenario.objects.all().order_by('id'):
        status = check(scenario)
        if all(status[f]['reachable'] for f in families):
            return scenario, status
        if best is None:
            best = (scenario, status)
    return (None, best[1] if best else {})
