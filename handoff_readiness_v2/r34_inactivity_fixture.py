#!/usr/bin/env python3
"""Build a disposable game whose round 1 makes the R32 inactivity guard FIRE.

R34 records a guard firing as an audit event. The guard has **never fired in
stored play** (the 2026-09-16 measurement: 448 index rows, worst `index_change`
−5.82), so a replay over any recorded round would reproduce the *absence* of
the firing and call that a pass. This fixture therefore constructs the firing
deterministically and then ASSERTS it happened, exiting non-zero and naming
what was missing rather than resolving a round that proves nothing.

Three things have to be true for this round to be evidence for R34:

  1. **A firm is classified commercially inactive.** `material_revenue_floor`
     is one percent of the largest positive revenue in the round, so a team
     that sells nothing while its rivals sell is below the floor. The team is
     given a budget and a locked submission but **no marketing rows at all**,
     which is what produces revenue of exactly zero: `bass_engine` builds its
     offer map from `DecisionMarketing`, so a team with no rows takes no
     demand. Declaring an intention to produce is not competing (V2-022).

  2. **The demotion is a genuine INVERSION**, not a firm that would have
     finished last anyway. The inactive team's carried performance index is
     raised before resolution, so that after the bounded −5.00 composite cap it
     still holds a **higher** index than every firm that competed — and is
     still ranked below all of them. That is exactly the situation R34 exists
     to explain: "index 90.00, rank 4" above "index 55.00, rank 1".

  3. **The receipt exists** — one `inactivity_rank_demotion` audit event for
     the demoted team, carrying the lowest active index and the rank received.

Modelled on `v6_envelope_fixture.py` and deliberately reusing its `seed_round`
for the ordinary, non-degenerate decision set, so the only difference between
the competing teams here and that fixture's is the one team held out.

ISOLATED USE ONLY. Point DB_* at a disposable stack.

    cd backend && python3 ../handoff_readiness_v2/r34_inactivity_fixture.py --teams 4
"""
import argparse
import io
import json
import os
import sys
from decimal import Decimal as D

import django

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')
django.setup()

from django.core.management import call_command  # noqa: E402
from django.utils import timezone  # noqa: E402

from core.models import (  # noqa: E402
    DecisionAuditEvent, DecisionSubmission, Game, Round, Team)
from core.models.decisions import DecisionMarketing  # noqa: E402
from core.models.results_financials import (  # noqa: E402
    LeaderboardEntry, RoundResultFinancials, RoundResultPerformanceIndex)
from core.models.scenario import Scenario  # noqa: E402
from core.engine import leaderboard as lb  # noqa: E402


class SurfaceEmpty(RuntimeError):
    """A condition this fixture exists to create did not occur."""


def hold_one_team_out(game, round_obj, carried_index):
    """Strip one team back to "did not compete", and raise what it carries.

    Returns the team held out. Its submission and budget stay — the team is
    present and locked, it simply sold nothing — because a team with no
    submission at all is the *different* case that `close_round` defaults, and
    conflating the two would test the wrong control.
    """
    team = Team.objects.filter(game=game).order_by('id').last()
    submission = DecisionSubmission.objects.filter(
        team=team, round=round_obj).first()
    if submission is None:
        raise SurfaceEmpty(f'No submission to strip for team {team.name}.')

    removed = DecisionMarketing.objects.filter(submission=submission).delete()
    # Carried state, set before resolution and therefore inside the input
    # envelope like any other carried value. This is what makes the demotion an
    # inversion rather than a firm that was last regardless.
    team.performance_index = D(carried_index)
    team.save(update_fields=['performance_index'])
    return team, removed


