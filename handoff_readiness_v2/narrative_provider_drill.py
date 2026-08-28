#!/usr/bin/env python3
"""Drain a round's narrative jobs against a chosen provider condition.

One scenario per run: a working endpoint, an unreachable one, or no API key at
all. Each records what the jobs did and, in every case, whether the competitive
hash moved — which is the property that matters and the one the handoff names.

ISOLATED USE ONLY. Point DB_* at a disposable stack.

    cd backend && DB_NAME=globalstrat_replay \
      DASHSCOPE_COMPATIBLE_URL=http://127.0.0.1:9/v1/chat/completions \
      python3 ../handoff_readiness_v2/narrative_provider_drill.py \
        --game 37 --round 1 --scenario unreachable-endpoint --out <dir>
"""
import argparse
import json
import os
import sys

import django

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')
django.setup()

from django.conf import settings                                     # noqa: E402
from django.utils import timezone                                    # noqa: E402

from core.models import Game, Round                                  # noqa: E402
from core.models.narrative_jobs import NarrativeJob                  # noqa: E402
from core.services import narrative_jobs                             # noqa: E402
from core.services.build_identity import build_identity              # noqa: E402
from core.services.canonical_json import canonical_sha256            # noqa: E402
from core.services.resolution_manifest import build_output_manifest   # noqa: E402


def competitive_hash(round_obj):
    competitive, _narrative = build_output_manifest(round_obj)
    return canonical_sha256(competitive)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game', type=int, required=True, dest='game_id')
    parser.add_argument('--round', type=int, required=True, dest='round_number')
    parser.add_argument('--scenario', required=True,
                        help='Name for the evidence file, e.g. no-api-key.')
    parser.add_argument('--out', required=True, help='Evidence directory.')
    args = parser.parse_args()

    game = Game.objects.get(pk=args.game_id)
    round_obj = Round.objects.get(game=game, round_number=args.round_number)

    # Requeue so the drill has work, and clear any prior degradation so the
    # record describes this run only.
    NarrativeJob.objects.filter(round=round_obj).update(
        state=NarrativeJob.PENDING, attempts=0, last_error='', degraded=False,
        claimed_by='', claimed_at=None, claim_expires_at=None,
        completed_at=None)
    narrative_jobs.enqueue_round(game, round_obj)

    identity = build_identity()
    before = competitive_hash(round_obj)
    processed = narrative_jobs.drain(game_id=game.id)

    report = {
        'scenario': args.scenario,
        'code_revision': identity['code_revision'],
        'source_tree_sha256': identity['source_tree_sha256'],
        'llm_endpoint': getattr(settings, 'DASHSCOPE_COMPATIBLE_URL', ''),
        'llm_key_configured': bool(getattr(settings, 'DASHSCOPE_API_KEY', '')),
        'hash_before': before,
        'hash_after': competitive_hash(round_obj),
        'jobs': [{
            'type': job.narrative_type, 'state': job.state,
            'attempts': job.attempts, 'degraded': job.degraded,
            'last_error': job.last_error[:300],
            'model_name': job.model_name, 'model_endpoint': job.model_endpoint,
        } for job in sorted(processed, key=lambda j: j.narrative_type)],
        'backlog': narrative_jobs.backlog(game.id),
        'completed_at': timezone.now().isoformat(),
    }
    report['competitive_hash_unchanged'] = (
        report['hash_before'] == report['hash_after'])
    report['all_jobs_terminal'] = all(
        job['state'] in (NarrativeJob.SUCCEEDED, NarrativeJob.FAILED)
        for job in report['jobs'])
    # No credential may reach a row an instructor can read.
    report['no_secret_in_any_field'] = not any(
        marker in (job['last_error'] or '')
        for job in report['jobs'] for marker in ('sk-', 'Bearer', 'api_key='))

    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, f'provider-{args.scenario}.json')
    with open(path, 'w', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)

    print(f"{args.scenario}: hash_unchanged={report['competitive_hash_unchanged']} "
          f"terminal={report['all_jobs_terminal']} "
          f"degraded={report['backlog']['degraded']} "
          f"failed={report['backlog']['failed']} "
          f"secrets={not report['no_secret_in_any_field']}")
    ok = (report['competitive_hash_unchanged'] and report['all_jobs_terminal']
          and report['no_secret_in_any_field'])
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
