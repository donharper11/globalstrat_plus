"""
Embedding generation for RAG queries.
Supports BGE-M3 (local via sentence-transformers) or DashScope API.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# English-only embedding models that need query translation for non-English input
_ENGLISH_ONLY_MODELS = {'all-MiniLM-L6-v2', 'all-MiniLM-L12-v2'}


def _is_english_only_model():
    """Check if the configured embedding model is English-only."""
    model_name = settings.EMBEDDING_MODEL
    # Check against known English-only model names (may be full path)
    for name in _ENGLISH_ONLY_MODELS:
        if name in model_name:
            return True
    return False


def translate_query_if_needed(query, language):
    """Translate a zh-CN query to English for English-only embedding models.

    If the embedding model supports multilingual input (e.g. BGE-M3), returns
    the query unchanged. For English-only models like all-MiniLM-L6-v2,
    translates zh-CN queries to English via the LLM.
    """
    if language != 'zh-CN' or not _is_english_only_model():
        return query

    try:
        from core.engine import llm_runner

        if not llm_runner.llm_configured():
            return query

        translated = (llm_runner.chat_completion(
            model=llm_runner.model_for_purpose('query_translation'),
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'Translate the following Chinese search query to English. '
                        'Return ONLY the English translation, nothing else. '
                        'Keep it concise — this is a search query for an academic knowledge base.'
                    ),
                },
                {'role': 'user', 'content': query},
            ],
            max_tokens=100,
            temperature=0.0,
            timeout=10,
        ) or '').strip()
        if translated:
            logger.debug(f"RAG query translated: '{query}' -> '{translated}'")
            return translated
    except Exception as e:
        logger.warning(f"Query translation failed, using original: {e}")

    return query


def get_embedding(text):
    """
    Generate an embedding for the given text.
    Uses sentence-transformers (local path or HuggingFace model) or the
    configured remote endpoint.
    Local models: paths starting with '/' or HuggingFace IDs like 'BAAI/bge-m3'.
    Remote: model names not matching the above patterns.
    """
    model_name = settings.EMBEDDING_MODEL
    # Use local embedding for filesystem paths or known HuggingFace models
    if model_name.startswith('/') or model_name.startswith('BAAI/') or model_name.startswith('sentence-transformers/'):
        return _local_embedding(text)
    else:
        return _remote_embedding(text)


def _local_embedding(text):
    """Use sentence-transformers for local embedding."""
    from sentence_transformers import SentenceTransformer
    # Cache the model as a function-level singleton
    if not hasattr(_local_embedding, '_model'):
        _local_embedding._model = SentenceTransformer(settings.EMBEDDING_MODEL)
    model = _local_embedding._model
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def _remote_embedding(text):
    """Embed through the configured endpoint (proxy, else DashScope).

    Dormant in production, where EMBEDDING_MODEL is a local path and
    _local_embedding runs instead. The model name is unchanged, so the vectors
    are the same ones the Qdrant collection was built with.
    """
    import httpx

    from core.engine import llm_runner

    if not llm_runner.llm_configured():
        raise RuntimeError('No embedding endpoint key configured.')

    response = httpx.post(
        llm_runner.embeddings_url(),
        headers={'Authorization': f'Bearer {llm_runner._get_key()}',
                 'Content-Type': 'application/json'},
        json={'model': settings.EMBEDDING_MODEL, 'input': text},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()['data'][0]['embedding']
