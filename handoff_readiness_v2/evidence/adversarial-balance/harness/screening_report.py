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

# A response worth a closer look, relative to the control's own scale.
MATERIAL_FRACTION = D('0.10')
EXPLOIT_SENSITIVE = {
    ('budget', 'rd_budget'),          # the capability ratio's denominator
    ('marketing', 'retail_price'),    # price is the main revenue lever
    ('marketing', 'production_volume'),
}


def load():
    return json.loads((EVIDENCE / 'screening.json').read_text(encoding='utf-8'))


def classify(report):
    by_dimension = {}
    for row in report['results']:
        if not row.get('applied'):
            continue
        key = (row['decision_type'], row['field'])
        by_dimension.setdefault(key, []).append(row)

    table = []
    escalate = []
    for (decision_type, field), rows in sorted(by_dimension.items()):
        entry = {'decision_type': decision_type, 'field': field,
                 'kind': rows[0]['kind'], 'probes': []}
        material = False
        indices = []
        for row in rows:
            delta = row.get('delta') or {}
            control = row.get('control') or {}
            fraction = None
            if delta.get('net_income') and control.get('net_income'):
                base = abs(D(control['net_income'])) or D('1')
                fraction = abs(D(delta['net_income'])) / base
            index_moved = (
                row.get('probe') and row.get('control')
                and row['probe'].get('index_value') != row['control'].get('index_value'))
            if index_moved:
                indices.append(row['probe']['index_value'])
            entry['probes'].append({
                'label': row['label'], 'value': row['value'],
                'moved': row.get('moved'),
                'net_income_delta': delta.get('net_income'),
                'revenue_delta': delta.get('total_revenue'),
                'index_changed': bool(index_moved),
                'fraction_of_control_net_income': (
                    str(round(fraction, 4)) if fraction is not None else None),
                'resolution_error': row.get('resolution_error'),
            })
            if fraction is not None and fraction >= MATERIAL_FRACTION:
                material = True
            if index_moved:
                material = True
            if row.get('resolution_error'):
                material = True
        reasons = []
        if material:
            reasons.append('material response or leaderboard movement')
        if (decision_type, field) in EXPLOIT_SENSITIVE:
            reasons.append('known exploit-sensitive mechanism')
        entry['escalate'] = bool(reasons)
        entry['escalation_reasons'] = reasons
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
