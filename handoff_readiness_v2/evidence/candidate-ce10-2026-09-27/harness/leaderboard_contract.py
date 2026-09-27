"""Assertions for the published leaderboard order used by the CE10 harness."""


def _score(row):
    try:
        return float(row.get('performance_index'))
    except (TypeError, ValueError):
        return None


def validate_leaderboard(entries, rank_rule_note):
    """Validate score order without rejecting the published R32 demotion rule.

    Active firms are score-ordered first.  Firms explicitly marked
    commercially inactive form a trailing score-ordered group and must carry
    both the per-row marker and the API's explanatory rule note.
    """
    active = [row for row in entries if not row.get('commercially_inactive')]
    inactive = [row for row in entries if row.get('commercially_inactive')]
    scores_present = all(_score(row) is not None for row in entries)

    def descending(rows):
        return all(_score(rows[i]) >= _score(rows[i + 1])
                   for i in range(len(rows) - 1))

    groups_ordered = entries == active + inactive
    score_ordered = (scores_present and descending(active)
                     and descending(inactive))
    markers_correct = (
        all(not row.get('rank_marker') for row in active)
        and all(row.get('rank_marker') for row in inactive)
    )
    rule_explained = bool(rank_rule_note) if inactive else not rank_rule_note

    ranks = [row.get('rank') for row in entries]
    ranks_valid = bool(ranks) and ranks[0] == 1
    if ranks_valid:
        previous = ranks[0]
        for position, rank in enumerate(ranks, 1):
            if not isinstance(rank, int) or rank < previous:
                ranks_valid = False
                break
            if rank != previous and rank != position:
                ranks_valid = False
                break
            previous = rank

    return {
        'active_then_inactive': groups_ordered,
        'score_ordered_within_groups': score_ordered,
        'inactivity_markers_correct': markers_correct,
        'rank_rule_explained': rule_explained,
        'published_ranks_valid': ranks_valid,
    }
