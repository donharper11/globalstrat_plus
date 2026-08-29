#!/usr/bin/env python3
"""Turn the screen into a table and an escalation decision.

Escalation is not "anything that moved". Every money field moves net income by
roughly what was spent; that is arithmetic, not a balance property. What earns a
dense sweep is a response that is large relative to the baseline, changes the
leaderboard, is non-monotonic between minimum and maximum, or touches a
mechanism already known to be exploit-sensitive.
"""
import json
import pathlib
import sys
from decimal import Decimal as D

EVIDENCE = pathlib.Path(__file__).resolve().parent.parent

# A response worth a closer look, relative to the subject's own baseline.
MATERIAL_FRACTION = D('0.10')

# The performance index is a ranking scale, not a money figure: teams finish
# within a few points of each other, so a smaller relative move matters more
# than it would on a balance sheet. Deliberately tighter than the money
# threshold — but not zero. Every cost change nudges the index through the
# financial component, and the median nudge in this screen was 0.09 on a
# baseline of 56.54, which is 0.16% and is not a balance property.
MATERIAL_INDEX_FRACTION = D('0.01')
EXPLOIT_SENSITIVE = {
    ('budget', 'rd_budget'),          # the capability ratio's denominator
    ('marketing', 'retail_price'),    # price is the main revenue lever
    ('marketing', 'production_volume'),
}


def load():
    return json.loads((EVIDENCE / 'screening.json').read_text(encoding='utf-8'))


class UnreadableScreeningReport(Exception):
    """The analysis cannot read the report it was given.

    Raised rather than returning verdicts. Every previous version of this
    function answered "flat" when it could not read a row, which is the one
    answer guaranteed to be wrong: an unmeasured dimension is not a dimension
    that did not respond.
    """


def classify(report):
    """Decide which dimensions earn a dense sweep.

    Reads the counterfactual format: each result carries `delta` against the
    single cached `baseline_metrics`, so the scale a response is judged against
    is the subject team's own baseline. An earlier version of this function was
    written for the previous result shape and looked for `control` and `probe`
    keys that no longer exist — every fraction came out `None`, nothing
    escalated on measurement, and the only dimensions flagged were the three on
    the hard-coded list. It looked like a decisive result and measured nothing.
    """
    baseline = report.get('baseline_metrics') or {}
    if not baseline:
        raise UnreadableScreeningReport(
            'the report carries no baseline_metrics, so no response can be '
            'judged against anything')
    applied = [r for r in report.get('results', []) if r.get('applied')]
    without_delta = [f"{r.get('decision_type')}.{r.get('field')}"
                     for r in applied if not r.get('delta')]
    if without_delta:
        raise UnreadableScreeningReport(
            f'{len(without_delta)} applied result(s) carry no delta — the '
            f'report is in a shape this analysis does not understand: '
            f'{without_delta[:5]}')

    def scale(metric):
        value = baseline.get(metric)
        if value is None:
            return None
        magnitude = abs(D(value))
        return magnitude if magnitude > 0 else None

    by_dimension = {}
    for row in report['results']:
        if not row.get('applied'):
            continue
        by_dimension.setdefault((row['decision_type'], row['field']), []).append(row)

    table = []
    escalate = []
    for (decision_type, field), rows in sorted(by_dimension.items()):
        entry = {'decision_type': decision_type, 'field': field,
                 'kind': rows[0]['kind'], 'probes': []}
        reasons = set()
        signed_net = []
        for row in rows:
            deltas = row.get('delta') or {}
            fractions = {}
            for metric in ('net_income', 'total_revenue', 'cash_closing'):
                raw, denominator = deltas.get(metric), scale(metric)
                if raw is not None and denominator:
                    fractions[metric] = abs(D(raw)) / denominator
            index_delta = deltas.get('index_value')
            index_scale = scale('index_value')
            index_changed = (
                index_delta is not None and index_scale is not None
                and abs(D(index_delta)) / index_scale >= MATERIAL_INDEX_FRACTION)

            if any(f >= MATERIAL_FRACTION for f in fractions.values()):
                reasons.add('material response against the subject baseline')
            if index_changed:
                reasons.add('performance index moved materially')
            if row.get('resolution_error'):
                reasons.add('resolution error')
            if deltas.get('net_income') is not None:
                signed_net.append(D(deltas['net_income']))

            entry['probes'].append({
                'label': row['label'], 'value': row['value'],
                'moved': row.get('moved'),
                'net_income_delta': deltas.get('net_income'),
                'revenue_delta': deltas.get('total_revenue'),
                'index_delta': index_delta,
                'fractions': {k: str(round(v, 4)) for k, v in fractions.items()},
            })

        # A minimum and a maximum that move the same metric in the *same*
        # direction is not a monotonic response to a magnitude, and is worth a
        # closer look even when neither end is large.
        if len(signed_net) == 2 and signed_net[0] != 0 and signed_net[1] != 0:
            if (signed_net[0] > 0) == (signed_net[1] > 0):
                reasons.add('minimum and maximum move net income the same way')

        if (decision_type, field) in EXPLOIT_SENSITIVE:
            reasons.add('known exploit-sensitive mechanism')

        entry['escalate'] = bool(reasons)
        entry['escalation_reasons'] = sorted(reasons)
        entry['verdict'] = 'escalate' if reasons else 'flat in screening'
        table.append(entry)
        if reasons:
            escalate.append(entry)
    return table, escalate


def main():
    report = load()
    table, escalate = classify(report)
    summary = {
        'code_revision': report.get('code_revision'),
        'seed': report.get('seed'),
        'baseline': report.get('baseline'),
        'elapsed_seconds': report.get('elapsed_seconds'),
        'planned': report.get('planned'),
        'screened': report.get('screened'),
        'dimensions_screened': len(table),
        'dimensions_flat': len([e for e in table if not e['escalate']]),
        'dimensions_escalated': len(escalate),
        'not_screened': report.get('not_screened'),
        'material_fraction_threshold': str(MATERIAL_FRACTION),
        'material_index_fraction_threshold': str(MATERIAL_INDEX_FRACTION),
        'baseline_metrics': report.get('baseline_metrics'),
        'dimensions': table,
    }
    (EVIDENCE / 'screening-summary.json').write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding='utf-8')

    print(f"{'dimension':44} {'verdict':22} reasons")
    for entry in table:
        name = f"{entry['decision_type']}.{entry['field']}"
        print(f"  {name:42} {entry['verdict']:22} "
              f"{', '.join(entry['escalation_reasons'])}")
    print(f"\nscreened {summary['dimensions_screened']} dimensions | "
          f"flat {summary['dimensions_flat']} | "
          f"escalate {summary['dimensions_escalated']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
