"""Where Phase 2 narrative calls go, and with which model.

Round narratives moved from DashScope to the local LiteLLM fleet proxy. These
tests pin the routing rules without reaching any provider: the HTTP client is
replaced by a recorder.

* Both NARRATIVE_LLM_URL and NARRATIVE_LLM_KEY set: calls go to the proxy with
  the per-call alias (`analyst` / `tutor`).
* Either unset: calls go to DashScope exactly as before, with DASHSCOPE_MODEL --
  a proxy alias is not a DashScope model.
* The thinking switch is left to the alias unless a call sets it, because an
  explicit `enable_thinking: false` would turn `analyst`'s thinking off.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.engine import llm_runner, narratives
from core.services import narrative_jobs

PROXY_URL = 'http://proxy.test:4100/v1/chat/completions'
DASHSCOPE_URL = 'https://dashscope.test/compatible-mode/v1/chat/completions'

BASE = dict(
    DASHSCOPE_API_KEY='dashscope-test-key',
    DASHSCOPE_MODEL='qwen-max',
    DASHSCOPE_COMPATIBLE_URL=DASHSCOPE_URL,
    NARRATIVE_LLM_URL=PROXY_URL,
    NARRATIVE_LLM_KEY='proxy-test-key',
    NARRATIVE_MODEL_DEEP='analyst',
    NARRATIVE_MODEL_FAST='tutor',
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


@override_settings(**BASE)
class ProxyRoutingTests(RoutingBase):

    def test_calls_go_to_the_proxy_with_its_key_and_the_call_model(self):
        results, sent = self.send([
            {'id': 'a', 'prompt': 'p', 'model': 'analyst'},
            {'id': 'b', 'prompt': 'p', 'model': 'tutor'},
        ])
        self.assertTrue(all(r['success'] for r in results.values()))
        self.assertEqual({r['url'] for r in sent}, {PROXY_URL})
        self.assertEqual({r['headers']['Authorization'] for r in sent},
                         {'Bearer proxy-test-key'})
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
        without = [b for b in bodies if 'chat_template_kwargs' not in b]
        self.assertEqual(len(with_switch), 1)
        self.assertEqual(with_switch[0]['chat_template_kwargs'],
                         {'enable_thinking': False})
        self.assertEqual(len(without), 1)
        self.assertTrue(all('extra_body' not in r['body'] for r in sent))

    def test_a_call_without_a_model_uses_dashscope_model(self):
        _results, sent = self.send([{'id': 'a', 'prompt': 'p'}])
        self.assertEqual(sent[0]['body']['model'], 'qwen-max')

    def test_pacing_for_a_shared_gpu(self):
        self.assertEqual(llm_runner.TIMEOUT_PER_CALL, 150)
        self.assertEqual(llm_runner.MAX_CONCURRENT, 4)
        _results, sent = self.send([{'id': 'a', 'prompt': 'p', 'model': 'tutor'}])
        self.assertEqual(sent[0]['timeout'], 150)

    def test_job_provenance_names_the_alias_and_proxy_but_never_the_key(self):
        deep = narrative_jobs._model_provenance('briefing')
        fast = narrative_jobs._model_provenance('compliance')
        self.assertEqual(deep, {'model_name': 'analyst', 'model_endpoint': PROXY_URL})
        self.assertEqual(fast['model_name'], 'tutor')
        self.assertNotIn('proxy-test-key', repr((deep, fast)))


class DashScopeFallbackTests(RoutingBase):

    def assert_dashscope(self, sent):
        self.assertEqual(sent[0]['url'], DASHSCOPE_URL)
        self.assertEqual(sent[0]['headers']['Authorization'],
                         'Bearer dashscope-test-key')
        # `analyst` means nothing to DashScope.
        self.assertEqual(sent[0]['body']['model'], 'qwen-max')
        self.assertNotIn('chat_template_kwargs', sent[0]['body'])

    @override_settings(**{**BASE, 'NARRATIVE_LLM_KEY': ''})
    def test_without_a_proxy_key_calls_stay_on_dashscope(self):
        _results, sent = self.send([{'id': 'a', 'prompt': 'p', 'model': 'analyst'}])
        self.assert_dashscope(sent)

    @override_settings(**{**BASE, 'NARRATIVE_LLM_URL': ''})
    def test_without_a_proxy_url_calls_stay_on_dashscope(self):
        _results, sent = self.send([{'id': 'a', 'prompt': 'p', 'model': 'analyst'}])
        self.assert_dashscope(sent)

    @override_settings(**{**BASE, 'NARRATIVE_LLM_URL': '', 'DASHSCOPE_API_KEY': ''})
    def test_no_key_anywhere_means_no_calls(self):
        results, sent = self.send([{'id': 'a', 'prompt': 'p', 'model': 'analyst'}])
        self.assertEqual(sent, [])
        self.assertEqual(results['a']['error'], 'no_api_key')
        self.assertFalse(narratives._llm_available())

    @override_settings(**{**BASE, 'DASHSCOPE_API_KEY': ''})
    def test_the_proxy_alone_is_enough_for_narratives(self):
        self.assertTrue(narratives._llm_available())


@override_settings(**BASE)
class NarrativeModelTests(SimpleTestCase):

    def test_analysis_types_use_the_deep_model_and_notices_the_fast_one(self):
        self.assertEqual(
            {t: narratives.model_for_type(t) for t in narrative_jobs.ENQUEUED_TYPES},
            {'briefing': 'analyst', 'coherence_rag': 'analyst',
             'coaching': 'analyst', 'outlook': 'tutor',
             'sc_event': 'tutor', 'compliance': 'tutor'})

    @override_settings(NARRATIVE_MODEL_DEEP='qwen3.7-max', NARRATIVE_MODEL_FAST='fast')
    def test_model_names_come_from_settings(self):
        self.assertEqual(narratives.model_for_type('briefing'), 'qwen3.7-max')
        self.assertEqual(narratives.model_for_type('outlook'), 'fast')

    def test_communication_scoring_is_not_routed_through_the_proxy(self):
        """It feeds graded coherence; moving it needs its own comparison."""
        import inspect
        from core.rag import communication_eval
        source = inspect.getsource(communication_eval)
        self.assertNotIn('NARRATIVE_LLM', source)
        self.assertNotIn('run_llm_batch', source)
        self.assertIn('DASHSCOPE_API_KEY', source)
