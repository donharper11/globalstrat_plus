"""
Textbook knowledge-base retrieval via Qdrant.

Collection: globalstrat_textbook @ 192.168.50.186:6333
Embedding model: BAAI/bge-m3 (1024-dim, cosine)

Provides:
  - search_textbook(query, section_type, limit)  — general semantic search
  - get_context_for_persona(persona_key, trigger_reason) — course material for LLM persona prompts
  - get_context_for_student_query(student_message) — course material for student reply context
"""
import logging
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

logger = logging.getLogger(__name__)

QDRANT_HOST = '192.168.50.186'
QDRANT_PORT = 6333
COLLECTION = 'globalstrat_textbook'
EMBEDDING_MODEL = 'BAAI/bge-m3'
EMBEDDING_DIM = 1024

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
        host=QDRANT_HOST, port=QDRANT_PORT,
        timeout=10, check_compatibility=False,
    )


@lru_cache(maxsize=1)
def _get_encoder():
    """Lazy-load the sentence-transformers encoder (cached singleton)."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBEDDING_MODEL)


def _embed(text):
    """Embed a single text string, return list of floats."""
    model = _get_encoder()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


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
    try:
        client = _get_client()
        vector = _embed(query)

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
            collection_name=COLLECTION,
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
                collection_name=COLLECTION,
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