def main():
    # V2-128: never write a pre-resolution dump into the live backup root.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from harness_isolation import require_disposable_backup_dir
    require_disposable_backup_dir()

    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', type=int)
    parser.add_argument('--teams', type=int, default=4)
    parser.add_argument('--name', default='R34-INACTIVITY-FIXTURE')
    parser.add_argument('--section-id', type=int, default=90634)
    parser.add_argument('--carried-index', default='95.00',
                        help="The inactive team's carried index before the round.")
    parser.add_argument('--summary', help='Write a JSON summary here.')
    args = parser.parse_args()

    scenario = (Scenario.objects.get(pk=args.scenario) if args.scenario
                else Scenario.objects.order_by('id').first())
    call_command('initialize_game', scenario=scenario.id, teams=args.teams,
                 name=args.name, stdout=io.StringIO())
    game = Game.objects.filter(name=args.name).order_by('-id').first()
    game.section_id = args.section_id
    game.save(update_fields=['section_id'])

    round_obj = Round.objects.get(game=game, round_number=game.current_round)

    # The ordinary decision set, reused verbatim so the competing teams are a
    # realistic field rather than a two-team toy.
    from v6_envelope_fixture import seed_round
    seed_round(game, round_obj, scenario)

    idle, removed = hold_one_team_out(game, round_obj, args.carried_index)

    summary = {
        'game_id': game.id, 'scenario_id': scenario.id,
        'round_number': round_obj.round_number, 'teams': args.teams,
        'held_out': {
            'team': idle.name, 'team_id': idle.id,
            'carried_index_before_round': str(idle.performance_index),
            'marketing_rows_removed': removed[0],
        },
    }

    from core.engine.advance_round import close_round, process_round
    round_obj.deadline = timezone.now()
    round_obj.save(update_fields=['deadline'])
    close_round(game.id, reason='r34-inactivity-fixture')
    process_round(game.id)

    # --- the guard actually fired, and the inversion is real ---------------
    events = list(DecisionAuditEvent.objects.filter(
        round=round_obj, action=lb.ACTION_INACTIVITY_DEMOTION).order_by('id'))
    entries = {e.team.name: e for e in LeaderboardEntry.objects.filter(
        game=game, round_number=round_obj.round_number).select_related('team')}
    revenues = {f.team.name: str(f.total_revenue)
                for f in RoundResultFinancials.objects.filter(
                    game=game, round_number=round_obj.round_number,
                ).select_related('team')}
    indexes = {p.team.name: str(p.index_value)
               for p in RoundResultPerformanceIndex.objects.filter(
                   game=game, round_number=round_obj.round_number,
               ).select_related('team')}

    idle_entry = entries.get(idle.name)
    active_entries = [e for name, e in entries.items() if name != idle.name]
    summary['after_resolution'] = {
        'demotion_events': len(events),
        'demotion_payloads': [e.payload for e in events],
        'revenues': revenues,
        'index_values': indexes,
        'ranks': {name: e.rank for name, e in entries.items()},
        'published_indexes': {name: str(e.performance_index)
                              for name, e in entries.items()},
    }

    if not events:
        raise SurfaceEmpty(
            'The inactivity guard did not fire: no inactivity_rank_demotion '
            'event. A replay of this round would prove nothing about R34.')
    if idle_entry is None:
        raise SurfaceEmpty(f'No leaderboard entry for {idle.name}.')
    worst_active_rank = max(e.rank for e in active_entries)
    if idle_entry.rank <= worst_active_rank:
        raise SurfaceEmpty(
            f'{idle.name} ranked {idle_entry.rank}, not below every firm that '
            f'competed (worst active rank {worst_active_rank}).')
    outscored = [e.team.name for e in active_entries
                 if D(str(e.performance_index)) < D(str(idle_entry.performance_index))]
    if not outscored:
        raise SurfaceEmpty(
            'The demotion cost no places: the inactive firm did not outscore '
            'any firm ranked above it, so this round does not exhibit the '
            'inversion R34 exists to explain.')
    if not events[0].payload.get('outscored_a_firm_ranked_above'):
        raise SurfaceEmpty(
            'The recorded payload does not report the inversion it exhibits.')
    summary['after_resolution']['outscored_firms_ranked_above'] = outscored

    manifest = Round.objects.get(pk=round_obj.pk).resolution_manifest
    summary['manifest'] = {
        'schema_version': manifest.schema_version,
        'input_sha256': manifest.input_sha256,
        'output_sha256': manifest.output_sha256,
        'narrative_sha256': manifest.narrative_sha256,
        'code_revision': manifest.code_revision,
        'source_tree_sha256': manifest.source_tree_sha256,
        'backup_path': manifest.backup_path,
        'input_decision_audit_event_rows': len(
            (manifest.input_manifest or {}).get(
                'sections', {}).get('decision_audit_event', [])),
    }
    if manifest.schema_version != 6:
        raise SurfaceEmpty(
            f'Manifest is schema version {manifest.schema_version}, not 6. '
            f'R34 must not move the envelope.')

    print(json.dumps(summary, indent=2, default=str))
    if args.summary:
        with open(args.summary, 'w', encoding='utf-8') as handle:
            json.dump(summary, handle, indent=2, sort_keys=True, default=str)


if __name__ == '__main__':
    main()
