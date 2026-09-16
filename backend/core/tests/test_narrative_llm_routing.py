"""Where model calls go, and which model answers.

Every model call this platform makes goes to the local LiteLLM fleet gateway.
No third-party provider is called from here and no provider SDK is imported
(2026-09-16). These tests pin that without reaching any endpoint: the HTTP
client is replaced by a recorder.

The model is chosen by purpose (llm_runner.MODEL_BY_PURPOSE), so the choice is
stated in one place and can be overridden per purpose from the environment.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.engine import llm_runner, narratives
from core.services import narrative_jobs

GATEWAY_URL = 'http://gateway.test:4100/v1/chat/completions'

BASE = dict(
    LLM_GATEWAY_URL=GATEWAY_URL,
    LLM_GATEWAY_KEY='gateway-test-key',
    LLM_PURPOSE_MODELS={},
)


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {'choices': [{'message': {'content': 'ok'}}]}


class _RecordingClient:
    """Stands in for httpx.AsyncClient and records every request."""

    requests = []

    def __init__(self, timeout=None):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None):
        _RecordingClient.requests.append(
            {'url': url, 'body': json, 'headers': headers,
             'timeout': self.timeout})
        return _Response()


class RoutingBase(SimpleTestCase):
    def send(self, calls):
        _RecordingClient.requests = []
        with patch.object(llm_runner.httpx, 'AsyncClient', _RecordingClient):
            results = llm_runner.run_llm_batch_sync(calls)
        return results, list(_RecordingClient.requests)

    def send_one(self, **kwargs):
        captured = {}

        def recorder(url, json=None, headers=None, timeout=None):
            captured.update({'url': url, 'body': json, 'headers': headers,
                             'timeout': timeout})
            return _Response()

        with patch.object(llm_runner.httpx, 'post', recorder):
            text = llm_runner.chat_completion(
                messages=[{'role': 'user', 'content': 'hi'}], **kwargs)
        return text, captured


@override_settings(**BASE)
class GatewayRoutingTests(RoutingBase):

    def test_batch_calls_go_to_the_gateway_with_its_key_and_model(self):
        results, sent = self.send([
            {'id': 'a', 'prompt': 'p', 'model': 'analyst'},
            {'id': 'b', 'prompt': 'p', 'model': 'tutor'},
        ])
        self.assertTrue(all(r['success'] for r in results.values()))
        self.assertEqual({r['url'] for r in sent}, {GATEWAY_URL})
        self.assertEqual({r['headers']['Authorization'] for r in sent},
                         {'Bearer gateway-test-key'})
        self.assertEqual(sorted(r['body']['model'] for r in sent),
                         ['analyst', 'tutor'])

    def test_thinking_is_left_to_the_alias_unless_a_call_sets_it(self):
        _results, sent = self.send([
            {'id': 'default', 'prompt': 'p', 'model': 'analyst'},
            {'id': 'off', 'prompt': 'p', 'model': 'analyst',
             'enable_thinking': False},
        ])
        bodies = [r['body'] for r in sent]
        with_switch = [b for b in bodies if 'chat_template_kwargs' in b]
        self.assertEqual(len(with_switch), 1)
        self.assertEqual(with_switch[0]['chat_template_kwargs'],
                         {'enable_thinking': False})
        self.assertEqual(len([b for b in bodies if 'chat_template_kwargs' not in b]), 1)
        self.assertTrue(all('extra_body' not in b for b in bodies))

    def test_a_call_without_a_model_uses_the_default_purpose(self):
        _results, sent = self.send([{'id': 'a', 'prompt': 'p'}])
        self.assertEqual(sent[0]['body']['model'],
                         llm_runner.model_for_purpose(llm_runner.DEFAULT_PURPOSE))

    def test_pacing_for_a_shared_gpu(self):
        self.assertEqual(llm_runner.TIMEOUT_PER_CALL, 150)
        self.assertEqual(llm_runner.MAX_CONCURRENT, 4)
        _results, sent = self.send([{'id': 'a', 'prompt': 'p', 'model': 'tutor'}])
        self.assertEqual(sent[0]['timeout'], 150)

    def test_single_calls_go_to_the_gateway_with_the_given_model(self):
        text, sent = self.send_one(model='tutor', max_tokens=400, temperature=0.3)
        self.assertEqual(text, 'ok')
        self.assertEqual(sent['url'], GATEWAY_URL)
        self.assertEqual(sent['headers']['Authorization'], 'Bearer gateway-test-key')
        self.assertEqual(sent['body']['model'], 'tutor')
        self.assertEqual(sent['body']['max_tokens'], 400)
        self.assertEqual(sent['body']['temperature'], 0.3)

    def test_a_caller_timeout_is_honoured(self):
        _text, sent = self.send_one(model='tutor', timeout=5)
        self.assertEqual(sent['timeout'], 5)

    def test_a_failed_call_returns_none_so_callers_fall_back(self):
        def boom(*args, **kwargs):
            raise RuntimeError('gateway down')

        with patch.object(llm_runner.httpx, 'post', boom):
            self.assertIsNone(llm_runner.chat_completion(
                messages=[{'role': 'user', 'content': 'hi'}], model='tutor'))

    def test_the_embeddings_url_sits_beside_the_chat_url(self):
        self.assertEqual(llm_runner.embeddings_url(),
                         'http://gateway.test:4100/v1/embeddings')

    def test_job_provenance_names_the_model_and_gateway_but_never_the_key(self):
        deep = narrative_jobs._model_provenance('briefing')
        fast = narrative_jobs._model_provenance('compliance')
        self.assertEqual(deep, {'model_name': 'analyst', 'model_endpoint': GATEWAY_URL})
        self.assertEqual(fast['model_name'], 'tutor')
        self.assertNotIn('gateway-test-key', repr((deep, fast)))


class NoGatewayTests(RoutingBase):
    """With nothing configured there is no model, and callers fall back."""

    @override_settings(**{**BASE, 'LLM_GATEWAY_KEY': ''})
    def test_without_a_key_nothing_is_called(self):
        results, sent = self.send([{'id': 'a', 'prompt': 'p', 'model': 'tutor'}])
        self.assertEqual(sent, [])
        self.assertEqual(results['a']['error'], 'no_api_key')
        self.assertFalse(narratives._llm_available())

    @override_settings(**{**BASE, 'LLM_GATEWAY_URL': ''})
    def test_without_a_url_nothing_is_called(self):
        text, sent = self.send_one(model='tutor')
        self.assertIsNone(text)
        self.assertEqual(sent, {})
        self.assertFalse(llm_runner.llm_configured())

    @override_settings(**BASE)
    def test_a_configured_gateway_is_all_that_is_needed(self):
        self.assertTrue(narratives._llm_available())


@override_settings(**BASE)
class PurposeModelTests(SimpleTestCase):

    def test_every_purpose_names_a_local_fleet_alias(self):
        local_aliases = {'analyst', 'tutor', 'reasoner', 'fast', 'classify',
                         'qwen36', 'qwen38', 'gpt-oss-120b', 'qwen2.5-14b'}
        for purpose, model in llm_runner.MODEL_BY_PURPOSE.items():
            with self.subTest(purpose=purpose):
                self.assertIn(model, local_aliases)

    def test_narrative_types_map_to_their_tier(self):
        self.assertEqual(
            {t: narratives.model_for_type(t) for t in narrative_jobs.ENQUEUED_TYPES},
            {'briefing': 'analyst', 'coherence_rag': 'analyst',
             'coaching': 'analyst', 'outlook': 'tutor',
             'sc_event': 'tutor', 'compliance': 'tutor'})

    def test_work_a_person_waits_on_does_not_use_a_thinking_model(self):
        """`analyst` thinks for ~45s; nobody waits that long on a screen."""
        for purpose in ('research_brief', 'persona_reply', 'query_translation',
                        'communication_eval'):
            with self.subTest(purpose=purpose):
                self.assertEqual(llm_runner.model_for_purpose(purpose), 'tutor')

    @override_settings(LLM_PURPOSE_MODELS={'communication_eval': 'analyst'})
    def test_a_purpose_can_be_overridden_from_the_environment(self):
        self.assertEqual(llm_runner.model_for_purpose('communication_eval'), 'analyst')
        self.assertEqual(llm_runner.model_for_purpose('research_brief'), 'tutor')

    def test_communication_scoring_pins_its_own_purpose(self):
        """It feeds a grade, so it must not borrow another caller's model."""
        import inspect
        from core.rag import communication_eval
        source = inspect.getsource(communication_eval._call_llm_evaluation)
        self.assertIn("model_for_purpose('communication_eval')", source)


