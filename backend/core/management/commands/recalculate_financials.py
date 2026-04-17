"""
Management command to recalculate revenue and financials for already-played rounds.

This re-runs the revenue → costs → financials pipeline without re-running
adoption, events, or other upstream steps. Useful when the revenue or cost
formulas change (e.g. adding channel/distributor margins) and we need to
retroactively update financial results for rounds that have already been played.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models.core import Game, Team, Round
from core.engine.utils import RoundContext


class Command(BaseCommand):
    help = 'Recalculate revenue and financials for already-played rounds'

    def add_arguments(self, parser):
        parser.add_argument('game_id', type=int, help='Game ID to recalculate')
        parser.add_argument(
            '--rounds', type=str, default=None,
            help='Comma-separated round numbers to recalculate (default: all processed rounds)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would change without writing to the database',
        )

    def handle(self, *args, **options):
        game_id = options['game_id']
        dry_run = options['dry_run']

        try:
            game = Game.objects.get(id=game_id)
        except Game.DoesNotExist:
            raise CommandError(f'Game {game_id} not found')

        # Determine which rounds to recalculate
        processed_rounds = Round.objects.filter(
            game=game, status='processed',
        ).order_by('round_number')

        if options['rounds']:
            round_nums = [int(r.strip()) for r in options['rounds'].split(',')]
            processed_rounds = processed_rounds.filter(round_number__in=round_nums)
        else:
            # Skip Round 0 by default — it's bootstrapped from starter profiles,
            # not computed by the engine pipeline
            processed_rounds = processed_rounds.exclude(round_number=0)

        if not processed_rounds.exists():
            raise CommandError('No processed rounds found to recalculate')

        round_numbers = list(processed_rounds.values_list('round_number', flat=True))
        self.stdout.write(f'Game: {game.name} (ID: {game_id})')
        self.stdout.write(f'Rounds to recalculate: {round_numbers}')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be saved'))
        self.stdout.write('')

        sid = None
        if dry_run:
            sid = transaction.savepoint()

        try:
            for round_num in round_numbers:
                self._recalculate_round(game, round_num)

            if dry_run:
                transaction.savepoint_rollback(sid)
                self.stdout.write(self.style.WARNING('\nDry run complete — all changes rolled back'))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'\nRecalculation complete for {len(round_numbers)} rounds'
                ))
        except Exception:
            if dry_run and sid:
                transaction.savepoint_rollback(sid)
            raise

    def _recalculate_round(self, game, round_number):
        """Recalculate revenue and financials for a single round."""
        from core.engine.revenue import calculate_revenue
        from core.engine.costs import (
            calculate_cogs, calculate_logistics_tariffs,
            calculate_operating_expenses, calculate_interest,
            calculate_tax, calculate_inventory_costs, calculate_retirement_costs,
        )
        from core.engine.financials import generate_financial_statements
        from core.engine.events import update_market_conditions
        from core.models.results_financials import RoundResultFinancials

        self.stdout.write(f'── Round {round_number} ──')

        # Build context (same as advance_round but without running adoption/events)
        context = RoundContext(game, round_number)

        # We need market conditions applied for exchange rates
        update_market_conditions(context)

        # Capture pre-recalc financials for comparison
        pre_financials = {}
        for fin in RoundResultFinancials.objects.filter(game=game, round_number=round_number):
            pre_financials[fin.team_id] = {
                'total_revenue': fin.total_revenue,
                'gross_profit': fin.gross_profit,
                'net_income': fin.net_income,
            }

        # Re-run revenue → full cost pipeline → financials
        calculate_revenue(context)
        calculate_cogs(context)
        calculate_logistics_tariffs(context)
        calculate_operating_expenses(context)
        calculate_interest(context)
        calculate_tax(context)
        calculate_inventory_costs(context)
        calculate_retirement_costs(context)
        generate_financial_statements(context)

        # Report changes
        for team in context.teams:
            pre = pre_financials.get(team.id, {})
            post_fin = RoundResultFinancials.objects.filter(
                game=game, round_number=round_number, team=team,
            ).first()
            if not post_fin:
                continue

            old_rev = pre.get('total_revenue', Decimal('0'))
            new_rev = post_fin.total_revenue
            margin = post_fin.total_channel_margin

            self.stdout.write(
                f'  {team.name}: '
                f'gross_rev=${post_fin.gross_revenue:,.0f} '
                f'- channel_margin=${margin:,.0f} '
                f'= net_rev=${new_rev:,.0f} '
                f'(was ${old_rev:,.0f}, '
                f'delta=${new_rev - old_rev:,.0f})'
            )

        for entry in context.log:
            self.stdout.write(f'  {entry}')
        self.stdout.write('')
