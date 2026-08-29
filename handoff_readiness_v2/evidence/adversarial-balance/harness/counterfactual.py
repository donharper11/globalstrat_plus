"""Compare a team only with itself, from one frozen checkpoint.

The first screen compared a probe team against a *different* control team in
the same resolution. Those are different firms with different starter profiles
and products, so their outcomes differ before any dimension is varied, and the
comparison could not tell "this dimension moved something" from "these are two
different companies". It reported every dimension as escalate-worthy, which is
worth exactly as much as reporting none.

This measures the counterfactual instead. One game reaches a pre-resolution
checkpoint. Every evaluation opens a transaction from that identical
checkpoint, writes decisions, resolves the round, reads the metrics and rolls
back. `_run_phase_1` is itself atomic, so the outer transaction turns it into a
savepoint and nothing survives. The baseline and each probe therefore differ in
exactly one decision dimension and in nothing else — same game id, same section,
same scenario, same round, same roster, same starting state, same RNG stream.

Because everything rolls back, one game serves every probe, and no paired game
is needed — which also avoids inheriting V2-011, where the supply-chain and
compliance engines seed on `game.id` and two games would not share those
streams.
"""
from decimal import Decimal as D

from django.db import transaction


class _Rollback(Exception):
    """Raised to unwind an evaluation. Never escapes `evaluate`."""


METRIC_FIELDS = ('total_revenue', 'net_income', 'cash_closing',
                 'operating_income', 'strategy_expense')


def read_metrics(game, team, round_number):
    from core.models import RoundResultFinancials, RoundResultPerformanceIndex
    fin = (RoundResultFinancials.objects
           .filter(team=team, round_number=round_number).order_by('-id').first())
    idx = (RoundResultPerformanceIndex.objects
           .filter(team=team, round_number=round_number).order_by('-id').first())
    metrics = {f: (str(getattr(fin, f)) if fin else None) for f in METRIC_FIELDS}
    metrics['index_value'] = str(idx.index_value) if idx else None
    metrics['satisfaction_score'] = str(idx.satisfaction_score) if idx else None
    return metrics


def fingerprint(game, rnd):
    """Enough of the database to notice an evaluation that did not roll back."""
    from core.models import (DecisionSubmission, RoundResultFinancials,
                             RoundResultPerformanceIndex, Round, Team)
    from core.models.decisions import DecisionMarketing
    rnd.refresh_from_db()
    teams = list(Team.objects.filter(game=game).order_by('id'))
    return {
        'round_status': rnd.status,
        'round_processing': rnd.processing_status,
        'game_current_round': game.__class__.objects.get(pk=game.pk).current_round,
        'results_financial': RoundResultFinancials.objects.filter(game=game).count(),
        'results_index': RoundResultPerformanceIndex.objects.filter(game=game).count(),
        'submissions': DecisionSubmission.objects.filter(round=rnd).count(),
        'marketing_rows': DecisionMarketing.objects.filter(
            submission__round=rnd).count(),
        'team_cash': {t.id: str(t.cash_on_hand) for t in teams},
        'team_index': {t.id: str(t.performance_index) for t in teams},
    }


def context_identity(game, rnd):
    """The facts every evaluation must share. Asserted, not assumed."""
    from core.models import Team
    teams = list(Team.objects.filter(game=game).order_by('id'))
    return {
        'game_id': game.id,
        'section_id': game.section_id,
        'scenario_id': game.scenario_id,
        'round_number': rnd.round_number,
        'roster': [t.id for t in teams],
        'starter_profiles': {t.id: t.firm_starter_profile_id for t in teams},
        'starting_cash': {t.id: str(t.cash_on_hand) for t in teams},
    }


def evaluate(game, rnd, team, write_decisions):
    """Resolve once from the checkpoint and roll back. Returns metrics.

    `write_decisions()` writes every team's decisions inside the transaction,
    so a probe differs from the baseline only in what it changes.
    """
    from core.engine.advance_round import _run_phase_1

    captured = {}
    before = fingerprint(game, rnd)
    identity_before = context_identity(game, rnd)
    try:
        with transaction.atomic():
            write_decisions()
            _run_phase_1(game.id)
            captured.update(read_metrics(game, team, rnd.round_number))
            raise _Rollback()
    except _Rollback:
        pass
    after = fingerprint(game, rnd)
    identity_after = context_identity(game, rnd)

    if after != before:
        differences = {k: (before[k], after[k])
                       for k in before if before[k] != after[k]}
        raise AssertionError(
            f'the database did not return to the checkpoint: {differences}')
    if identity_after != identity_before:
        raise AssertionError('the evaluation context changed between runs')
    return captured


def delta(baseline, probe):
    out = {}
    for key, value in probe.items():
        base = baseline.get(key)
        if value is None or base is None:
            out[key] = None
            continue
        try:
            out[key] = str(D(value) - D(base))
        except Exception:
            out[key] = None
    return out


def is_zero(deltas):
    return all(v is None or D(v) == 0 for v in deltas.values())
