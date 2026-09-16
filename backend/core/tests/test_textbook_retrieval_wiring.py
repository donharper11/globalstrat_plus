"""Course-material retrieval: dead by configuration, not by accident.

This service came over from BECSR in the fork pointing at a collection that has
never existed (`globalstrat_textbook`), so persona prompts and the two
`/api/resources/` endpoints silently received nothing while the code looked
wired. These tests pin the three things that repair required, so the next reader
can tell "switched off" from "broken":

* it is configuration-driven, and unconfigured means an immediate empty result;
* a configured-but-missing collection is reported once, not once per request;
* embedding goes through the fleet gateway, never a local model download.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.services import textbook_retrieval as TR


class _Client:
    """Stands in for QdrantClient; records what it was asked."""

    def __init__(self, exists=True, fail=False):
        self.exists = exists
        self.fail = fail
        self.asked = []

    def collection_exists(self, name):
        self.asked.append(name)
        if self.fail:
            raise RuntimeError('qdrant unreachable')
        return self.exists

    def query_points(self, **kwargs):
        raise AssertionError('must not be reached when unavailable')

    def scroll(self, **kwargs):
        raise AssertionError('must not be reached when unavailable')


class AvailabilityTests(SimpleTestCase):
    def setUp(self):
        TR._UNAVAILABLE_REPORTED.clear()

    @override_settings(TEXTBOOK_COLLECTION='')
    def test_unconfigured_is_unavailable_and_searches_nothing(self):
        self.assertFalse(TR.is_available())
        with patch.object(TR, '_get_client', side_effect=AssertionError('no call')):
            self.assertEqual(TR.search_textbook('anything'), [])
            self.assertEqual(TR.get_textbook_content(), [])
            self.assertEqual(TR.get_context_for_persona('cfo', 'trigger'), '')
            self.assertEqual(TR.get_context_for_student_query('a real question'), '')

    @override_settings(TEXTBOOK_COLLECTION='a_collection_only_settings_could_name')
    def test_a_missing_collection_is_reported_once_not_per_request(self):
        """The name is deliberately odd: a hardcoded collection cannot satisfy it."""
        client = _Client(exists=False)
        with patch.object(TR, '_get_client', return_value=client):
            with self.assertLogs('core.services.textbook_retrieval', level='WARNING') as first:
                self.assertEqual(TR.search_textbook('q'), [])
            self.assertEqual(len(first.output), 1)
            self.assertIn('a_collection_only_settings_could_name', first.output[0])
            # Second call: still refuses, but says nothing more.
            with patch.object(TR.logger, 'warning') as warn:
                self.assertEqual(TR.search_textbook('q'), [])
                warn.assert_not_called()
        # It kept asking the host rather than caching a stale "no".
        self.assertEqual(client.asked, ['a_collection_only_settings_could_name'] * 2)

    @override_settings(TEXTBOOK_COLLECTION='globalstrat_textbook')
    def test_an_unreachable_host_is_not_an_exception_to_the_caller(self):
        with patch.object(TR, '_get_client', return_value=_Client(fail=True)):
            self.assertFalse(TR.is_available())
            self.assertEqual(TR.search_textbook('q'), [])


@override_settings(TEXTBOOK_COLLECTION='some_collection',
                   TEXTBOOK_EMBEDDING_MODEL='bge-m3',
                   LLM_GATEWAY_URL='http://gateway.test:4100/v1/chat/completions',
                   LLM_GATEWAY_KEY='gateway-test-key')
class EmbeddingRouteTests(SimpleTestCase):
    def setUp(self):
        TR._UNAVAILABLE_REPORTED.clear()

    def test_embedding_goes_to_the_gateway_with_the_configured_model(self):
        captured = {}

        class _Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {'data': [{'embedding': [0.1, 0.2, 0.3]}]}

        def recorder(url, json=None, headers=None, timeout=None):
            captured.update({'url': url, 'body': json, 'headers': headers})
            return _Response()

        import httpx
        with patch.object(httpx, 'post', recorder):
            vector = TR._embed('market entry strategy')

        self.assertEqual(vector, [0.1, 0.2, 0.3])
        self.assertEqual(captured['url'], 'http://gateway.test:4100/v1/embeddings')
        self.assertEqual(captured['body']['model'], 'bge-m3')
        self.assertEqual(captured['headers']['Authorization'], 'Bearer gateway-test-key')

    def test_no_local_model_is_ever_downloaded(self):
        """The pre-repair code would have fetched ~2.2GB inside a request.

        Checks the code, not the prose: the module docstring names the removed
        call deliberately, so a plain text scan would match its own explanation.
        """
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(TR))
        imported = {
            alias.name.split('.')[0]
            for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module.split('.')[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertNotIn('sentence_transformers', imported)
        called = {
            node.func.id for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertNotIn('SentenceTransformer', called)

    @override_settings(LLM_GATEWAY_KEY='')
    def test_without_a_gateway_it_returns_nothing_rather_than_raising(self):
        self.assertIsNone(TR._embed('q'))
