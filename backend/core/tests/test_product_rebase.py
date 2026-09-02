"""Re-basing a product, and the history that keeps past rounds reconstructable.

Stage 4. The feature is small; the trap it opens is not. BECSR recorded it as
defect B: its demand side resolved platforms as of the round while its supply
side resolved them as of now, so a re-based program's demand reconciled to
nothing — no sale, no lost sale, no inventory row and no error, because the
standing `demand - sold - lost == 0` check summed only rows that existed. It
measured zero units purely because no cohort had used the feature.

GlobalStrat's shape was different and, for determinism, worse: every consumer
read one live pointer, so a switch would have silently re-resolved rounds
already scored and published — the boundary GSP-CRV2-01 certified.
"""
import ast
import pathlib
from decimal import Decimal as D

from django.test import SimpleTestCase, TestCase

from core.models import DecisionSubmission, Round
from core.models.results_financials import RoundResultProductMarket
from core.models.scenario import (FeatureDefinition, FeatureLevelCost,
                                  MarketDefinition, PlatformFeatureCeiling,
                                  PlatformGenerationDefinition, ScenarioConfig)
from core.models.team_state import (TeamPlatform, TeamPlatformFeatureLevel,
                                    TeamProduct, TeamProductPlatformHistory)
from core.services import product_platform, product_rebase
from core.tests.test_operator_concurrency import build_minimal_game


class RebaseFixture(TestCase):

    def setUp(self):
        self.game, self.teams = build_minimal_game(f'rebase-{id(self)}')
        self.team = self.teams[0]
        self.other_team = self.teams[1]
        self.scenario = self.game.scenario
        self.market = MarketDefinition.objects.filter(
            scenario=self.scenario).first()

        self.old_gen = self.generation(1)
        self.new_gen = self.generation(2)
        self.old_platform = self.platform(self.old_gen, 'Old Platform')
        self.new_platform = self.platform(self.new_gen, 'New Platform')

        self.feature = FeatureDefinition.objects.create(
            scenario=self.scenario, code='REB', name='Rebase feature',
            description='d', layer='platform', category='core',
            cost_curve_type='linear', cost_base=D('1000'))
        # The two platforms differ on the feature, so a round resolving to the
        # wrong one is visible rather than coincidentally equal.
        TeamPlatformFeatureLevel.objects.create(
            team_platform=self.old_platform, feature=self.feature,
            current_level=D('3'))
        TeamPlatformFeatureLevel.objects.create(
            team_platform=self.new_platform, feature=self.feature,
            current_level=D('9'))

        self.product = TeamProduct.objects.create(
            team=self.team, team_platform=self.old_platform,
            name='Aurora', positioning='mainstream', status='active',
            created_round=1)

    def generation(self, order):
        return PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name=f'Gen {order}', description='d',
            generation_order=order, unlock_round=0,
            development_cost=D('1000000'), license_cost=D('2000000'),
            development_rounds=1)

    def platform(self, generation, name, team=None, status='active'):
        return TeamPlatform.objects.create(
            team=team or self.team, platform_generation=generation, name=name,
            status=status, development_method='in_house',
            development_started_round=0, funded_round=0,
            development_rounds_remaining=0)

    def stock(self, round_number, unsold, unit_cost):
        return RoundResultProductMarket.objects.create(
            game=self.game, round_number=round_number, team=self.team,
            team_product=self.product, market=self.market,
            units_produced=int(D(str(unsold))), units_sold=D('0'),
            units_unsold=D(str(unsold)), unit_cost=D(str(unit_cost)))


class RebaseRefusalTests(RebaseFixture):
    """Fail-closed: ownership, readiness, and the no-op switch."""

    def test_another_teams_platform_is_refused(self):
        theirs = self.platform(self.new_gen, 'Theirs', team=self.other_team)
        with self.assertRaises(product_rebase.RebaseRefused) as caught:
            product_rebase.rebase(self.product, theirs, self.team, 2)
        self.assertIn('belongs to another team', str(caught.exception))
        self.product.refresh_from_db()
        self.assertEqual(self.product.team_platform_id, self.old_platform.id)
        self.assertEqual(TeamProductPlatformHistory.objects.count(), 0)

    def test_a_platform_still_in_development_is_refused(self):
        building = self.platform(self.new_gen, 'Building',
                                 status='in_development')
        with self.assertRaises(product_rebase.RebaseRefused) as caught:
            product_rebase.rebase(self.product, building, self.team, 2)
        self.assertIn('only be re-based onto a ready platform',
                      str(caught.exception))
        self.assertEqual(TeamProductPlatformHistory.objects.count(), 0)

    def test_an_unfunded_draft_is_refused(self):
        draft = self.platform(self.new_gen, 'Draft', status='unfunded_draft')
        with self.assertRaises(product_rebase.RebaseRefused):
            product_rebase.rebase(self.product, draft, self.team, 2)

    def test_another_teams_product_is_refused(self):
        theirs = TeamProduct.objects.create(
            team=self.other_team, team_platform=self.old_platform,
            name='Not mine', positioning='mainstream', status='active',
            created_round=1)
        with self.assertRaises(product_rebase.RebaseRefused) as caught:
            product_rebase.rebase(theirs, self.new_platform, self.team, 2)
        self.assertIn('belongs to another team', str(caught.exception))

    def test_re_basing_onto_the_current_platform_is_refused(self):
        with self.assertRaises(product_rebase.RebaseRefused) as caught:
            product_rebase.rebase(self.product, self.old_platform, self.team, 2)
        self.assertIn('already based on', str(caught.exception))

    def test_a_refusal_charges_nothing_and_writes_no_history(self):
        self.stock(1, unsold=100, unit_cost=50)
        theirs = self.platform(self.new_gen, 'Theirs', team=self.other_team)
        with self.assertRaises(product_rebase.RebaseRefused):
            product_rebase.rebase(self.product, theirs, self.team, 2)
        self.assertEqual(TeamProductPlatformHistory.objects.count(), 0)
        self.assertEqual(
            product_rebase.write_offs_for_round(self.team, 2), D('0'))


