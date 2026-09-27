"""Aggregate the non-negotiable checks for one completed candidate round."""
import json
import pathlib
import sys

SCRATCH = pathlib.Path(__file__).resolve().parent
RECORDS = SCRATCH.parent / 'records'
ROUND = int(sys.argv[1])
LANG = sys.argv[2]

instructor = json.loads((RECORDS / ('instructor-round%d-console-%s.json'
                                    % (ROUND, LANG))).read_text())
accounting = json.loads((RECORDS / ('check-round%d.json' % ROUND)).read_text())
reasoning = json.loads((RECORDS / ('reasoning-round%d.json' % ROUND)).read_text())
ready = json.loads((RECORDS / ('ready-round%d.json' % ROUND)).read_text())


def step_pass(record, prefix):
    return any(row.get('outcome') == 'pass' and row.get('name', '').startswith(prefix)
               for row in record.get('steps', []))


process_refusals = [row for row in instructor.get('refused', [])
                    if 'round-control/process' in row.get('url', '')]
mutating_recovery = [row for row in instructor.get('api', [])
                     if any(piece in row.get('url', '')
                            for piece in ('/reopen/', '/force-close/', '/recover/'))]
checks = {
    'all_four_locked_before_close': len(instructor.get('observed', {}).get('locked_themselves') or []) == 4,
    'none_pending_at_close': not (instructor.get('observed', {}).get('pending_at_close') or []),
    'standard_processing_completed': step_pass(instructor, 'round %d processed' % ROUND),
    'next_round_opened': step_pass(instructor, 'round %d open after advance' % (ROUND + 1)),
    'no_processing_refusal': not process_refusals,
    'no_reopen_force_or_recovery_call': not mutating_recovery,
    'ready_checks_pass': all(ready.get('checks', {}).values()),
    'accounting_checks_pass': all(row.get('outcome') == 'pass'
                                  for row in accounting.get('checks', [])),
    'reasoning_checks_pass': all(row.get('outcome') == 'pass'
                                 for row in reasoning.get('checks', [])),
}
out = {'round': ROUND, 'checks': checks,
       'process_refusals': process_refusals,
       'mutating_recovery_calls': mutating_recovery,
       'locked_themselves': instructor.get('observed', {}).get('locked_themselves'),
       'pending_at_close': instructor.get('observed', {}).get('pending_at_close')}
path = RECORDS / ('acceptance-round%d.json' % ROUND)
path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
for name, ok in checks.items():
    print('%s %s' % ('PASS' if ok else 'FAIL', name))
print('record:', path)
raise SystemExit(0 if all(checks.values()) else 1)
