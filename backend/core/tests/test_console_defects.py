"""
Regression tests for the instructor console defects found on 2026-07-15 by
exercising the endpoints rather than reading them.

The delete-cascade test is the important one: deleting a game only failed once
the game had results, so every casual test passed. A brand-new game deleted
fine; one that had actually run a round did not.
"""
from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.utils import timezone

from core.models import Game, Round, Team
from core.models.course import Course, Section, SimulationInstance
from core.models.results_financials import RoundResultProductMarket
from core.models.scenario import (
    FirmStarterProfile, MarketDefinition, PlatformGenerationDefinition, Scenario,
)
from core.models.team_state import TeamPlatform, TeamProduct
from core.views.course import _game_ids_for_section
from core.views.scenario_views import _delete_game_cascade


class _Fixture(TestCase):

    def setUp(self):
        self.owner = DjangoUser.objects.create(username='owner')
        self.scenario = Scenario.objects.create(
            name='S', industry_label='Test', description='d',
            starting_cash=1000, num_rounds=3,
        )
        self.market = MarketDefinition.objects.create(
            scenario=self.scenario, name='Home', code='HM', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1,
        )
        self.profile = FirmStarterProfile.objects.create(
            scenario=self.scenario, profile_name='P', description='d',
            home_market=self.market,
        )
        self.game = Game.objects.create(
            scenario=self.scenario, name='G', status='active',
            current_round=1, created_by=self.owner,
        )
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now(),
        )
        self.team = Team.objects.create(
            game=self.game, name='T1', firm_starter_profile=self.profile,
            performance_index=100, cash_on_hand=1000, total_equity=1000,
            home_market=self.market,
        )

    def _make_product(self):
        generation = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Gen1', description='d',
            generation_order=1, development_cost=0, license_cost=0,
        )
        platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=generation, status='active',
        )
        return TeamProduct.objects.create(
            team=self.team, team_platform=platform, name='P1',
            positioning='mainstream', created_round=1,
        )


class DeleteGameCascadeTests(_Fixture):
    """A game must stay deletable once it has produced results."""

    def test_delete_game_with_no_results(self):
        """The easy case. This always worked, which is what hid the bug."""
        gid = self.game.id
        _delete_game_cascade(self.game)
        self.assertFalse(Game.objects.filter(id=gid).exists())

    def test_delete_game_that_has_results(self):
        """
        The real case. TeamProduct is PROTECTed by
        RoundResultProductMarket.team_product, and the cascade deleted team
        state before those results, so this raised ProtectedError. The view is
        atomic, so the whole delete rolled back and the game silently survived.
        """
        product = self._make_product()
        RoundResultProductMarket.objects.create(
            game=self.game, team=self.team, round_number=1,
            team_product=product, market=self.market,
        )

        gid, pid = self.game.id, product.id
        _delete_game_cascade(self.game)

        self.assertFalse(Game.objects.filter(id=gid).exists())
        self.assertFalse(Team.objects.filter(game_id=gid).exists())
        self.assertFalse(TeamProduct.objects.filter(id=pid).exists())
        self.assertFalse(
            RoundResultProductMarket.objects.filter(game_id=gid).exists())


class SectionToGameLinkageTests(_Fixture):
    """A section reaches its game two ways; both must be honoured."""

    def setUp(self):
        super().setUp()
        self.course = Course.objects.create(
            course_code='C1', course_name='Course', is_active=True,
        )
        self.section = Section.objects.create(
            course=self.course, section_code='S1', is_active=True,
        )

    def test_resolves_game_via_game_section_id(self):
        self.game.section_id = self.section.section_id
        self.game.save()
        self.assertIn(self.game.id,
                      _game_ids_for_section(self.section.section_id))

    def test_resolves_game_via_simulation_instance(self):
        """
        The demo section is linked ONLY this way — its Game.section_id is NULL.
        Checking game__section_id alone reported zero teams where five existed.
        """
        SimulationInstance.objects.create(
            section=self.section, game_id=self.game.id,
        )
        self.assertIsNone(self.game.section_id)
        self.assertIn(self.game.id,
                      _game_ids_for_section(self.section.section_id))

    def test_no_duplicate_when_both_links_present(self):
        self.game.section_id = self.section.section_id
        self.game.save()
        SimulationInstance.objects.create(
            section=self.section, game_id=self.game.id,
        )
        ids = _game_ids_for_section(self.section.section_id)
        self.assertEqual(ids.count(self.game.id), 1)

    def test_unrelated_section_resolves_to_nothing(self):
        self.assertEqual(_game_ids_for_section(99999), [])


class TeamFieldTests(_Fixture):
    """Team.team_id / team_name are read-only properties, not fields."""

    def test_team_id_and_name_are_not_fields(self):
        field_names = {f.name for f in Team._meta.get_fields()}
        self.assertNotIn('team_name', field_names)
        self.assertNotIn('team_id', field_names)
        self.assertIn('name', field_names)

    def test_properties_still_read(self):
        """They read fine — which is why some call sites appeared to work."""
        self.assertEqual(self.team.team_name, self.team.name)
        self.assertEqual(self.team.team_id, self.team.id)

    def test_rename_via_the_real_field(self):
        team = Team.objects.get(id=self.team.id)
        team.name = 'Renamed'
        team.save(update_fields=['name'])
        self.assertEqual(Team.objects.get(id=self.team.id).name, 'Renamed')