class RebaseWriteOffTests(RebaseFixture):
    """Authoritative and exactly once."""

    def test_the_write_off_is_the_authored_percentage_of_stock(self):
        ScenarioConfig.objects.create(
            scenario=self.scenario, config_key='platform_switch_write_off_pct',
            config_value='0.15', description='Stage 4')
        self.stock(1, unsold=100, unit_cost=50)
        result = product_rebase.rebase(self.product, self.new_platform,
                                       self.team, 2)
        self.assertEqual(D(result['units_written_off']), D('100'))
        self.assertEqual(D(result['write_off']), D('750.00'))   # 100*50*0.15

    def test_the_percentage_comes_from_the_scenario(self):
        ScenarioConfig.objects.create(
            scenario=self.scenario, config_key='platform_switch_write_off_pct',
            config_value='0.40', description='Stage 4')
        from core.engine import utils as engine_utils
        engine_utils._config_cache.pop(self.scenario.id, None)
        self.stock(1, unsold=100, unit_cost=50)
        result = product_rebase.rebase(self.product, self.new_platform,
                                       self.team, 2)
        self.assertEqual(D(result['write_off']), D('2000.00'))

    def test_no_stock_costs_nothing(self):
        result = product_rebase.rebase(self.product, self.new_platform,
                                       self.team, 2)
        self.assertEqual(D(result['units_written_off']), D('0'))
        self.assertEqual(D(result['write_off']), D('0'))

    def test_only_the_latest_closing_position_is_written_off(self):
        """Summing older rows would write off stock sold rounds ago."""
        self.stock(1, unsold=500, unit_cost=50)
        self.stock(2, unsold=100, unit_cost=50)
        result = product_rebase.rebase(self.product, self.new_platform,
                                       self.team, 2)
        self.assertEqual(D(result['units_written_off']), D('100'))

    def test_the_charge_is_read_once_from_the_history_row(self):
        self.stock(1, unsold=100, unit_cost=50)
        product_rebase.rebase(self.product, self.new_platform, self.team, 2)
        self.assertEqual(product_rebase.write_offs_for_round(self.team, 2),
                         D('750.00'))
        # Not charged again in a later round.
        self.assertEqual(product_rebase.write_offs_for_round(self.team, 3),
                         D('0'))

    def test_a_second_switch_in_one_round_updates_rather_than_adds(self):
        third_gen = self.generation(3)
        third = self.platform(third_gen, 'Third Platform')
        self.stock(1, unsold=100, unit_cost=50)
        product_rebase.rebase(self.product, self.new_platform, self.team, 2)
        product_rebase.rebase(self.product, third, self.team, 2)
        rows = TeamProductPlatformHistory.objects.filter(
            team_product=self.product, effective_from_round=2)
        self.assertEqual(rows.count(), 1, 'a second switch added a second row')
        self.assertEqual(rows.first().team_platform_id, third.id)


