"""ORM-side helpers for the CRV2-08 completed game.

Only identities and description live here. Every decision, lock and lifecycle
action is driven through the HTTP API by `build_completed_game.py`, because an
audit trail written by the seeder proves nothing about what the product
records.
"""
THREE_TEAMS = 3


def seed_identities(game_placeholder, password):
    from django.contrib.auth.models import User as DjangoUser
    from django.core.management import call_command
    from django.utils import timezone

    from core.models import Enrollment, Game, Team, User
    from core.models.course import Section
    from core.utils.passwords import hash_password

    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('crv208admin', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)

    import fixture_contract as FC
    chosen, _ = FC.scenario_supporting(
        ('sourcing', 'trade_finance', 'compliance', 'logistics'))
    if chosen is None:
        from core.models import Scenario
        chosen = Scenario.objects.order_by('id').first()
    call_command('setup_test_game', '--scenario', str(chosen.id), verbosity=0)

    game = Game.objects.order_by('-id').first()
    section = Section.objects.order_by('section_id').first()
    hashed = hash_password(password)

    # Three teams exactly. Any extra team setup_test_game created is withdrawn
    # rather than deleted, so the game's own history stays consistent.
    roster = list(Team.objects.filter(game=game).order_by('id'))
    keep, retire = roster[:THREE_TEAMS], roster[THREE_TEAMS:]
    for team in retire:
        Team.objects.filter(pk=team.pk).update(participation_status='withdrawn')

    teams = []
    for index, team in enumerate(keep, start=1):
        username = f'crv208_student_{index}'
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={'role': 'student', 'email': f'{username}@example.invalid'})
        User.objects.filter(pk=user.pk).update(
            password_hash=hashed, role='student', team_id=team.id)
        Enrollment.objects.update_or_create(
            user_id=user.user_id, section=section,
            defaults={'team_id': team.id, 'is_active': True,
                      'enrolled_at': timezone.now()})
        teams.append({'id': team.id, 'name': team.name, 'student': username,
                      'user_id': user.user_id})

    instructor, _ = User.objects.get_or_create(
        username='crv208_instructor',
        defaults={'role': 'instructor', 'email': 'inst@example.invalid'})
    User.objects.filter(pk=instructor.pk).update(
        password_hash=hashed, role='instructor')

    return {'game_id': game.id, 'section_id': section.section_id,
            'scenario': chosen.name, 'teams': teams,
            'instructor': 'crv208_instructor',
            'withdrawn_teams': [t.name for t in retire]}


def describe(game):
    """What the walkthrough needs to address the game, and what it contains."""
    from core.models import (DecisionAuditEvent, DecisionSubmission,
                             OperatorAuditEvent, ResolutionManifest, Round, Team)
    from core.models.audit_integrity import SensitiveReadEvent
    from core.models.results_financials import RoundResultFinancials

    rounds = list(Round.objects.filter(game=game).order_by('round_number')
                  .values('round_number', 'status', 'deadline', 'closed_at',
                          'processed_at', 'close_reason'))
    return {
        'game_id': game.id,
        'game_status': game.status,
        'current_round': game.current_round,
        'rounds': rounds,
        'summary': {
            'teams_active': Team.objects.filter(
                game=game, participation_status='active').count(),
            'rounds_processed': sum(1 for r in rounds if r['status'] == 'processed'),
            'submissions': DecisionSubmission.objects.filter(
                round__game=game).count(),
            'decision_audit_events': DecisionAuditEvent.objects.filter(
                game=game).count(),
            'operator_audit_events': OperatorAuditEvent.objects.filter(
                game=game).count(),
            'resolution_manifests': ResolutionManifest.objects.filter(
                game=game).count(),
            'financial_rows': RoundResultFinancials.objects.filter(
                game=game).count(),
            'sensitive_read_events': SensitiveReadEvent.objects.filter(
                game_id_read=game.id).count(),
        },
    }


def complete_submission(game, team_id, round_number):
    """Fill everything the lock validator requires beyond the budget.

    The budget saves are driven through the API because they are the evidence
    the disputes are answered from -- the audit rows, their payload hashes and
    their server timestamps. The rest of a valid submission is fixture bulk:
    a product portfolio, a marketing mix for every active product-market pair,
    a strategy mix, and any mandatory communication the round triggered. Those
    are written here so the lock endpoint has a complete submission to accept
    or refuse on its own terms.
    """
    import baseline as BASE
    from django.utils import timezone
    from core.models import DecisionSubmission, Round, Team
    from core.models.cc32_models import CommunicationAssignment, TeamCommunication

    team = Team.objects.get(id=team_id)
    rnd = Round.objects.get(game=game, round_number=round_number)
    submission, _ = DecisionSubmission.objects.get_or_create(
        team=team, round=rnd, defaults={'status': 'draft'})
    BASE.build(submission, team)
    optional = BASE.build_optional(submission, team)

    for assignment in CommunicationAssignment.objects.filter(scenario=game.scenario):
        TeamCommunication.objects.update_or_create(
            game=game, team=team, round=rnd, assignment=assignment,
            defaults={'content': 'Seeded for the CRV2-08 walkthrough.',
                      'word_count': 6, 'is_draft': False,
                      'submitted_at': timezone.now()})
    return {'team': team.name, 'round': round_number,
            'optional_built': sorted(k for k, v in optional.items()
                                     if v.get('built'))}
