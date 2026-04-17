"""
Qdrant vector database client for RAG article retrieval.
CC-7 infrastructure — CC-11 handles actual article ingestion.
"""
from django.conf import settings


def get_qdrant_client():
    """Get a Qdrant client instance."""
    from qdrant_client import QdrantClient
    return QdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
        check_compatibility=False,
    )


def ensure_collection():
    """Create the collection if it doesn't exist."""
    from qdrant_client.models import Distance, VectorParams

    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]

    if settings.QDRANT_COLLECTION not in collections:
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
        return True  # Created
    return False  # Already exists


def search_articles(query_embedding, tags=None, limit=5):
    """
    Search the article collection.
    Optionally filter by rag_source_tags.
    Returns list of dicts with text, source, title, tags, score.
    """
    client = get_qdrant_client()

    filter_conditions = None
    if tags:
        from qdrant_client.models import Filter, FieldCondition, MatchAny
        filter_conditions = Filter(
            should=[
                FieldCondition(
                    key="tags",
                    match=MatchAny(any=tags),
                )
            ]
        )

    response = client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=query_embedding,
        query_filter=filter_conditions,
        limit=limit,
    )

    return [
        {
            'text': hit.payload.get('text', ''),
            'source': hit.payload.get('source', ''),
            'title': hit.payload.get('title', ''),
            'tags': hit.payload.get('tags', []),
            'score': hit.score,
        }
        for hit in response.points
    ]
