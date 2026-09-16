"""
Course-material retrieval via Qdrant, for persona prompts and the resources API.

Carried over from BECSR in the fork and **not wired to anything** until
2026-09-16: it pointed at a collection, `globalstrat_textbook`, that has never
existed on the Qdrant host, so every caller silently received nothing. Three
faults were repaired together, because any one of them alone still left it dead:

* the collection name, host and model were hardcoded, so no deployment could
  point it anywhere -- they are settings now;
* the embedder called `SentenceTransformer('BAAI/bge-m3')` with no
  `local_files_only`, so the first student request would have tried to download
  ~2.2GB from HuggingFace inside the request. Embedding now goes through the
  LiteLLM fleet gateway like every other model call this platform makes;
* a missing collection surfaced as a caught exception per call. It is now
  checked once and reported once, and callers get an empty result immediately
  rather than a stack trace per request.

It stays dead until a collection exists to point it at: set
`TEXTBOOK_COLLECTION` (and ingest one). `PERSONA_TOPICS` below is still BECSR's
CSR vocabulary — re-authoring it for a global-strategy course is advisory-layer
work, not this repair.

Provides:
  - search_textbook(query, section_type, limit)  — general semantic search
  - get_context_for_persona(persona_key, trigger_reason) — course material for LLM persona prompts
  - get_context_for_student_query(student_message) — course material for student reply context
"""
import logging

from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

logger = logging.getLogger(__name__)


def _setting(name, default):
    return getattr(settings, name, default)


def _collection():
    """The collection to search. Empty (the default) means none is configured."""
    return _setting('TEXTBOOK_COLLECTION', '')


def _embedding_model():
    """Gateway alias for the embedder. Must match the collection's vectors."""
    return _setting('TEXTBOOK_EMBEDDING_MODEL', 'bge-m3')

# Persona-to-topic keyword mapping for enriching search queries
PERSONA_TOPICS = {
    'cfo': 'financial ethics profit fiduciary duty shareholder revenue cost-benefit',
    'sustainability': 'ESG environmental sustainability climate corporate social responsibility',
    'stakeholder': 'stakeholder engagement CSR social responsibility community trust',
    'regulatory': 'governance compliance whistleblowing regulation accountability transparency',
    'board_chair': 'corporate governance strategic leadership B-Corp ethics culture',
}


def _get_client():
    """Return a Qdrant client (new instance each call for thread safety)."""
    return QdrantClient(
        host=_setting('QDRANT_HOST', '192.168.50.186'),
        port=int(_setting('QDRANT_PORT', 6333)),
        timeout=10, check_compatibility=False,
    )


_UNAVAILABLE_REPORTED = set()


def _unavailable(reason):
    """Say why this is dead once, not once per student request."""
    if reason not in _UNAVAILABLE_REPORTED:
        _UNAVAILABLE_REPORTED.add(reason)
        logger.warning('Course-material retrieval unavailable: %s', reason)
    return False


def is_available():
    """Whether a configured collection actually exists on the host.

    Checked per call but reported once. A missing collection is a deployment
    state, not an error: the caller shows what it has without the excerpts.
    """
    collection = _collection()
    if not collection:
        return _unavailable('no TEXTBOOK_COLLECTION configured')
    try:
        if not _get_client().collection_exists(collection):
            return _unavailable(f'collection {collection!r} does not exist')
    except Exception as error:                        # noqa: BLE001
        return _unavailable(f'Qdrant unreachable: {error}')
    return True


