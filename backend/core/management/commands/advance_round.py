"""
Management command to advance a game's round.

Usage:
    python manage.py advance_round <game_id>
    python manage.py advance_round <game_id> --dry-run
"""
from django.core.management.base import BaseCommand, CommandError

from core.models.core import Game


class Command(BaseCommand):
    help = 'Advance a game round by running the full engine pipeline (Steps 1-17).'

    def add_arguments(self, parser):
        parser.add_argument('game_id', type=int, help='ID of the game to advance')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run all calculations but roll back database changes.',
        )

    def handle(self, *args, **options):
        game_id = options['game_id']
        dry_run = options['dry_run']

        try:
            game = Game.objects.get(id=game_id)
        except Game.DoesNotExist:
            raise CommandError(f'Game with ID {game_id} does not exist.')

        self.stdout.write(
            f'Advancing round for Game "{game.name}" (ID: {game_id})'
        )
        if game.scenario:
            self.stdout.write(f'Scenario: {game.scenario.name}')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be saved'))

        self.stdout.write('')

        try:
            from core.engine.advance_round import advance_round
            context = advance_round(game_id, dry_run=dry_run)
        except ValueError as e:
            raise CommandError(str(e))

        # Print summary
        self.stdout.write(self.style.SUCCESS('Engine pipeline complete (Steps 1-17)'))
        self.stdout.write('')

        # Events (CC-7 enhanced output)
        if context.events_fired:
            self.stdout.write(f'=== Events This Round ({len(context.events_fired)}) ===')
            self.stdout.write('')
            for event in context.events_fired:
                template = event.event_template
                self.stdout.write(
                    f'Event: {template.name} (severity: {template.severity})'
                )
                market_name = event.target_market.name if event.target_market else 'Global'
                self.stdout.write(f'Market: {market_name}')
                self.stdout.write(f'Narrative: {event.narrative}')
                self.stdout.write(
                    f'Response required: {"Yes" if template.response_required else "No"}'
                )
                self.stdout.write('')
        else:
            self.stdout.write('Events fired: 0')

        # Fit scores summary
        fit_scores = context.fit_scores
        if fit_scores:
            self.stdout.write(f'\nPreference matching: {len(fit_scores)} combinations scored')
            non_zero = {k: v for k, v in fit_scores.items() if v > 0}
            if non_zero:
                best_key = max(non_zero, key=non_zero.get)
                worst_key = min(non_zero, key=non_zero.get)
                self.stdout.write(f'  Highest fit: {non_zero[best_key]:.4f}')
                self.stdout.write(f'  Lowest fit:  {non_zero[worst_key]:.4f}')

        # Adoption summary
        adoption = context.adoption
        if adoption:
            total = sum(adoption.values())
            self.stdout.write(f'\nBass adoption: {total:,.0f} total new adopters')

            caps_hit = [
                k for k, v in context.production_remaining.items() if v <= 0
            ]
            if caps_hit:
                self.stdout.write(
                    f'Production caps hit: {len(caps_hit)} product-market combinations'
                )

        # Financial summary
        financials = getattr(context, 'financials', {})
        if financials:
            self.stdout.write('\n=== Financial Results ===')
            for team in context.teams:
                fin = financials.get(team.id, {})
                rev = fin.get('total_revenue', 0)
                ni = fin.get('net_income', 0)
                sr = fin.get('shareholder_return', 0)
                d2e = fin.get('debt_to_equity', 0)
                self.stdout.write(
                    f'  {team.name}: '
                    f'Revenue ${rev:,.0f} | '
                    f'Net Income ${ni:,.0f} | '
                    f'D/E {d2e:.2f} | '
                    f'Return {sr:.2%}'
                )

        # Full log
        if context.log:
            self.stdout.write('\n--- Engine Log ---')
            for entry in context.log:
                self.stdout.write(f'  {entry}')

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '\nDRY RUN complete — no changes saved to database.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nRound processed. Game advanced.'
            ))
