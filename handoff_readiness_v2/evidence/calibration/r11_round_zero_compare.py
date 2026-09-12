#!/usr/bin/env python3
"""Compare two R11 round-zero probe runs (pre-change engine vs R11).

    r11_round_zero_compare.py <label-a> <label-b> [runs-root]

Outputs ``comparison_<a>_vs_<b>.json`` in the runs root.  Two independent
views:

1. result tables (``results.json``): every row of every per-round result table,
   keyed by readable natural key, split into round 0 and rounds >= 1;
2. the competitive output manifest body for every round (what ``output_sha256``
   hashes): every section, every row, split by the row's own round_number when
   it has one, plus a recomputed hash that excludes only round 0 rows.

**Read the name-normalised figures, not the raw hashes**, unless both runs were
produced with ``--name-seed``.  ``initialize_game`` draws company names with an
unseeded shuffle, so two unpinned runs name the same starter-profile slot
differently and the raw manifest bodies cannot hash equal however the engine
behaves.  Teams are aligned here by creation order — the same starter profile
in both runs — and names never enter scoring.
"""
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / 'backend'))
from core.services.canonical_json import canonical_sha256  # noqa: E402

A_LABEL, B_LABEL = (sys.argv[1:3] if len(sys.argv) >= 3
                    else ('baseline_pre_r11', 'variant_r11'))
RUNS = pathlib.Path(sys.argv[3]) if len(sys.argv) >= 4 else (HERE / 'r11_runs')
A = RUNS / A_LABEL
B = RUNS / B_LABEL

KEYS = {
    'adoption': ('round_number', 'team__name', 'segment__name', 'market__code'),
    'product_demand': ('round_number', 'team__name', 'team_product__name', 'segment__name', 'market__code'),
    'ai_adoption': ('round_number', 'ai_competitor__name', 'segment__name', 'market__code'),
    'reconciliation': ('round_number', 'segment__name', 'market__code'),
    'financials': ('round_number', 'team__name'),
    'performance_index': ('round_number', 'team__name'),
    'leaderboard': ('round_number', 'team__name'),
    'product_market': ('round_number', 'team__name', 'team_product__name', 'market__code'),
    'market_revenue': ('round_number', 'team__name', 'market__code'),
    'coherence': ('round_number', 'team__name'),
}
IGNORE = {'game_id', 'team_id', 'segment_id', 'market_id', 'team_product_id',
          'best_product_id', 'ai_competitor_id'}


NAMES = {}  # run dir -> team names in creation (pk) order


def _team_names(run_dir):
    if run_dir not in NAMES:
        teams = json.loads((run_dir / 'results.json').read_text())['teams']
        NAMES[run_dir] = [t['name'] for t in teams]
        assert all(a not in b for a in NAMES[run_dir] for b in NAMES[run_dir] if a != b)
    return NAMES[run_dir]


def load(path):
    """Load a run file with team names replaced by creation-index placeholders."""
    text = path.read_text()
    if path.name != 'run_meta.json':
        for index, name in enumerate(_team_names(path.parent)):
            text = text.replace(name, f'TEAM{index:02d}')
    return json.loads(text)


def table_diff(name, rows_a, rows_b):
    key = KEYS[name]
    ia = {tuple(r.get(k) for k in key): r for r in rows_a}
    ib = {tuple(r.get(k) for k in key): r for r in rows_b}
    out = {'rows_a': len(ia), 'rows_b': len(ib), 'r0': [], 'r_ge1': [],
           'only_in_one': sorted(str(k) for k in set(ia) ^ set(ib))}
    for k in sorted(set(ia) & set(ib), key=str):
        ra, rb = ia[k], ib[k]
        fields = [f for f in sorted(set(ra) | set(rb)) if f not in IGNORE and ra.get(f) != rb.get(f)]
        if fields:
            entry = {'key': list(k), 'diff': {f: [ra.get(f), rb.get(f)] for f in fields}}
            (out['r0'] if k[0] == 0 else out['r_ge1']).append(entry)
    out['r0_rows_differing'] = len(out['r0'])
    out['r_ge1_rows_differing'] = len(out['r_ge1'])
    out['r0_fields_differing'] = sorted({f for e in out['r0'] for f in e['diff']})
    out['r_ge1_fields_differing'] = sorted({f for e in out['r_ge1'] for f in e['diff']})
    out['r0'] = out['r0'][:12]
    out['r_ge1'] = out['r_ge1'][:12]
    return out


