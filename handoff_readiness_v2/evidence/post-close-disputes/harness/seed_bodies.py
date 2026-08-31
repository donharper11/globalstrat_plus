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

    # A game only reaches status 'completed' by advancing past its scenario's
    # final round (advance_round.py:310). The handoff wants a completed game of
    # at least three rounds, not a ten-round playthrough, so this fixture's
    # scenario is three rounds long and the real completion path fires.
    from core.models import Scenario
    Scenario.objects.filter(pk=chosen.pk).update(num_rounds=3)

    # setup_test_game leaves Game.section_id NULL. The instructor portal
    # reaches a game from a section through SimulationInstance.game_id or
    # Game.section_id (course.py:461), so with neither set the section selects
    # but no game loads and the team overview tab -- the whole dispute
    # evidence path -- never appears. A game created through the instructor UI
    # carries its section; this fixture must too, or the walkthrough would be
    # reporting a UI gap that only its own seeding created.
    Game.objects.filter(pk=game.pk).update(section_id=section.section_id)
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

    # The fixture instructor owns the course behind the game's section, which
    # is what a real instructor running their own cohort looks like. Without
    # this the course belongs to setup_test_game's own instructor row and
    # every ownership-scoped endpoint correctly refuses the fixture's
    # instructor -- which is how the missing checks elsewhere were found.
    from core.models.course import Course
    Course.objects.filter(course_id=section.course_id).update(
        instructor_id=instructor.user_id)

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
    # A fixture that does not contain what it claims is worse than no fixture:
    # every later check reads it and reports on something else.
    # Closing a round auto-creates an empty submission for every team that
    # did not submit, so "has no submission row" is the wrong question. The
    # product records the distinction as submission_origin, derived from the
    # audit log, and that is what an instructor actually reads.
    from core.views.results_api import classify_submission_origin
    from core.models.decisions import DecisionSubmission as DS
    origins = {}
    for rnd_obj in Round.objects.filter(game=game, status='processed'):
        for team in Team.objects.filter(game=game, participation_status='active'):
            submission = DS.objects.filter(team=team, round=rnd_obj).first()
            origin = classify_submission_origin(game, team, rnd_obj, submission)
            origins.setdefault(origin, []).append(
                f'{team.name} r{rnd_obj.round_number}')
    defaulted = sorted(origins.get('defaulted_missing', []))
    edit_hashes = list(DecisionAuditEvent.objects
                       .filter(game=game, action='save')
                       .values('team__name', 'round__round_number',
                               'payload_sha256'))
    by_team_round = {}
    for row in edit_hashes:
        key = (row['team__name'], row['round__round_number'])
        by_team_round.setdefault(key, set()).add(row['payload_sha256'])
    edited = sorted(f'{name} r{rnd}' for (name, rnd), hashes
                    in by_team_round.items() if len(hashes) > 1)

    return {
        'game_id': game.id,
        'game_status': game.status,
        'contains': {
            'submission_origins': {k: sorted(v) for k, v in origins.items()},
            'defaulted_missing_team_rounds': defaulted,
            'submissions_saved_more_than_once_with_differing_hashes': edited,
        },
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
    """Fill exactly what the lock validator requires, and nothing else.

    The budget saves are driven through the API because they are the evidence
    the disputes are answered from -- the audit rows, their payload hashes and
    their server timestamps. The rest of a valid submission is fixture bulk,
    written here so the lock endpoint has something complete to judge.

    The adversarial-balance harness's `build_optional` was tried first and is
    wrong for this game. It develops a platform the team already owns, enters a
    market below the entry-mode minimum, and reuses one product name every
    round -- which the lock validator refused twice and which then stalled
    round 2 on the team_product natural key. That last one is V2-029's second
    variant arriving through the ORM, so it is also a live demonstration that
    the manifest backstop still holds where the new write-path check cannot
    reach. Here the fixture simply stops doing it.

    What the validator actually needs: a budget, a product portfolio entry, a
    marketing row per active product-market pair, and one strategy decision.
    """
    import baseline as BASE
    from decimal import Decimal as D
    from django.utils import timezone
    from core.models import DecisionSubmission, Round, Team
    from core.models.cc32_models import CommunicationAssignment, TeamCommunication
    from core.models.decisions import DecisionESG, DecisionProductCreate
    from core.models.team_state import TeamMarketPresence, TeamPlatform

    team = Team.objects.get(id=team_id)
    rnd = Round.objects.get(game=game, round_number=round_number)
    submission, _ = DecisionSubmission.objects.get_or_create(
        team=team, round=rnd, defaults={'status': 'draft'})

    # Budget, talent and a marketing row for every active product-market pair.
    BASE.build(submission, team)

    # Product portfolio: one create, named per team and round so no two rows
    # ever share (team_id, name).
    platform = TeamPlatform.objects.filter(team=team).order_by('id').first()
    markets = list(TeamMarketPresence.objects
                   .filter(team=team, status='active')
                   .values_list('market_id', flat=True))
    DecisionProductCreate.objects.filter(submission=submission).delete()
    if platform and markets:
        DecisionProductCreate.objects.create(
            submission=submission, team_platform=platform,
            product_name=f'{team.name} R{round_number} Line',
            positioning='mainstream', target_market_ids=markets[:1])

    # Strategy: ESG is the one strategy decision with no capital minimum and no
    # scenario prerequisites, so it cannot fail for reasons unrelated to this
    # fixture.
    DecisionESG.objects.update_or_create(
        submission=submission,
        defaults={'environmental_investment': D('50000'),
                  'social_investment': D('25000')})

    for assignment in CommunicationAssignment.objects.filter(scenario=game.scenario):
        TeamCommunication.objects.update_or_create(
            game=game, team=team, round=rnd, assignment=assignment,
            defaults={'content': 'Seeded for the CRV2-08 walkthrough.',
                      'word_count': 6, 'is_draft': False,
                      'submitted_at': timezone.now()})
    return {'team': team.name, 'round': round_number,
            'product': f'{team.name} R{round_number} Line'}
