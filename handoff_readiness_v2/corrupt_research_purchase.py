#!/usr/bin/env python3
"""Tamper with one stored research-purchase price — the negative test for v6.

`corrupt_one_value.py` covers a decision payload, a scenario value and a
carried-state value. None of them touches `decision_research_purchase`, which
is the section the v5 -> v6 envelope change actually added. A replay that
refuses a tampered marketing price proves the v2-era envelope still works; only
a replay that refuses a tampered *purchase* price proves the NEW section is
inside the verified envelope rather than merely present in it.

ISOLATED USE ONLY. Point DB_* at a disposable stack.

    cd backend && python3 ../handoff_readiness_v2/corrupt_research_purchase.py <game_id>
"""
import os
import sys

import django

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')
django.setup()

from decimal import Decimal as D  # noqa: E402

from core.models import Game  # noqa: E402
from core.models.research import DecisionResearchPurchase  # noqa: E402


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: corrupt_research_purchase.py <game_id>')
    game = Game.objects.get(pk=int(sys.argv[1]))

    row = (DecisionResearchPurchase.objects
           .filter(submission__team__game=game)
           .order_by('id').first())
    if row is None:
        raise SystemExit(
            'No DecisionResearchPurchase rows for this game. The fixture did '
            'not seed the v6 section, so this negative test would prove '
            'nothing.')

    before = row.price
    row.price = D(before) + D('1.00')
    row.save(update_fields=['price'])
    print(f'decision_research_purchase[{row.id}] '
          f'({row.submission.team.name}, {row.report_type}, '
          f'scope_key={row.scope_key!r}).price {before} -> {row.price}')


if __name__ == '__main__':
    main()
