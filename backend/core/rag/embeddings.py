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
        import httpx
        api_key = getattr(settings, 'DASHSCOPE_API_KEY', '')
        if not api_key:
            return query

        url = getattr(
            settings, 'DASHSCOPE_COMPATIBLE_URL',
            'https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions',
        )
        model = getattr(settings, 'DASHSCOPE_MODEL', 'qwen3-max-preview')

        response = httpx.post(
            url,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': model,
                'messages': [
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
                'max_tokens': 100,
                'temperature': 0.0,
            },
            timeout=10,
        )
        response.raise_for_status()
        translated = (
            response.json()
            .get('choices', [{}])[0]
            .get('message', {})
            .get('content', '')
            .strip()
        )
        if translated:
            logger.debug(f"RAG query translated: '{query}' -> '{translated}'")
            return translated
    except Exception as e:
        logger.warning(f"Query translation failed, using original: {e}")

    return query


def get_embedding(text):
    """
    Generate an embedding for the given text.
    Uses sentence-transformers (local path or HuggingFace model) or DashScope API.
    Local models: paths starting with '/' or HuggingFace IDs like 'BAAI/bge-m3'.
    DashScope: model names not matching the above patterns.
    """
    model_name = settings.EMBEDDING_MODEL
    # Use local embedding for filesystem paths or known HuggingFace models
    if model_name.startswith('/') or model_name.startswith('BAAI/') or model_name.startswith('sentence-transformers/'):
        return _local_embedding(text)
    else:
        return _dashscope_embedding(text)


def _local_embedding(text):
    """Use sentence-transformers for local embedding."""
    from sentence_transformers import SentenceTransformer
    # Cache the model as a function-level singleton
    if not hasattr(_local_embedding, '_model'):
        _local_embedding._model = SentenceTransformer(settings.EMBEDDING_MODEL)
    model = _local_embedding._model
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def _dashscope_embedding(text):
    """Use DashScope API for embedding."""
    import dashscope
    from dashscope import TextEmbedding
    dashscope.api_key = settings.DASHSCOPE_API_KEY
    result = TextEmbedding.call(
        model=settings.EMBEDDING_MODEL,
        input=text,
    )
    return result.output['embeddings'][0]['embedding']