class RebaseHistoryTests(RebaseFixture):
    """Atomic switch, seeded history, and round-correct resolution."""

    def test_the_prior_association_is_seeded_on_the_first_switch(self):
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        rows = list(TeamProductPlatformHistory.objects
                    .filter(team_product=self.product)
                    .order_by('effective_from_round')
                    .values_list('effective_from_round', 'team_platform_id'))
        self.assertEqual(rows, [(1, self.old_platform.id),
                                (4, self.new_platform.id)])

    def test_earlier_rounds_still_resolve_to_the_old_platform(self):
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        for round_number in (1, 2, 3):
            self.assertEqual(
                product_platform.platform_as_of_round(
                    self.product, round_number).id,
                self.old_platform.id,
                f'round {round_number} re-attributed to the new platform')
        for round_number in (4, 5):
            self.assertEqual(
                product_platform.platform_as_of_round(
                    self.product, round_number).id,
                self.new_platform.id)

    def test_the_batched_resolution_agrees_with_the_single_one(self):
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        for round_number in (1, 3, 4, 6):
            batched = product_platform.platform_ids_as_of_round(
                [self.product], round_number)[self.product.id]
            single = product_platform.platform_as_of_round(
                self.product, round_number).id
            self.assertEqual(batched, single,
                             f'batched and single disagree in round {round_number}')

    def test_the_live_pointer_moves_with_the_switch(self):
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        self.product.refresh_from_db()
        self.assertEqual(self.product.team_platform_id, self.new_platform.id)

    def test_a_product_without_history_resolves_to_its_pointer(self):
        for round_number in (0, 1, 9):
            self.assertEqual(
                product_platform.platform_as_of_round(
                    self.product, round_number).id, self.old_platform.id)


class MissingResolutionTests(RebaseFixture):
    """The check that fails on an absent row rather than summing present ones."""

    def test_a_healthy_game_reports_nothing(self):
        self.assertEqual(
            product_platform.missing_platform_resolutions(self.game, 1), [])

    def test_a_product_resolving_to_another_teams_platform_is_named(self):
        theirs = self.platform(self.new_gen, 'Theirs', team=self.other_team)
        product_platform.record_association(self.product, theirs, 1)
        problems = product_platform.missing_platform_resolutions(self.game, 1)
        self.assertEqual(len(problems), 1)
        self.assertIn('owned by another team', problems[0]['detail'])
        self.assertIn('Aurora',
                      product_platform.describe_missing_resolutions(problems))

    def test_the_check_reads_the_round_it_is_asked_about(self):
        theirs = self.platform(self.new_gen, 'Theirs', team=self.other_team)
        product_platform.record_association(self.product, self.old_platform, 1)
        product_platform.record_association(self.product, theirs, 5)
        self.assertEqual(
            product_platform.missing_platform_resolutions(self.game, 1), [])
        self.assertEqual(
            len(product_platform.missing_platform_resolutions(self.game, 5)), 1)


class SwitchThenReplayTests(RebaseFixture):
    """A round scored before a switch must replay to the same answer.

    This is the GSP-CRV2-01 boundary. Before Stage 4 every consumer read
    `TeamProduct.team_platform`, a single live pointer, so re-basing would have
    changed what an already-resolved round resolved to -- a different feature
    level, a different fit score, a different competitive hash for a round the
    cohort had already been shown.

    The engine now resolves through `resolved_platform`, so these tests ask the
    resolution question the way the engine asks it, before and after a switch.
    """

    def resolve_via_engine(self, round_number):
        """What the engine's own helper answers for this round."""
        from core.engine.utils import resolved_platform
        return resolved_platform(self.product, round_number).id

    def feature_level_seen(self, round_number):
        """The platform feature level the demand side would score with."""
        from core.engine.preference_engine import _get_platform_value
        return _get_platform_value(self.team, self.product, self.feature,
                                   round_number)

    def test_the_engine_helper_resolves_as_of_the_round(self):
        before = {r: self.resolve_via_engine(r) for r in (1, 2, 3)}
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        after = {r: self.resolve_via_engine(r) for r in (1, 2, 3)}
        self.assertEqual(before, after,
                         'a resolved round changed platform after a switch')
        self.assertEqual(self.resolve_via_engine(4), self.new_platform.id)

    def test_the_feature_level_a_past_round_scored_with_is_unchanged(self):
        """The value that actually feeds the fit score, not just the FK."""
        before = {r: self.feature_level_seen(r) for r in (1, 2, 3)}
        self.assertEqual(set(before.values()), {3.0},
                         'fixture did not score on the old platform')
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        after = {r: self.feature_level_seen(r) for r in (1, 2, 3)}
        self.assertEqual(before, after,
                         'a past round would now score on the new platform')
        self.assertEqual(self.feature_level_seen(4), 9.0,
                         'the switch round did not pick up the new platform')

    def test_demand_and_supply_resolve_identically(self):
        """Defect B in one assertion: the two sides cannot disagree."""
        from core.engine.utils import resolved_platform
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        for round_number in (1, 2, 3, 4, 5):
            demand_side = resolved_platform(self.product, round_number).id
            supply_side = product_platform.platform_ids_as_of_round(
                [self.product], round_number)[self.product.id]
            self.assertEqual(demand_side, supply_side,
                             f'demand and supply disagree in round {round_number}')

    def test_a_switch_does_not_disturb_an_unswitched_product(self):
        other = TeamProduct.objects.create(
            team=self.team, team_platform=self.old_platform, name='Steady',
            positioning='mainstream', status='active', created_round=1)
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)
        for round_number in (1, 4, 6):
            self.assertEqual(
                product_platform.platform_as_of_round(other, round_number).id,
                self.old_platform.id,
                'an unswitched product moved with another product\'s switch')


