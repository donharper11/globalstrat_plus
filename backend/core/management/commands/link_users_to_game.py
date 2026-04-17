"""
Re-link student users to the current active game's teams.

Fixes the recurring issue where User.team_id, Enrollment.team_id, and
SimulationInstance.game_id go stale after teams are recreated with new IDs.

Matches users to teams by position (student1 → Team 1, student2 → Team 2, etc.)
and by name pattern (team1_student → Team 1).

Usage:
    python manage.py link_users_to_game            # auto-detect game
    python manage.py link_users_to_game --game 61   # specify game ID
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models.core import User, Game, Team
from core.models.course import Section, SimulationInstance, Enrollment


class Command(BaseCommand):
    help = 'Re-link student users to the current game teams'

    def add_arguments(self, parser):
        parser.add_argument(
            '--game', type=int, default=None,
            help='Game ID (default: most recent active/completed game)',
        )

    def handle(self, *args, **options):
        game_id = options['game']

        # Find game
        if game_id:
            try:
                game = Game.objects.get(pk=game_id)
            except Game.DoesNotExist:
                raise CommandError(f"Game {game_id} not found.")
        else:
            game = Game.objects.order_by('-id').first()
            if not game:
                raise CommandError("No games found.")

        teams = list(Team.objects.filter(game=game).order_by('id'))
        if not teams:
            raise CommandError(f"No teams in game '{game.name}' (ID: {game.id}).")

        self.stdout.write(f'Game: {game.name} (ID: {game.id})')
        self.stdout.write(f'Teams: {", ".join(f"{t.name} (ID:{t.id})" for t in teams)}')

        # Build team lookup by number
        team_by_num = {}
        for t in teams:
            # Extract number from "Team 1", "Team 2", etc.
            for word in t.name.split():
                try:
                    team_by_num[int(word)] = t
                except ValueError:
                    continue

        # Find all student users
        students = User.objects.filter(role='student')
        linked = 0

        for user in students:
            team = None

            # Match by name pattern: "team1_student" → Team 1
            for num, t in team_by_num.items():
                if f'team{num}' in user.username.lower():
                    team = t
                    break

            # Match by name pattern: "student1" → Team 1
            if not team:
                for num, t in team_by_num.items():
                    if f'student{num}' in user.username.lower():
                        team = t
                        break

            # Fallback: assign by index
            if not team:
                idx = list(students).index(user) % len(teams)
                team = teams[idx]

            if user.team_id != team.id:
                old_id = user.team_id
                user.team_id = team.id
                user.save(update_fields=['team_id'])
                self.stdout.write(
                    f'  {user.username}: team_id {old_id} → {team.id} ({team.name})'
                )
                linked += 1
            else:
                self.stdout.write(f'  {user.username}: already correct ({team.name})')

        # Fix SimulationInstance → game linkage
        sections = Section.objects.filter(is_active=True)
        for section in sections:
            instance, created = SimulationInstance.objects.get_or_create(
                section=section,
                defaults={
                    'game_id': game.id,
                    'status': 'active',
                    'started_at': timezone.now(),
                    'created_at': timezone.now(),
                },
            )
            if instance.game_id != game.id:
                old_gid = instance.game_id
                instance.game_id = game.id
                instance.save(update_fields=['game_id'])
                self.stdout.write(
                    f'  SimulationInstance (section {section.section_code}): '
                    f'game_id {old_gid} → {game.id}'
                )
            elif created:
                self.stdout.write(
                    f'  SimulationInstance (section {section.section_code}): created → game {game.id}'
                )

        # Fix Enrollment.team_id
        enrollments = Enrollment.objects.filter(is_active=True)
        for enr in enrollments:
            user = User.objects.filter(user_id=enr.user_id).first()
            if user and user.team_id and enr.team_id != user.team_id:
                old_tid = enr.team_id
                enr.team_id = user.team_id
                enr.save(update_fields=['team_id'])
                self.stdout.write(
                    f'  Enrollment (user {user.username}): '
                    f'team_id {old_tid} → {enr.team_id}'
                )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done. {linked} user(s) re-linked to game {game.id}.'
        ))
