"""V2-010 and V2-011 — one cohort rule, and one stream per operation.

**V2-010.** `events.py` seeded on `game.section_id or game.id`; `sc_engine` and
`compliance_engine` seeded on `game.id`. Two sections of one class therefore met
the same events and different supply-chain and compliance disruptions, so the
exposure they were scored against differed by construction.

**V2-011.** Both of those engines drew from a *single sequential* RNG across
every team, regime and market. Draw *n* belonged to whichever combination
reached it *n*-th, so adding or withdrawing a team shifted every later draw —
one team's presence decided another team's outcome. Each operation now has its
own stream, keyed by cohort, round, subsystem and the identity of the thing
being decided.
"""
from django.test import SimpleTestCase

from core.engine.rng import get_rng
from core.engine.sc_engine import _cohort_key


class _Game:
    def __init__(self, section_id, id):
        self.section_id = section_id
        self.id = id


class CohortKeyTests(SimpleTestCase):

    def test_every_subsystem_uses_the_same_cohort_rule(self):
        """The rule `events.py` already used, now shared.

        Asserted against the source of the engines that diverged, so this fails
        if either one goes back to seeding on the game.
        """
        import inspect
        from core.engine import compliance_engine, events, sc_engine

        self.assertIn('game.section_id or game.id',
                      inspect.getsource(sc_engine._cohort_key))
        for module in (sc_engine, compliance_engine):
            source = inspect.getsource(module)
            self.assertIn('_cohort_key(game)', source,
                          f'{module.__name__} does not use the shared rule')
            self.assertNotIn('_seed(game.id', source,
                             f'{module.__name__} still seeds on the game id')
        self.assertIn('game.section_id or game.id', inspect.getsource(events))

    def test_a_sectioned_game_is_keyed_on_its_section(self):
        self.assertEqual(_cohort_key(_Game(section_id=7, id=42)), 7)

    def test_an_unsectioned_game_stays_isolated_by_game_id(self):
        """A solo game must not collide with any other solo game."""
        self.assertEqual(_cohort_key(_Game(section_id=None, id=42)), 42)
        self.assertNotEqual(
            get_rng(_cohort_key(_Game(None, 42)), 1, 'op').random(),
            get_rng(_cohort_key(_Game(None, 43)), 1, 'op').random())

    def test_two_sections_of_one_class_are_different_cohorts(self):
        self.assertNotEqual(
            get_rng(_cohort_key(_Game(1, 10)), 1, 'op').random(),
            get_rng(_cohort_key(_Game(2, 11)), 1, 'op').random())


class StreamIndependenceTests(SimpleTestCase):
    """The properties V2-011 asks for, stated as arithmetic on the keys."""

    def enforcement(self, class_id, round_number, regime, team, market):
        return get_rng(
            class_id, round_number,
            f'compliance_enforcement:{regime}:{team}:{market}').random()

    def test_repeated_execution_is_exact(self):
        first = self.enforcement(1, 3, 'REACH', 42, 'eu')
        second = self.enforcement(1, 3, 'REACH', 42, 'eu')
        self.assertEqual(first, second)

    def test_reordering_teams_changes_nothing(self):
        """The draw belongs to the team, not to its position in a queryset."""
        forwards = [self.enforcement(1, 3, 'REACH', t, 'eu')
                    for t in (10, 20, 30)]
        backwards = [self.enforcement(1, 3, 'REACH', t, 'eu')
                     for t in (30, 20, 10)]
        self.assertEqual(forwards, list(reversed(backwards)))

    def test_adding_or_withdrawing_a_team_changes_no_other_team(self):
        """The defect, stated directly: one team's presence moved another's."""
        cohort = [10, 20, 30]
        before = {t: self.enforcement(1, 3, 'REACH', t, 'eu') for t in cohort}

        joined = cohort + [40]
        after_join = {t: self.enforcement(1, 3, 'REACH', t, 'eu')
                      for t in joined}
        for team in cohort:
            self.assertEqual(before[team], after_join[team])

        withdrew = [t for t in cohort if t != 20]
        after_withdraw = {t: self.enforcement(1, 3, 'REACH', t, 'eu')
                          for t in withdrew}
        for team in withdrew:
            self.assertEqual(before[team], after_withdraw[team])

    def test_distinct_operations_have_independent_streams(self):
        base = self.enforcement(1, 3, 'REACH', 42, 'eu')
        self.assertNotEqual(base, self.enforcement(1, 3, 'REACH', 43, 'eu'))
        self.assertNotEqual(base, self.enforcement(1, 3, 'RoHS', 42, 'eu'))
        self.assertNotEqual(base, self.enforcement(1, 3, 'REACH', 42, 'na'))
        self.assertNotEqual(base, self.enforcement(1, 4, 'REACH', 42, 'eu'))
        self.assertNotEqual(base, self.enforcement(2, 3, 'REACH', 42, 'eu'))

    def test_subsystems_do_not_share_a_stream(self):
        """A supply-chain roll and a compliance roll must not be the same draw."""
        sc = get_rng(1, 3, 'sc_event_trigger:5').random()
        compliance = get_rng(1, 3, 'compliance_enforcement:REACH:5:eu').random()
        event = get_rng(1, 3, 'event_trigger:5').random()
        self.assertEqual(len({sc, compliance, event}), 3)


class SharedSequentialContrastTests(SimpleTestCase):
    """Why per-operation keying was needed, shown rather than asserted.

    The repaired engines no longer contain a shared sequential RNG, so a test
    against the old code can only fail on import. This reproduces the old
    consumption pattern in miniature and demonstrates the property that made it
    unfair — then shows the keyed scheme does not have it.
    """

    @staticmethod
    def sequential_draws(teams):
        """One RNG, consumed in queryset order — the old pattern."""
        import random
        rng = random.Random(12345)
        return {team: rng.random() for team in teams}

    @staticmethod
    def keyed_draws(teams):
        return {team: get_rng(1, 3, f'compliance_enforcement:REACH:{team}:eu')
                .random() for team in teams}

    def test_a_shared_sequential_rng_lets_one_team_move_another(self):
        before = self.sequential_draws([10, 20, 30])
        after_join = self.sequential_draws([5, 10, 20, 30])
        self.assertNotEqual(before[10], after_join[10],
                            'if this ever passes, the contrast is meaningless')
        self.assertNotEqual(before[30], after_join[30])

    def test_a_shared_sequential_rng_depends_on_order(self):
        forwards = self.sequential_draws([10, 20, 30])
        backwards = self.sequential_draws([30, 20, 10])
        self.assertNotEqual(forwards[10], backwards[10])

    def test_the_keyed_scheme_has_neither_property(self):
        before = self.keyed_draws([10, 20, 30])
        after_join = self.keyed_draws([5, 10, 20, 30])
        backwards = self.keyed_draws([30, 20, 10])
        for team in (10, 20, 30):
            self.assertEqual(before[team], after_join[team])
            self.assertEqual(before[team], backwards[team])