class RebaseEndpointTests(RebaseFixture):
    """The supported write surface for the switch.

    The service is proved above; what these add is that a team can actually
    reach it, that its refusals arrive as refusals rather than 500s, and that
    a refused call leaves nothing behind.
    """

    def setUp(self):
        super().setUp()
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        self.student = User.objects.create(
            username=f'rebase-student-{id(self)}', role='student',
            password_hash='x')
        course = Course.objects.create(
            course_code=f'REB{id(self) % 100000}', course_name='Rebase',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=self.student.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True)
        Round.objects.update_or_create(
            game=self.game, round_number=self.game.current_round,
            defaults={'status': 'open'})

    def client_as_student(self):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.student)}')
        return client

    def url(self, product=None):
        product = product or self.product
        return (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/products/{product.id}/rebase/')

    def test_a_team_can_switch_its_product_through_the_api(self):
        response = self.client_as_student().post(
            self.url(), {'team_platform': self.new_platform.id},
            format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['to_platform'], self.new_platform.id)
        self.assertEqual(response.data['from_platform'],
                         self.old_platform.id)
        self.product.refresh_from_db()
        self.assertEqual(self.product.team_platform_id, self.new_platform.id)

    def test_the_switch_is_recorded_as_history_not_only_a_pointer_move(self):
        round_number = self.game.current_round
        self.client_as_student().post(
            self.url(), {'team_platform': self.new_platform.id},
            format='json')

        row = TeamProductPlatformHistory.objects.get(
            team_product=self.product, effective_from_round=round_number)
        self.assertEqual(row.team_platform_id, self.new_platform.id)

    def test_another_teams_platform_is_refused_with_400_not_500(self):
        foreign = self.platform(self.new_gen, 'Theirs',
                                team=self.other_team)
        response = self.client_as_student().post(
            self.url(), {'team_platform': foreign.id}, format='json')

        self.assertEqual(response.status_code, 400)
        # The endpoint resolves the platform *through* the team, so a rival's
        # id is simply not found. It deliberately does not answer "that one
        # exists but is not yours", which would turn the route into an
        # enumeration oracle for rivals' platform ids. The service still
        # distinguishes the two for its own callers -- see
        # RebaseRefusalTests.test_another_teams_platform_is_refused.
        self.assertIn('No such platform', response.data['detail'])

    def test_a_refused_call_moves_nothing(self):
        foreign = self.platform(self.new_gen, 'Theirs',
                                team=self.other_team)
        self.client_as_student().post(
            self.url(), {'team_platform': foreign.id}, format='json')

        self.product.refresh_from_db()
        self.assertEqual(self.product.team_platform_id, self.old_platform.id)
        self.assertFalse(TeamProductPlatformHistory.objects.filter(
            team_product=self.product).exists())

    def test_an_unknown_platform_is_refused_rather_than_crashing(self):
        response = self.client_as_student().post(
            self.url(), {'team_platform': 9_999_999}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('No such platform', response.data['detail'])

    def test_the_switch_is_written_to_the_decision_audit_trail(self):
        from core.models.competition_audit import DecisionAuditEvent
        self.client_as_student().post(
            self.url(), {'team_platform': self.new_platform.id},
            format='json')

        event = DecisionAuditEvent.objects.filter(
            team=self.team, action='rebase').first()
        self.assertIsNotNone(event)
        self.assertEqual(event.payload['to_platform'], self.new_platform.id)

    def rival_client(self):
        """A student enrolled on the *other* team in the same game."""
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        rival = User.objects.create(
            username=f'rebase-rival-{id(self)}', role='student',
            password_hash='x')
        course = Course.objects.create(
            course_code=f'RIV{id(self) % 100000}', course_name='Rival',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=rival.user_id, section_id=section.section_id,
            team_id=self.other_team.id, is_active=True)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(rival)}')
        return client

    def test_a_rival_cannot_re_base_another_teams_product(self):
        response = self.rival_client().post(
            self.url(), {'team_platform': self.new_platform.id},
            format='json')

        # Refused by the shared scope-guard middleware, which returns a
        # plain JsonResponse rather than a DRF response -- the new route
        # inherits the CRV2-08 default-deny boundary without opting in.
        self.assertEqual(response.status_code, 403, response.content)

    def test_a_rivals_attempt_moves_nothing(self):
        self.rival_client().post(
            self.url(), {'team_platform': self.new_platform.id},
            format='json')

        self.product.refresh_from_db()
        self.assertEqual(self.product.team_platform_id, self.old_platform.id)
        self.assertFalse(TeamProductPlatformHistory.objects.filter(
            team_product=self.product).exists())


class PlatformConsumerGuardTests(SimpleTestCase):
    """Static inventory of every way resolution code can reach a platform.

    The Stage 4 inventory looked for direct attribute reads and calls to
    `resolved_platform`, so it saw neither of the two forms that actually
    matter here. A queryset can reach the live pointer through a relationship
    traversal -- `team_product__team_platform=<round-resolved platform>` -- and
    that comparison is guaranteed to fail after a re-base rather than to
    return the wrong row, which is why it emptied a historical sum instead of
    raising anything (V2-050).
    """

    ENGINE_ROOT = pathlib.Path(__file__).resolve().parent.parent / 'engine'
    SERVICES_ROOT = pathlib.Path(__file__).resolve().parent.parent / 'services'
    RESOLUTION_SERVICES = ('funding_need.py', 'product_platform.py',
                           'product_rebase.py', 'rd_costs.py',
                           'resolution_manifest.py')

    # Decision rows carry their own platform choice; that is the row's data,
    # not a product's round-varying association.
    DECISION_ROW_NAMES = {'investment', 'pg', 'create_dec', 'dec', 'row'}

    def _sources(self):
        for path in sorted(self.ENGINE_ROOT.rglob('*.py')):
            if '__pycache__' in str(path) or 'tests' in path.parts:
                continue
            yield path
        for name in self.RESOLUTION_SERVICES:
            yield self.SERVICES_ROOT / name

    def test_no_queryset_traverses_a_relationship_to_the_live_platform(self):
        offenders = []
        for path in self._sources():
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                for kw in node.keywords:
                    if kw.arg and '__team_platform' in kw.arg:
                        offenders.append(
                            f'{path.name}:{node.lineno} {kw.arg}=...')
        self.assertFalse(offenders, (
            'These filter through a product\'s live platform foreign key. '
            'Resolve each row as of its own round instead:\n'
            + '\n'.join(offenders)))

    def test_no_product_reads_its_platform_pointer_directly(self):
        offenders = []
        for path in self._sources():
            # The two modules that own the association itself: one resolves
            # it, the other moves it. Everything else must go through them.
            if path.name in ('product_platform.py', 'product_rebase.py'):
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Attribute):
                    continue
                if node.attr not in ('team_platform', 'team_platform_id'):
                    continue
                base = node.value
                if not isinstance(base, ast.Name):
                    continue
                if base.id in self.DECISION_ROW_NAMES:
                    continue
                if 'product' not in base.id and base.id not in ('p', 'prod'):
                    continue
                offenders.append(
                    f'{path.name}:{node.lineno} {base.id}.{node.attr}')
        self.assertFalse(offenders, (
            'Read the platform as of the round being scored, via '
            'resolved_platform()/platform_as_of_round():\n'
            + '\n'.join(offenders)))