def _embed(text):
    """Embed through the fleet gateway. Returns None when it cannot."""
    from core.engine import llm_runner

    if not llm_runner.llm_configured():
        _unavailable('no LLM gateway configured for embeddings')
        return None
    try:
        import httpx
        response = httpx.post(
            llm_runner.embeddings_url(),
            headers={'Authorization': f'Bearer {llm_runner._get_key()}',
                     'Content-Type': 'application/json'},
            json={'model': _embedding_model(), 'input': text},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()['data'][0]['embedding']
    except Exception as error:                        # noqa: BLE001
        logger.warning('Course-material embedding failed: %s', error)
        return None


def search_textbook(query, section_type=None, chapter_number=None, limit=10):
    """
    Semantic search over textbook knowledge base.

    Args:
        query: search text
        section_type: optional filter — 'concept', 'definition', 'case_study',
                      'frontline', 'dilemma', 'progress_qa', or list thereof
        chapter_number: optional int or list of ints to filter by chapter
        limit: max results (default 10)

    Returns:
        list of dicts with keys: chunk_id, chapter_number, chapter_title,
        section_type, section_title, content, score
    """
    if not is_available():
        return []
    try:
        client = _get_client()
        vector = _embed(query)
        if vector is None:
            return []

        # Build optional filter
        conditions = []
        if section_type:
            if isinstance(section_type, list):
                conditions.append(FieldCondition(
                    key='section_type', match=MatchAny(any=section_type),
                ))
            else:
                conditions.append(FieldCondition(
                    key='section_type', match=MatchValue(value=section_type),
                ))
        if chapter_number:
            if isinstance(chapter_number, list):
                conditions.append(FieldCondition(
                    key='chapter_number', match=MatchAny(any=chapter_number),
                ))
            else:
                conditions.append(FieldCondition(
                    key='chapter_number', match=MatchValue(value=chapter_number),
                ))

        query_filter = Filter(must=conditions) if conditions else None

        response = client.query_points(
            collection_name=_collection(),
            query=vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )

        results = []
        for hit in response.points:
            p = hit.payload
            results.append({
                'chunk_id': p.get('chunk_id'),
                'chapter_number': p.get('chapter_number'),
                'chapter_title': p.get('chapter_title'),
                'section_type': p.get('section_type'),
                'section_title': p.get('section_title'),
                'content': p.get('content'),
                'word_count': p.get('word_count'),
                'score': round(hit.score, 4),
            })
        return results

    except Exception as e:
        logger.warning(f"Qdrant search failed: {e}")
        return []


def get_context_for_persona(persona_key, trigger_reason):
    """
    Retrieve textbook excerpts relevant to a persona's reaction trigger.
    Returns formatted string for inclusion in LLM prompt, or empty string.
    """
    topic_boost = PERSONA_TOPICS.get(persona_key, '')
    query = f"{trigger_reason} {topic_boost}".strip()
    if not query:
        return ''

    results = search_textbook(
        query,
        section_type=['concept', 'definition', 'case_study'],
        limit=3,
    )
    if not results:
        return ''

    lines = []
    for r in results:
        source = f"Ch.{r['chapter_number']} — {r['section_title']}"
        lines.append(f"[{source}]\n{r['content']}")

    return '\n\n'.join(lines)


def get_context_for_student_query(student_message):
    """
    Retrieve textbook excerpts relevant to a student's question/reply.
    Returns formatted string for inclusion in LLM prompt, or empty string.
    """
    if not student_message or len(student_message.strip()) < 10:
        return ''

    results = search_textbook(student_message, limit=3)
    if not results:
        return ''

    lines = []
    for r in results:
        source = f"Ch.{r['chapter_number']} — {r['section_title']}"
        lines.append(f"[{source}]\n{r['content']}")

    return '\n\n'.join(lines)


def get_textbook_content(section_type=None, chapter_number=None):
    """
    Retrieve all textbook chunks matching filters (non-semantic, scroll-based).
    Used for populating resource pages with categorized content.

    Returns list of dicts sorted by chapter_number, section_title.
    """
    if not is_available():
        return []
    try:
        client = _get_client()

        conditions = []
        if section_type:
            if isinstance(section_type, list):
                conditions.append(FieldCondition(
                    key='section_type', match=MatchAny(any=section_type),
                ))
            else:
                conditions.append(FieldCondition(
                    key='section_type', match=MatchValue(value=section_type),
                ))
        if chapter_number:
            if isinstance(chapter_number, list):
                conditions.append(FieldCondition(
                    key='chapter_number', match=MatchAny(any=chapter_number),
                ))
            else:
                conditions.append(FieldCondition(
                    key='chapter_number', match=MatchValue(value=chapter_number),
                ))

        scroll_filter = Filter(must=conditions) if conditions else None

        all_points = []
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=_collection(),
                scroll_filter=scroll_filter,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            all_points.extend(points)
            if offset is None:
                break

        results = []
        for pt in all_points:
            p = pt.payload
            results.append({
                'chunk_id': p.get('chunk_id'),
                'chapter_number': p.get('chapter_number'),
                'chapter_title': p.get('chapter_title'),
                'section_type': p.get('section_type'),
                'section_title': p.get('section_title'),
                'content': p.get('content'),
                'word_count': p.get('word_count'),
            })

        results.sort(key=lambda r: (r.get('chapter_number', 0), r.get('section_title', '')))
        return results

    except Exception as e:
        logger.warning(f"Qdrant scroll failed: {e}")
        return []
