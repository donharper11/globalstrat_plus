"""
Create a ready-to-play test game with test users and enrollments.

Usage: python manage.py setup_test_game [--flush] [--scenario <id>]
"""
import hashlib
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.utils import timezone

from core.models.core import User, Game, Team, Round
from core.models.course import Course, Section, SimulationInstance, Enrollment
from core.models.scenario import Scenario, FirmStarterProfile


def _hash(plain):
    return hashlib.sha256(plain.encode()).hexdigest()


STUDENTS = [
    ('student1', 'student1pass', 'Alex Chen'),
    ('student2', 'student2pass', 'Jordan Park'),
    ('student3', 'student3pass', 'Morgan Liu'),
    ('student4', 'student4pass', 'Sam Rivera'),
    ('team1_student', 'changeme123', 'Taylor Kim'),
]

INSTRUCTOR = ('instructor', 'instructorpass', 'Instructor')


class Command(BaseCommand):
    help = 'Create a complete test game with users, enrollments, and Round 0 results'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush', action='store_true',
            help='Delete existing test game data before creating',
        )
        parser.add_argument(
            '--scenario', type=int, default=None,
            help='Scenario ID (default: first available)',
        )

    def handle(self, *args, **options):
        flush = options['flush']
        scenario_id = options['scenario']

        # 1. Find or validate scenario
        if scenario_id:
            try:
                scenario = Scenario.objects.get(pk=scenario_id)
            except Scenario.DoesNotExist:
                raise CommandError(f"Scenario {scenario_id} not found.")
        else:
            scenario = Scenario.objects.first()
            if not scenario:
                raise CommandError(
                    "No scenarios found. Run: python manage.py load_scenario electronics"
                )

        # 2. Flush old test data if requested
        if flush:
            self.stdout.write('Flushing old test game data...')
            # Delete old games (cascades to teams, rounds, results, decisions)
            Game.objects.filter(name__icontains='Test Game').delete()
            # Clean ALL games if none match the name pattern
            if not Game.objects.exists():
                self.stdout.write('  No games remain — clean slate.')
            # Clean stale enrollments pointing to teams that no longer exist
            from core.models import Enrollment as _Enr
            stale = _Enr.objects.exclude(
                team_id__in=Team.objects.values_list('id', flat=True),
            ).filter(team_id__isnull=False)
            if stale.exists():
                count = stale.count()
                stale.delete()
                self.stdout.write(f'  Deleted {count} stale enrollment(s) pointing to deleted teams')
            # Clear stale team_id on users table
            from core.models import User as _User
            stale_users = _User.objects.filter(
                team_id__isnull=False,
            ).exclude(
                team_id__in=Team.objects.values_list('id', flat=True),
            )
            if stale_users.exists():
                count = stale_users.count()
                stale_users.update(team_id=None)
                self.stdout.write(f'  Cleared team_id on {count} user(s) pointing to deleted teams')
            # Clear stale CC-24 impact records
            from django.db import connection
            for table in [
                'esg_economic_impact', 'talent_economic_impact',
                'partnership_economic_impact',
            ]:
                try:
                    with connection.cursor() as c:
                        c.execute(f'DELETE FROM {table}')
                except Exception:
                    pass

        # 3. Create test users (in legacy users table)
        instructor_user = self._ensure_user(
            INSTRUCTOR[0], INSTRUCTOR[1], INSTRUCTOR[2], 'instructor',
        )

        student_users = []
        for username, password, display in STUDENTS:
            u = self._ensure_user(username, password, display, 'student')
            student_users.append(u)

        # 4. Create game via initialize_game
        from django.contrib.auth.models import User as AuthUser
        admin_user = AuthUser.objects.filter(is_superuser=True).first()
        if not admin_user:
            raise CommandError("No Django superuser found. Run: manage.py createsuperuser")

        profiles = list(FirmStarterProfile.objects.filter(scenario=scenario))
        if not profiles:
            raise CommandError(f"No starter profiles for scenario '{scenario.name}'.")

        self.stdout.write(f'Creating game with scenario: {scenario.name}')
        call_command(
            'initialize_game',
            scenario=scenario.pk,
            teams=4,
            name='GlobalStrat Test Game',
        )

        game = Game.objects.filter(name='GlobalStrat Test Game').order_by('-id').first()
        if not game:
            raise CommandError("Game creation failed.")

        teams = list(Team.objects.filter(game=game).order_by('id'))

        # 5. Assign students to teams
        for i, user in enumerate(student_users):
            team = teams[i % len(teams)]
            user.team_id = team.id
            user.display_name = f"{STUDENTS[i][2]} ({team.name})"
            user.save()

        # 6. Create course/section/enrollment chain
        course, _ = Course.objects.get_or_create(
            course_code='STRAT-TEST',
            defaults={
                'course_name': 'GlobalStrat Test Course',
                'instructor_id': instructor_user.user_id,
                'academic_year': '2026',
                'semester': 'Spring',
                'is_active': True,
                'created_at': timezone.now(),
            },
        )
        course.instructor_id = instructor_user.user_id
        course.is_active = True
        course.save()

        section, _ = Section.objects.get_or_create(
            course=course,
            section_code='TEST-01',
            defaults={
                'section_name': 'Test Section',
                'is_active': True,
                'created_at': timezone.now(),
            },
        )
        section.is_active = True
        section.save()

        instance, _ = SimulationInstance.objects.get_or_create(
            section=section,
            defaults={
                'game_id': game.id,
                'current_round': game.current_round,
                'total_rounds': scenario.num_rounds,
                'status': 'active',
                'started_at': timezone.now(),
                'created_at': timezone.now(),
            },
        )
        instance.game_id = game.id
        instance.status = 'active'
        instance.save()

        # Create enrollments
        for i, user in enumerate(student_users):
            team = teams[i % len(teams)]
            Enrollment.objects.update_or_create(
                user_id=user.user_id,
                section=section,
                defaults={
                    'team_id': team.id,
                    'enrolled_at': timezone.now(),
                    'is_active': True,
                },
            )

        # 7. Print results
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Test game created: "{game.name}" (ID: {game.id})'
        ))
        self.stdout.write('')
        self.stdout.write('Login credentials:')
        self.stdout.write('─' * 60)
        for i, (username, password, display) in enumerate(STUDENTS):
            team = teams[i % len(teams)]
            profile = team.firm_starter_profile
            self.stdout.write(
                f'  {username} / {password} → {team.name} ({profile.profile_name})'
            )
        self.stdout.write(
            f'  {INSTRUCTOR[0]} / {INSTRUCTOR[1]} → Instructor (all teams visible)'
        )
        self.stdout.write('')
        self.stdout.write(f'Round 0 results generated. Round 1 is open.')
        self.stdout.write(f'Frontend: http://localhost:3002')
        self.stdout.write(f'Backend:  http://localhost:8002')

    def _ensure_user(self, username, password, display_name, role):
        """Create or update a user in the legacy users table."""
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'password_hash': _hash(password),
                'role': role,
                'display_name': display_name,
            },
        )
        if not created:
            user.password_hash = _hash(password)
            user.role = role
            user.display_name = display_name
            user.save()
        return user