class RebaseGameBindingTests(RebaseFixture):
    """One game's URL must not reach another game's team.

    Neither shared guard supplies this relationship. The student guard proves
    membership in the URL *team* but not that the team is in the URL *game*;
    the instructor guard proves ownership of the URL *game* while `IsTeamMember`
    exempts instructors entirely. So a route that resolves the team by global
    primary key is unprotected in both directions (V2-051).
    """

    def setUp(self):
        super().setUp()
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        from core.tests.test_operator_concurrency import build_minimal_game

        # A second, unrelated game with its own owner.
        self.other_game, other_teams = build_minimal_game(f'bind-{id(self)}')
        self.foreign_team = other_teams[0]
        foreign_gen = PlatformGenerationDefinition.objects.create(
            scenario=self.other_game.scenario, name='Foreign Gen',
            description='d', generation_order=1, unlock_round=0,
            development_cost=D('1000000'), license_cost=D('2000000'),
            development_rounds=1)
        self.foreign_platform = TeamPlatform.objects.create(
            team=self.foreign_team, platform_generation=foreign_gen,
            name='Foreign Platform', status='active',
            development_method='in_house', development_started_round=0,
            funded_round=0, development_rounds_remaining=0)

        self.student = User.objects.create(
            username=f'bind-student-{id(self)}', role='student',
            password_hash='x')
        course = Course.objects.create(
            course_code=f'BND{id(self) % 100000}', course_name='Bind',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=self.student.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True)
        Round.objects.update_or_create(
            game=self.game, round_number=self.game.current_round,
            defaults={'status': 'open'})
        Round.objects.update_or_create(
            game=self.other_game,
            round_number=self.other_game.current_round,
            defaults={'status': 'open'})

    def client_as(self, user):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
        return client

    def instructor_owning(self, game):
        """An instructor who owns `game` and nothing else.

        Ownership runs game -> section -> course.instructor_id, so the cohort
        has to be built for the guard to see the instructor as the owner.
        """
        from core.models import User
        from core.models.course import Course, Section
        user = User.objects.create(
            username=f'bind-instr-{game.id}-{id(self)}', role='instructor',
            password_hash='x')
        course = Course.objects.create(
            course_code=f'OWN{game.id}{id(self) % 10000}',
            course_name='Owned', instructor_id=user.user_id, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        game.section_id = section.section_id
        game.save(update_fields=['section_id'])
        return user

    def unchanged(self):
        """The state a refused call must leave exactly as it found it."""
        self.product.refresh_from_db()
        return (self.product.team_platform_id,
                TeamProductPlatformHistory.objects.filter(
                    team_product=self.product).count())

    # -- the student direction ---------------------------------------------

    def test_a_student_cannot_route_their_own_team_through_another_game(self):
        before = self.unchanged()
        response = self.client_as(self.student).post(
            f'/api/games/{self.other_game.id}/teams/{self.team.id}'
            f'/products/{self.product.id}/rebase/',
            {'team_platform': self.new_platform.id}, format='json')

        self.assertIn(response.status_code, (403, 404))
        self.assertEqual(self.unchanged(), before)

    # -- the instructor direction ------------------------------------------

    def test_an_instructor_cannot_reach_another_game_through_their_own(self):
        """The case `IsTeamMember` cannot catch, because it exempts them."""
        instructor = self.instructor_owning(self.game)
        foreign_product = TeamProduct.objects.create(
            team=self.foreign_team, team_platform=self.foreign_platform,
            name='Theirs',
            positioning='mainstream', status='active', created_round=1)
        before_platform = foreign_product.team_platform_id

        response = self.client_as(instructor).post(
            f'/api/games/{self.game.id}/teams/{self.foreign_team.id}'
            f'/products/{foreign_product.id}/rebase/',
            {'team_platform': self.new_platform.id}, format='json')

        self.assertIn(response.status_code, (403, 404))
        foreign_product.refresh_from_db()
        self.assertEqual(foreign_product.team_platform_id, before_platform)
        self.assertFalse(TeamProductPlatformHistory.objects.filter(
            team_product=foreign_product).exists())

    def test_no_decision_audit_row_is_written_for_a_refused_cross_game_call(self):
        from core.models.competition_audit import DecisionAuditEvent
        instructor = self.instructor_owning(self.game)
        foreign_product = TeamProduct.objects.create(
            team=self.foreign_team, team_platform=self.foreign_platform,
            name='Theirs2',
            positioning='mainstream', status='active', created_round=1)

        self.client_as(instructor).post(
            f'/api/games/{self.game.id}/teams/{self.foreign_team.id}'
            f'/products/{foreign_product.id}/rebase/',
            {'team_platform': self.new_platform.id}, format='json')

        self.assertFalse(
            DecisionAuditEvent.objects.filter(action='rebase').exists(),
            'A refused cross-game call must not leave a successful decision '
            'audit row, least of all one attributed to the wrong game.')

    def test_a_cross_game_attempt_is_recorded_as_a_refusal(self):
        """Neither guard reaches this, so without a record it is invisible."""
        from core.models import AuthorizationRefusalEvent
        instructor = self.instructor_owning(self.game)
        foreign_product = TeamProduct.objects.create(
            team=self.foreign_team, team_platform=self.foreign_platform,
            name='Theirs3',
            positioning='mainstream', status='active', created_round=1)

        self.client_as(instructor).post(
            f'/api/games/{self.game.id}/teams/{self.foreign_team.id}'
            f'/products/{foreign_product.id}/rebase/',
            {'team_platform': self.new_platform.id}, format='json')

        event = AuthorizationRefusalEvent.objects.filter(
            reason='Team belongs to another game').first()
        self.assertIsNotNone(event)
        self.assertEqual(event.actor_user_id, instructor.user_id)
        self.assertEqual(event.game_id_attempted, self.game.id)
        self.assertEqual(event.outcome, 'rejected')
        self.assertEqual(event.method, 'POST')

    def test_an_unknown_team_records_nothing(self):
        """Only a real team in another game is a cross-cohort attempt."""
        from core.models import AuthorizationRefusalEvent
        self.client_as(self.student).post(
            f'/api/games/{self.game.id}/teams/99999999'
            f'/products/{self.product.id}/rebase/',
            {'team_platform': self.new_platform.id}, format='json')

        self.assertFalse(AuthorizationRefusalEvent.objects.filter(
            reason='Team belongs to another game').exists())

    # -- and the positive control ------------------------------------------

    def test_a_successful_event_has_one_coherent_hierarchy(self):
        from core.models.competition_audit import DecisionAuditEvent
        response = self.client_as(self.student).post(
            f'/api/games/{self.game.id}/teams/{self.team.id}'
            f'/products/{self.product.id}/rebase/',
            {'team_platform': self.new_platform.id}, format='json')
        self.assertEqual(response.status_code, 200, response.data)

        event = DecisionAuditEvent.objects.get(action='rebase')
        self.product.refresh_from_db()
        # game -> team -> product -> platform, all one chain.
        self.assertEqual(event.game_id, self.game.id)
        self.assertEqual(event.team_id, self.team.id)
        self.assertEqual(event.team.game_id, event.game_id)
        self.assertEqual(event.round.round_number, self.game.current_round)
        self.assertEqual(event.payload['product'], self.product.id)
        self.assertEqual(self.product.team_id, event.team_id)
        self.assertEqual(event.payload['to_platform'],
                         self.new_platform.id)
        self.assertEqual(self.new_platform.team_id, event.team_id)


class BrandAwarenessReplayTests(RebaseFixture):
    """A later switch must not change what an earlier round scored with.

    The existing replay tests checked the platform id and one platform feature
    level. Brand awareness is reached differently -- a cumulative query over
    historical marketing rows -- and that query filtered on the product's live
    platform foreign key while comparing it against a round-resolved platform.
    After a re-base the two could never agree, so every historical promotion
    row silently dropped out and a past round's awareness fell to zero
    (V2-050). Nothing raised, because an emptied sum is still a number.
    """

    def setUp(self):
        super().setUp()
        from core.models.decisions import DecisionMarketing
        self.rounds = {}
        for n in (1, 2, 3, 4):
            self.rounds[n], _ = Round.objects.get_or_create(
                game=self.game, round_number=n,
                defaults={'status': 'open'})
        # $1,000,000 of promotion spent while the product was on the old
        # platform. Non-zero on purpose: a control that starts at zero cannot
        # tell "correctly zero" from "silently emptied".
        for n in (1, 2, 3):
            submission = DecisionSubmission.objects.create(
                team=self.team, round=self.rounds[n], status='submitted')
            DecisionMarketing.objects.create(
                submission=submission, team_product=self.product,
                market=self.market, retail_price=D('500'),
                promotion_budget=D('1000000'), sales_team_count=0,
                production_volume=100, demand_estimate=100,
                campaign_focus_feature_ids=[],
                channel_digital_pct=D('1.0'),
                channel_traditional_pct=D('0'),
                channel_trade_pct=D('0'),
                distribution_strategy='direct',
                distribution_investment=D('0'),
                production_source_market=self.market)

    def awareness(self, round_number):
        from core.engine.preference_engine import _derive_brand_awareness

        class _Ctx:
            pass
        ctx = _Ctx()
        ctx.game = self.game
        return _derive_brand_awareness(
            ctx, self.team, self.product, self.market, None,
            self.scenario, round_number, 0.0, 1.0)

    def test_a_past_round_keeps_its_awareness_after_a_later_switch(self):
        before = self.awareness(3)
        self.assertGreater(before, 0.0,
                           'The control must start non-zero, or it proves '
                           'nothing about a value falling to zero.')

        product_rebase.rebase(self.product, self.new_platform, self.team, 4)

        self.assertEqual(self.awareness(3), before)

    def test_the_spend_follows_the_platform_it_was_spent_on(self):
        """After the switch, the new platform starts from its own history."""
        before = self.awareness(3)
        product_rebase.rebase(self.product, self.new_platform, self.team, 4)

        # Round 4 resolves to the new platform, which carries none of the
        # promotion spent while the product was on the old one.
        self.assertEqual(self.awareness(4), 0.0)
        # And the old platform's rounds are untouched.
        self.assertEqual(self.awareness(3), before)

    def test_an_unswitched_product_is_unaffected(self):
        before = self.awareness(3)
        other = TeamProduct.objects.create(
            team=self.team, team_platform=self.old_platform, name='Steady',
            positioning='mainstream', status='active', created_round=1)
        product_rebase.rebase(other, self.new_platform, self.team, 4)

        self.assertEqual(self.awareness(3), before)
        self.assertEqual(self.awareness(4), before)


class WriteOffAccountingTests(TestCase):
    """The write-off has to reach the team's money, not just a history row.

    Every previous write-off test read the history row back, or read
    `context.opex`. Both were true while the charge was invisible: it was
    computed, stored, put into the opex dict, and then dropped by the statement
    assembly, which enumerated six other opex keys by name. The team paid
    nothing, saw nothing, and was taxed as though the switch had not happened
    (V2-049).

    So these assert from `RoundResultFinancials` -- what the results API and the
    UI actually read -- and never from an intermediate. Each case is a whole
    independent game resolved once, because a resolved round is immutable and
    cannot be re-run to produce a comparison.
    """

    def case(self, switch=True, units='100', unit_cost='50'):
        """Build, optionally switch, resolve, and return the stored row."""
        from core.engine.advance_round import process_round
        from core.models.results_financials import (RoundResultFinancials,
                                                    RoundResultProductMarket)
        from core.tests.test_operator_concurrency import build_minimal_game

        game, teams = build_minimal_game(f'wo-{id(self)}-{switch}-{units}')
        team = teams[0]
        scenario = game.scenario
        market = MarketDefinition.objects.filter(scenario=scenario).first()

        gens = [PlatformGenerationDefinition.objects.create(
            scenario=scenario, name=f'G{n}', generation_order=n,
            development_cost=D('1000000'), license_cost=D('500000'),
            development_rounds=0, unlock_round=0) for n in (1, 2)]
        platforms = [TeamPlatform.objects.create(
            team=team, platform_generation=g, name=f'P{g.generation_order}',
            status='active', development_method='in_house',
            development_started_round=0, funded_round=0,
            development_rounds_remaining=0) for g in gens]

        product = TeamProduct.objects.create(
            team=team, team_platform=platforms[0], name='Aurora',
            positioning='mainstream', status='active', created_round=1)

        # Closing stock from the round *before* the one being resolved, so the
        # snapshot is a prior position rather than a row this round will write.
        RoundResultProductMarket.objects.create(
            game=game, round_number=0, team=team, team_product=product,
            market=market, units_produced=int(D(str(units))),
            units_sold=D('0'), units_unsold=D(str(units)),
            unit_cost=D(str(unit_cost)))

        rnd, _ = Round.objects.get_or_create(
            game=game, round_number=1, defaults={'status': 'closed'})
        Round.objects.filter(pk=rnd.pk).update(status='closed')
        for t in teams:
            DecisionSubmission.objects.update_or_create(
                team=t, round=rnd, defaults={'status': 'locked'})

        written = None
        if switch:
            written = product_rebase.rebase(product, platforms[1], team, 1)

        process_round(game.id)
        financials = RoundResultFinancials.objects.get(
            game=game, team=team, round_number=1)
        return financials, written, game, team

    # -- the line exists, and it is the authored amount ----------------------

    def test_the_write_off_is_stored_as_its_own_line(self):
        financials, written, _game, _team = self.case()

        # 100 x $50 x 15%
        self.assertEqual(D(written['write_off']), D('750.00'))
        self.assertEqual(financials.platform_switch_write_off, D('750.00'))

    def test_no_switch_stores_nothing(self):
        financials, _w, _g, _t = self.case(switch=False)

        self.assertEqual(financials.platform_switch_write_off, D('0'))

    # -- and it changes the money ------------------------------------------

    def test_it_reduces_operating_income_by_exactly_the_write_off(self):
        without, _w, _g, _t = self.case(switch=False)
        with_switch, written, _g2, _t2 = self.case(switch=True)

        self.assertEqual(without.operating_income - with_switch.operating_income,
                         D(written['write_off']))

    def test_it_is_carried_into_net_income_and_cash(self):
        without, _w, _g, _t = self.case(switch=False)
        with_switch, _w2, _g2, _t2 = self.case(switch=True)

        self.assertLess(with_switch.net_income, without.net_income)
        self.assertLess(with_switch.cash_closing, without.cash_closing)

    def test_it_is_deducted_for_tax(self):
        """Taxable profit falls with the charge, like any other opex line."""
        without, _w, game_a, team_a = self.case(switch=False)
        with_switch, _w2, game_b, team_b = self.case(switch=True)

        self.assertLessEqual(with_switch.tax_expense, without.tax_expense)
        self.assertLess(with_switch.pre_tax_income, without.pre_tax_income)

    # -- exactly once -------------------------------------------------------

    def test_a_later_round_is_not_charged_again(self):
        from core.engine.advance_round import process_round
        from core.models.results_financials import RoundResultFinancials
        financials, _w, game, team = self.case()
        self.assertEqual(financials.platform_switch_write_off, D('750.00'))

        rnd2, _ = Round.objects.get_or_create(
            game=game, round_number=2, defaults={'status': 'closed'})
        Round.objects.filter(pk=rnd2.pk).update(status='closed')
        for t in game.teams.all():
            DecisionSubmission.objects.update_or_create(
                team=t, round=rnd2, defaults={'status': 'locked'})
        game.refresh_from_db()
        game.current_round = 2
        game.save(update_fields=['current_round'])
        process_round(game.id)

        second = RoundResultFinancials.objects.get(
            game=game, team=team, round_number=2)
        self.assertEqual(second.platform_switch_write_off, D('0'))

    def test_a_resolved_round_cannot_be_charged_a_second_time(self):
        """Re-running is refused outright, so double-charging has no path."""
        from core.engine.advance_round import process_round
        from core.models.results_financials import RoundResultFinancials
        financials, _w, game, team = self.case()

        with self.assertRaises(Exception):
            process_round(game.id, round_number=1)

        financials.refresh_from_db()
        self.assertEqual(financials.platform_switch_write_off, D('750.00'))
        self.assertEqual(
            RoundResultFinancials.objects.filter(
                game=game, team=team, round_number=1).count(), 1)

    # -- decimal stock is not truncated -------------------------------------

    def test_a_fractional_balance_is_written_off_in_full(self):
        financials, written, _g, _t = self.case(units='100.50')

        # 100.50 x 50 x 15% = 753.75, not the 750.00 an integer cast gives.
        self.assertEqual(D(written['units_written_off']), D('100.50'))
        self.assertEqual(D(written['write_off']), D('753.75'))
        self.assertEqual(financials.platform_switch_write_off, D('753.75'))
