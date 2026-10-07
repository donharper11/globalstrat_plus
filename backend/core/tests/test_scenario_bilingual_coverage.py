"""Authored scenario content exists in both shipped languages.

The Stage-5 control (`backend/scripts/check-participant-strings`) asks whether
a scenario-authored name is *localised rather than interpolated raw* — a
question about mechanism, on the eight backend files in its scope. It does not
ask whether the authored content exists in both languages, and the ten-round
browser pass on candidate `a0631e5d` found what that costs: **155 player-facing
strings in the competition scenario had no `_zh` sibling**, and a
Simplified-Chinese team read the alliance questions it was judged on, the
criteria its memos were graded against, and the event news of every round, in
English. The mechanism was right everywhere, which is exactly why nobody saw
it: the same file already carried 126 `name_zh` and 96 `description_zh`.

This asserts the coverage. A new partner preference, assignment criterion or
event added without its translation fails here rather than on a Chinese
student's screen.

**Proper nouns are named individually, with the reason.** A manufacturer's
registered name and the title of a statute are legitimately Latin on a Chinese
screen. Nothing else gets that excuse, and a pattern match would have handed it
to everything.
"""
import pathlib

import yaml
from django.test import SimpleTestCase

SCENARIOS = (pathlib.Path(__file__).resolve().parents[2] / 'scenarios')

# The authored fields a player reads, each of which already has an established
# `<field>_zh` sibling in the shipped scenarios.
TRANSLATABLE = ('name', 'description', 'prompt_text', 'description_template')

# path -> why this one is allowed to stay in Latin script.
PROPER_NOUNS = {
    'suppliers[]:name': "a manufacturer's registered company name",
    'compliance_regimes[]:name': 'the title of a statute',
}

# path -> why a player never reads this, so a translation would be dead content.
# `interactions` is served as stored by `cc31j_views`; what a player actually
# reads about an interaction is built by `_evaluate_all_interactions` from the
# bilingual catalogue, and the page renders no field from the blob. The
# `amplifier` beside it IS printed, so it is not excused here and is translated.
NOT_SHOWN_TO_PLAYERS = {
    'governance_commitments[].interactions[].effect:description':
        'authoring note; the player reads the catalogue-built interaction '
        'warning, and CorporateStrategyPage renders no field of this blob',
    'governance_commitments[].interactions[].effect.impact:description':
        'the same blob, one level deeper',
}

# The scenario the competition runs. The other shipped scenarios are checked
# too, but only this one is required to be complete: see the test below.
COMPETITION_SCENARIO = 'consumer_electronics_2026.yaml'


def missing_translations(path):
    """{dotted place: [english values]} for every untranslated authored field."""
    document = yaml.safe_load(path.open())
    found = {}

    def walk(node, where):
        if isinstance(node, dict):
            for base in TRANSLATABLE:
                value = node.get(base)
                if isinstance(value, str) and value.strip():
                    sibling = node.get(base + '_zh')
                    if not (isinstance(sibling, str) and sibling.strip()):
                        key = (where or 'root') + ':' + base
                        found.setdefault(key, []).append(value)
            for key, value in node.items():
                walk(value, (where + '.' + str(key)) if where else str(key))
        elif isinstance(node, list):
            for item in node:
                walk(item, where + '[]')

    walk(document, '')
    return found


class CompetitionScenarioBilingualCoverageTests(SimpleTestCase):
    """The scenario the competition is run on has to be complete."""

    def setUp(self):
        self.path = SCENARIOS / COMPETITION_SCENARIO
        self.assertTrue(self.path.exists(), self.path)
        self.missing = missing_translations(self.path)

    def test_every_player_facing_string_has_a_chinese_sibling(self):
        unexplained = {
            place: values for place, values in self.missing.items()
            if place not in PROPER_NOUNS and place not in NOT_SHOWN_TO_PLAYERS}
        self.assertEqual(
            unexplained, {},
            'authored content a player reads with no `_zh` sibling. Add the '
            'translation, or — if it is a proper noun or something no player '
            'reads — name it in PROPER_NOUNS / NOT_SHOWN_TO_PLAYERS above with '
            'the reason, so the exception is stated rather than assumed.')

    def test_the_event_news_of_every_round_is_translated(self):
        """Called out separately because it is read every round, by everyone."""
        self.assertNotIn('events[]:description_template', self.missing)

    def test_the_alliance_questions_are_translated(self):
        """The 105 that this gap was found through."""
        self.assertNotIn(
            'alliance_partner_profiles[].preferences[]:description',
            self.missing)

    def test_the_memo_criteria_are_translated(self):
        """What a team is told its writing is judged on."""
        self.assertNotIn(
            'communication_assignments[].evaluation_criteria[]:description',
            self.missing)

    def test_every_stated_exception_is_still_doing_something(self):
        """An allow-list that has stopped matching is a lie about the content.

        If a proper noun is translated later, or a blob starts being shown to
        players, the entry here has to go — otherwise the next real gap hides
        behind it.
        """
        for place in PROPER_NOUNS:
            self.assertIn(place, self.missing,
                          '%s is listed as a proper noun but has a translation '
                          'now; drop the exception' % place)


class ShippedScenarioBilingualCoverageTests(SimpleTestCase):
    """The other scenarios, measured rather than enforced.

    They are not what the competition runs, and holding them to the same bar
    today would fail a check nobody has been given time to satisfy. What this
    does is stop them getting quietly worse: the counts are recorded here, and
    a new untranslated string pushes the number past its stated ceiling.
    """

    # Measured 2026-10-07 on candidate `a0631e5d`, after the competition
    # scenario was completed. Lower these as the scenarios are translated;
    # never raise them to make a failure go away.
    CEILINGS = {
        'clean_energy_tech_2026.yaml': 135,
        'media_entertainment_2026.yaml': 135,
        'consumer_electronics_plus_skeleton.yaml': 2,
    }

    def test_no_shipped_scenario_gets_less_translated(self):
        for name, ceiling in self.CEILINGS.items():
            path = SCENARIOS / name
            if not path.exists():
                continue
            total = sum(len(values) for place, values
                        in missing_translations(path).items())
            self.assertLessEqual(
                total, ceiling,
                '%s now has %d untranslated authored strings against a stated '
                'ceiling of %d' % (name, total, ceiling))