def row_round(row):
    """Round a manifest row belongs to: its round_number, else its round token."""
    if row.get('round_number') is not None:
        return int(row['round_number'])
    token = row.get('round_id')
    if isinstance(token, str) and token.startswith('round(') and token.endswith('")'):
        return int(token.rsplit('|"', 1)[1][:-2])
    return None


def _content(row):
    return json.dumps({k: v for k, v in row.items() if k != '_key'}, sort_keys=True)


def manifest_diff(round_number):
    fa, fb = A / f'manifest_r{round_number:02d}.json', B / f'manifest_r{round_number:02d}.json'
    if not fa.exists() or not fb.exists():
        return {'missing': True}
    raw_a, raw_b = json.loads(fa.read_text()), json.loads(fb.read_text())
    res = {'output_sha256_a': canonical_sha256(raw_a), 'output_sha256_b': canonical_sha256(raw_b)}
    res['output_sha256_equal'] = res['output_sha256_a'] == res['output_sha256_b']
    ma, mb = load(fa), load(fb)  # team names -> creation-index placeholders
    sections = {}
    for name in sorted(set(ma['sections']) | set(mb['sections'])):
        rows_a, rows_b = ma['sections'].get(name, []), mb['sections'].get(name, [])
        content_keyed = any('#' in r['_key'].split('(', 1)[0] for r in rows_a + rows_b)
        if content_keyed:
            ca = sorted(_content(r) for r in rows_a)
            cb = sorted(_content(r) for r in rows_b)
            if ca != cb:
                from collections import Counter
                only_a = list((Counter(ca) - Counter(cb)).elements())
                only_b = list((Counter(cb) - Counter(ca)).elements())
                sections[name] = {'content_keyed': True,
                                  'rows_only_in_a': len(only_a), 'rows_only_in_b': len(only_b),
                                  'rounds_of_differing_rows': sorted({str(row_round(json.loads(x)))
                                                                      for x in only_a + only_b}),
                                  'sample_a': only_a[:3], 'sample_b': only_b[:3]}
            continue
        ra = {r['_key']: r for r in rows_a}
        rb = {r['_key']: r for r in rows_b}
        diffs = {'round0': [], 'round_ge1': [], 'no_round': []}
        for k in sorted(set(ra) | set(rb)):
            a, b = ra.get(k), rb.get(k)
            if a == b:
                continue
            rnd = row_round(a or b)
            fields = sorted(f for f in set(a or {}) | set(b or {})
                            if (a or {}).get(f) != (b or {}).get(f))
            entry = {'key': k, 'fields': {f: [(a or {}).get(f), (b or {}).get(f)] for f in fields}}
            diffs['round0' if rnd == 0 else 'no_round' if rnd is None else 'round_ge1'].append(entry)
        if any(diffs.values()):
            sections[name] = {
                'rows_differing_round0': len(diffs['round0']),
                'rows_differing_round_ge1': len(diffs['round_ge1']),
                'rows_differing_no_round_field': len(diffs['no_round']),
                'fields_differing_round0': sorted({f for e in diffs['round0'] for f in e['fields']}),
                'sample_round0': diffs['round0'][:3],
                'sample_round_ge1': diffs['round_ge1'][:5],
                'sample_no_round_field': diffs['no_round'][:5],
            }
    res['differing_sections'] = sections

    def without_round0(body):
        kept = {name: [r for r in rows if row_round(r) != 0]
                for name, rows in body['sections'].items()}
        return dict(body, sections=kept,
                    section_digests={n: {'sha256': canonical_sha256(r), 'rows': len(r)}
                                     for n, r in sorted(kept.items())})
    res['exact_hash_excluding_round0_rows_a'] = canonical_sha256(without_round0(raw_a))
    res['exact_hash_excluding_round0_rows_b'] = canonical_sha256(without_round0(raw_b))
    res['hash_excluding_round0_rows_equal'] = (res['exact_hash_excluding_round0_rows_a'] ==
                                               res['exact_hash_excluding_round0_rows_b'])
    res['name_normalised_rows_ge1_or_unrounded_differing'] = sum(
        s.get('rows_differing_round_ge1', 0) + s.get('rows_differing_no_round_field', 0)
        + (s.get('rows_only_in_a', 0) + s.get('rows_only_in_b', 0)
           if s.get('content_keyed') and s['rounds_of_differing_rows'] != ['0'] else 0)
        for s in sections.values())
    return res


