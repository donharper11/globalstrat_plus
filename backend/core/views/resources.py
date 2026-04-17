"""
Views for textbook knowledge-base search and content retrieval.
"""
import re

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services.textbook_retrieval import search_textbook, get_textbook_content


def _clean_content(text):
    """
    Clean .doc conversion artifacts from textbook chunk text.
    Applied at the API layer so raw Qdrant data stays intact for embedding quality.
    """
    if not text:
        return text

    # Replace Unicode replacement character (U+FFFD) with apostrophe
    text = text.replace('\ufffd', "'")

    # Process line by line
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        # Strip leading bullet markers: "* " and "o " at line start
        if line.startswith('* '):
            line = line[2:]
        elif re.match(r'^o ', line):
            line = line[2:]
        cleaned.append(line)

    text = '\n'.join(cleaned)

    # Collapse 3+ consecutive blank lines into a single blank line
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def _clean_results(results, include_score=False):
    """Apply content cleaning to a list of result dicts."""
    cleaned = []
    for r in results:
        out = {k: v for k, v in r.items() if k != 'score'}
        out['content'] = _clean_content(out.get('content', ''))
        if include_score:
            out['score'] = r.get('score')
        cleaned.append(out)
    return cleaned


class ResourceSearchView(APIView):
    """POST /api/resources/search/ — semantic search over textbook knowledge base."""

    def post(self, request):
        query = request.data.get('query', '').strip()
        if not query:
            return Response(
                {'error': 'query is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        section_type = request.data.get('section_type')  # str or list
        chapter_number = request.data.get('chapter_number')  # int or list
        limit = min(int(request.data.get('limit', 10)), 50)

        results = search_textbook(
            query,
            section_type=section_type,
            chapter_number=chapter_number,
            limit=limit,
        )
        cleaned = _clean_results(results, include_score=False)
        return Response({'results': cleaned, 'count': len(cleaned)})


class ResourceContentView(APIView):
    """GET /api/resources/content/ — retrieve textbook chunks by filter (non-semantic)."""

    def get(self, request):
        section_type = request.query_params.get('section_type')
        chapter_number = request.query_params.get('chapter_number')

        # Parse comma-separated values
        if section_type:
            section_type = [s.strip() for s in section_type.split(',')]
        if chapter_number:
            chapter_number = [int(c.strip()) for c in chapter_number.split(',')]

        results = get_textbook_content(
            section_type=section_type,
            chapter_number=chapter_number,
        )
        cleaned = _clean_results(results, include_score=False)
        return Response({'results': cleaned, 'count': len(cleaned)})
