#!/usr/bin/env python3
"""Tamper with exactly one stored value, for the manifest negative tests.

GSP-CRV2-01 requires that a corrupted decision payload, scenario value or
carried-state value each fail manifest verification *before* the engine runs.
This writes the corruption; `manage.py replay_round --verify-only` detects it.

ISOLATED USE ONLY. Point DB_* at a disposable stack.

    cd backend && DB_NAME=globalstrat_replay \
      python3 ../handoff_readiness_v2/corrupt_one_value.py decision 32
"""
import os
import sys

import django

# Importable whether it is run from backend/ or by absolute path.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')
django.setup()

from decimal import Decimal as D  # noqa: E402

from core.models import Game  # noqa: E402
from core.models.decisions import DecisionMarketing  # noqa: E402
from core.models.scenario import SegmentPreference  # noqa: E402


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: corrupt_one_value.py '
                         '{decision|scenario|carried} <game_id>')
    kind, game_id = sys.argv[1], int(sys.argv[2])
    game = Game.objects.get(pk=game_id)

    if kind == 'decision':
        row = DecisionMarketing.objects.filter(
            submission__team__game=game).order_by('id').first()
        before = row.retail_price
        row.retail_price = D(before) + D('1.00')
        row.save(update_fields=['retail_price'])
        print(f'decision_marketing[{row.id}].retail_price '
              f'{before} -> {row.retail_price}')
    elif kind == 'scenario':
        row = SegmentPreference.objects.filter(
            segment__scenario=game.scenario).order_by('id').first()
        before = row.weight
        row.weight = (before or 0) + 1
        row.save(update_fields=['weight'])
        print(f'segment_preference[{row.id}].weight {before} -> {row.weight}')
    elif kind == 'carried':
        team = game.teams.order_by('id').first()
        before = team.cash_on_hand
        team.cash_on_hand = D(before) + D('1000000.00')
        team.save(update_fields=['cash_on_hand'])
        print(f'team[{team.id}].cash_on_hand {before} -> {team.cash_on_hand}')
    else:
        raise SystemExit(f'unknown corruption kind: {kind}')


if __name__ == '__main__':
    main()