def main():
    ra, rb = load(A / 'results.json'), load(B / 'results.json')
    report = {
        'runs': {A_LABEL: load(A / 'run_meta.json'), B_LABEL: load(B / 'run_meta.json')},
        'factor_lines': {A_LABEL: ra['factor_line'], B_LABEL: rb['factor_line']},
        'teams_equal': ra['teams'] == rb['teams'],
        'tables': {name: table_diff(name, ra['tables'][name], rb['tables'][name])
                   for name in KEYS},
        'manifests': {},
    }
    rounds = sorted(int(p.stem.split('_r')[1]) for p in A.glob('manifest_r*.json'))
    for rnd in rounds:
        report['manifests'][rnd] = manifest_diff(rnd)
    fin_a = {(r['round_number'], r['team__name']): r for r in ra['tables']['financials']}
    fin_b = {(r['round_number'], r['team__name']): r for r in rb['tables']['financials']}
    pi_a = {(r['round_number'], r['team__name']): r for r in ra['tables']['performance_index']}
    pi_b = {(r['round_number'], r['team__name']): r for r in rb['tables']['performance_index']}
    lb_a = {(r['round_number'], r['team__name']): r for r in ra['tables']['leaderboard']}
    lb_b = {(r['round_number'], r['team__name']): r for r in rb['tables']['leaderboard']}
    units = {}
    for label, run in ((A_LABEL, ra), (B_LABEL, rb)):
        for r in run['tables']['product_market']:
            key = (label, r['round_number'], r['team__name'])
            units[key] = units.get(key, 0.0) + float(r['units_sold'])
    summary = []
    for key in sorted(fin_a):
        rnd, team = key
        summary.append({
            'round': rnd, 'team': team,
            'units_sold': [units.get((A_LABEL, rnd, team)), units.get((B_LABEL, rnd, team))],
            'revenue': [fin_a[key]['total_revenue'], fin_b[key]['total_revenue']],
            'net_income': [fin_a[key]['net_income'], fin_b[key]['net_income']],
            'cash_closing': [fin_a[key]['cash_closing'], fin_b[key]['cash_closing']],
            'performance_index': [pi_a[key]['index_value'], pi_b[key]['index_value']],
            'rank': [lb_a[key]['rank'], lb_b[key]['rank']],
        })
    report['per_round_team_summary'] = summary
    report['per_round_team_summary_identical_rounds_ge1'] = all(
        len({json.dumps(v) for v in (row[f][0], row[f][1])}) == 1
        for row in summary if row['round'] >= 1
        for f in ('units_sold', 'revenue', 'net_income', 'cash_closing', 'performance_index', 'rank'))
    report['verdict'] = {
        'tables_rows_ge1_differing': {n: t['r_ge1_rows_differing'] for n, t in report['tables'].items()},
        'tables_rows_round0_differing': {n: t['r0_rows_differing'] for n, t in report['tables'].items()},
        'manifest_output_sha256_equal_by_round': {r: m.get('output_sha256_equal') for r, m in report['manifests'].items()},
        'manifest_hash_excluding_round0_rows_equal_by_round': {r: m.get('hash_excluding_round0_rows_equal') for r, m in report['manifests'].items()},
        'manifest_name_normalised_rows_ge1_or_unrounded_differing_by_round': {
            r: m.get('name_normalised_rows_ge1_or_unrounded_differing')
            for r, m in report['manifests'].items()},
        'manifest_differing_sections_by_round': {
            r: sorted(m.get('differing_sections', {})) for r, m in report['manifests'].items()},
    }
    out = RUNS / f'comparison_{A_LABEL}_vs_{B_LABEL}.json'
    out.write_text(json.dumps(report, indent=1, sort_keys=True, default=str))
    print(json.dumps(report['verdict'], indent=1, sort_keys=True))
    print('per_round_team_summary_identical_rounds_ge1 =',
          report['per_round_team_summary_identical_rounds_ge1'])
    print('wrote', out)


if __name__ == '__main__':
    main()
