"""One zh-CN word per concept, across every catalogue a user reads (D4).

On 2026-09-21 the backend catalogues said 比赛 for "game" while the frontend
catalogue said 游戏, so one screen could show both for the same thing: the
roster's short-team notice printed the server's 比赛开始前 directly above the
interface's 游戏. The survey that settled the terms (counts at f46d173):

    game         游戏 48   vs 比赛 8        -> 游戏
    round        回合 174  vs 轮 16         -> 回合
    team         团队 98   vs 队伍 4, 小组 1  -> 团队
    instructor   教师 17   (no rival)       -> 教师
    competition  竞赛 3    vs 比赛场次 1     -> 竞赛, and only where the text
                                              really means a competition

比赛 is therefore not used at all: a game an instructor runs is a 游戏, and a
competition is a 竞赛. This test reads the catalogues as text, so a new
sentence cannot reintroduce a retired term.
"""
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent

RETIRED = {
    '比赛': '游戏 (a game) or 竞赛 (a competition)',
    '队伍': '团队',
    '小组': '团队',
    '轮': '回合',
}

# The only sentences allowed to say 竞赛: they are about a competition as such.
COMPETITION_KEYS = {
    'frontend:instructor.grades_refused_model_component',
    'cohort_messages:competition_course_unowned',
    # A heat cannot be deleted: the sentence is about the competition itself.
    'cohort_messages:competition_game_not_deletable',
}


def _python_catalogue(relative, *dict_names):
    import ast
    tree = ast.parse((BACKEND / relative).read_text(encoding='utf-8'))
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        name = getattr(node.targets[0], 'id', None)
        if name in dict_names:
            for key, entry in ast.literal_eval(node.value).items():
                found[f'{name}.{key}'] = entry['zh-CN']
    return found


def _flatten(node, prefix=''):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _flatten(value, f'{prefix}.{key}' if prefix else key)
    elif isinstance(node, str):
        yield prefix, node


def zh_sentences():
    """{source:key -> zh-CN text} for every catalogue a user reads."""
    sentences = {}
    locale = json.loads((REPO / 'frontend/globalstrat-frontend/src/locales'
                         / 'zh-CN.json').read_text(encoding='utf-8'))
    for key, text in _flatten(locale):
        sentences[f'frontend:{key}'] = text
    for module, names in (
            ('participant_messages',
             ('MESSAGES', 'FIELD_LABELS', 'ROUND_STATUS_LABELS')),
            ('cohort_messages', ('MESSAGES',)),
            ('operator_messages', ('MESSAGES', 'GAME_STATUS_LABELS',
                                   'SUBMISSION_ORIGIN_LABELS'))):
        for key, text in _python_catalogue(
                f'core/utils/{module}.py', *names).items():
            short = key.split('.', 1)[1] if key.startswith('MESSAGES.') else key
            sentences[f'{module}:{short}'] = text
    # The instructor ticker keeps its zh-CN strings beside the view, and the
    # Phase-2 template fallbacks keep theirs beside the engine (W-CE-16).
    for label, relative in (
            ('cc31h_views', 'core/views/cc31h_views.py'),
            ('narratives', 'core/engine/narratives.py'),
            ('instructor_alerts', 'core/engine/instructor_alerts.py'),
            ('communication_eval', 'core/rag/communication_eval.py')):
        source = (BACKEND / relative).read_text(encoding='utf-8')
        for index, text in enumerate(re.findall(r"'([^'\n]*[一-鿿][^'\n]*)'",
                                                source)):
            sentences[f'{label}:{index}'] = text
    return sentences


class ZhTerminologyTests(SimpleTestCase):

    def test_the_survey_reads_every_catalogue(self):
        sources = {key.split(':', 1)[0] for key in zh_sentences()}
        self.assertEqual(sources, {
            'frontend', 'participant_messages', 'cohort_messages',
            'operator_messages', 'cc31h_views', 'narratives',
            'instructor_alerts', 'communication_eval'})
        self.assertGreater(len(zh_sentences()), 1500)

    def test_no_catalogue_uses_a_retired_term(self):
        offenders = [
            f'{key}: {text!r} says {term}; the established term is {instead}'
            for key, text in sorted(zh_sentences().items())
            for term, instead in RETIRED.items() if term in text]
        self.assertEqual(offenders, [])

    def test_competition_is_said_only_where_a_competition_is_meant(self):
        users = {key for key, text in zh_sentences().items() if '竞赛' in text}
        self.assertEqual(users, COMPETITION_KEYS)