class NoDirectProviderCallTests(SimpleTestCase):
    """No platform code may call a model provider directly (2026-09-16)."""

    def _sources(self):
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[2]
        for path in sorted((root / 'core').rglob('*.py')):
            if 'tests' in path.parts or 'migrations' in path.parts:
                continue
            yield path.relative_to(root).as_posix(), path.read_text()
        yield ('globalstrat/settings.py',
               (root / 'globalstrat' / 'settings.py').read_text())

    def test_no_module_imports_a_provider_sdk(self):
        offenders = [name for name, source in self._sources()
                     if 'import dashscope' in source
                     or 'from dashscope import' in source
                     or 'import openai' in source]
        self.assertEqual(offenders, [])

    def test_no_module_names_a_provider_endpoint(self):
        offenders = [name for name, source in self._sources()
                     if 'aliyuncs.com' in source or 'api.openai.com' in source
                     or 'api.anthropic.com' in source]
        self.assertEqual(offenders, [])

    def test_every_chat_call_goes_through_the_runner(self):
        """A POST to a chat endpoint anywhere else is a direct provider call."""
        offenders = [name for name, source in self._sources()
                     if "'/chat/completions'" in source
                     and name != 'core/engine/llm_runner.py']
        self.assertEqual(offenders, [])

    def test_no_module_reads_a_provider_setting(self):
        offenders = [name for name, source in self._sources()
                     if 'DASHSCOPE' in source]
        self.assertEqual(offenders, [])
