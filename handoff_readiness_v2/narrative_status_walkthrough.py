#!/usr/bin/env python3
"""One instructor request against a real round, printed as an auditor sees it.

Proves the endpoint answers "where is my briefing?" with live data rather than
a fixture: it resolves nothing, it reads.

ISOLATED USE ONLY.

    cd backend && DB_NAME=globalstrat_replay \
      python3 ../handoff_readiness_v2/narrative_status_walkthrough.py \
        --game 37 --out <dir>
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
from rest_framework.test import APIClient                            # noqa: E402

# APIClient addresses the app as `testserver`. Outside the test runner that is
# not an allowed host, so the walkthrough would get a 400 from middleware
# before reaching the view. Harness-only: the deployed ALLOWED_HOSTS is
# untouched.
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

from core.authentication import create_access_token                  # noqa: E402
from core.models import Game, User                                   # noqa: E402
from core.services.build_identity import build_identity              # noqa: E402


def call(user, game_id):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
    return client.get(f'/api/games/{game_id}/round-control/')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game', type=int, required=True, dest='game_id')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()

    game = Game.objects.get(pk=args.game_id)
    instructor = User.objects.filter(role__in=('instructor', 'admin')).first()
    student = User.objects.filter(role='student').first()
    if instructor is None:
        raise SystemExit('No instructor account on this stack.')

    identity = build_identity()
    instructor_response = call(instructor, game.id)
    student_response = call(student, game.id) if student else None

    payload = instructor_response.data.get('narratives')
    report = {
        'code_revision': identity['code_revision'],
        'source_tree_sha256': identity['source_tree_sha256'],
        'game_id': game.id,
        'endpoint': f'GET /api/games/{game.id}/round-control/',
        'instructor': {'username': instructor.username,
                       'status_code': instructor_response.status_code},
        'student': ({'username': student.username,
                     'status_code': student_response.status_code}
                    if student_response is not None else None),
        'narratives': payload,
    }
    body = json.dumps(instructor_response.data, default=str)
    report['no_credential_in_response'] = not any(
        marker in body for marker in ('sk-', 'Bearer ', 'api_key='))

    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, 'instructor-status-walkthrough.json')
    with open(path, 'w', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, sort_keys=True, default=str)

    print(f"instructor {instructor.username}: "
          f"HTTP {instructor_response.status_code}")
    if student_response is not None:
        print(f"student    {student.username}: "
              f"HTTP {student_response.status_code}")
    if payload:
        print(f"summary: {payload['summary']}")
        for row in payload['jobs']:
            print(f"  {row['narrative_type']:<14} {row['state']:<10} "
                  f"degraded={str(row['degraded']):<5} "
                  f"attempts={row['attempts']}/{row['max_attempts']} "
                  f"model={row['model_name'] or '-'} "
                  f"tpl=v{row['template_version']} "
                  f"err={(row['last_error'] or '-')[:60]}")
    print('no credential in response:', report['no_credential_in_response'])


if __name__ == '__main__':
    main()
