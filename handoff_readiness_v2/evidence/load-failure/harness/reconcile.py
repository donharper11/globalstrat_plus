"""Write reconciliation: nothing acknowledged is lost, nothing extra appears.

Run inside `manage.py shell` against the load database after a profile.

Each accepted save writes one append-only `DecisionAuditEvent` carrying the
`X-Request-ID` the driver sent. Two exact questions follow:

  * every acknowledged request id must appear exactly once -- a missing id is a
    lost write, a repeated one is a duplicate;
  * every audit row's request id must be one the driver acknowledged -- a row
    with an unknown id is an unexplained write, and a row carrying an id the
    API *refused* is worse: the write was rejected to the caller and kept
    anyway.
"""


def run(acknowledged, refused):
    from collections import Counter
    from core.models import DecisionAuditEvent

    acknowledged_ids = [w['request_id'] for w in acknowledged]
    refused_ids = {w['request_id'] for w in refused}

    rows = list(DecisionAuditEvent.objects.filter(
        action='save').values_list('request_id', flat=True))
    seen = Counter(r for r in rows if r)

    missing = [rid for rid in acknowledged_ids if seen[rid] == 0]
    duplicated = {rid: seen[rid] for rid in acknowledged_ids if seen[rid] > 1}
    known = set(acknowledged_ids)
    unexplained = [rid for rid in seen if rid.startswith('load-')
                   and rid not in known]
    refused_but_recorded = [rid for rid in seen if rid in refused_ids]

    return {
        'acknowledged_writes': len(acknowledged_ids),
        'refused_writes': len(refused_ids),
        'audit_rows_with_request_id': sum(seen.values()),
        'lost_writes': missing[:20],
        'lost_write_count': len(missing),
        'duplicated_writes': dict(list(duplicated.items())[:20]),
        'duplicated_write_count': len(duplicated),
        'unexplained_rows': unexplained[:20],
        'unexplained_row_count': len(unexplained),
        'refused_but_recorded': refused_but_recorded[:20],
        'refused_but_recorded_count': len(refused_but_recorded),
        'reconciles': (not missing and not duplicated and not unexplained
                       and not refused_but_recorded),
    }
