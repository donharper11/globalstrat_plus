"""
CC-7/CC-11: RAG research query and event API views.
"""
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team, Round, TeamMember
from core.models.decisions import DecisionSubmission, DecisionEventResponse
from core.models.results import EventInstance
from core.models.scenario import EventResponseDefinition
from core.engine.utils import get_config
from core.models import User


class IsTeamMember(permissions.BasePermission):
    def has_permission(self, request, view):
        team_id = view.kwargs.get('team_id')
        # Identity comes only from the signed JWT. The X-User-Id header used
        # to be accepted here, which allowed impersonating any user.
        from core.utils.auth_context import get_request_user
        user = get_request_user(request)
        if not user:
            return False
        role = (user.role or '').lower()
        if role in ('instructor', 'admin'):
            return True
        from core.models import Enrollment
        if Enrollment.objects.filter(
            user_id=user.user_id, team_id=team_id, is_active=True,
        ).exists():
            return True
        return TeamMember.objects.filter(
            team_id=team_id, user_id=user.user_id,
        ).exists()


# ---------------------------------------------------------------------------
# Active Events Endpoint
# ---------------------------------------------------------------------------

class ActiveEventsView(APIView):
    """
    GET /api/games/{game_id}/teams/{team_id}/events/active/
    Returns events fired this round: response_required + informational.
    """

    def get(self, request, game_id, team_id):
        try:
            game = Game.objects.get(id=game_id)
        except Game.DoesNotExist:
            return Response({'error': 'Game not found.'}, status=404)

        current_round = game.current_round

        events = EventInstance.objects.filter(
            game=game,
            round_number=current_round,
        ).select_related('event_template', 'target_market')

        response_required = []
        informational = []

        for event in events:
            template = event.event_template
            event_data = {
                'id': event.id,
                'name': template.name,
                'narrative': event.narrative,
                'category': template.category,
                'severity': template.severity,
                'market': event.target_market.name if event.target_market else 'Global',
                'response_required': template.response_required,
                'response_deadline_rounds': template.response_deadline_rounds,
            }

            if template.response_required:
                responses = EventResponseDefinition.objects.filter(
                    event_template=template,
                )
                event_data['response_options'] = [
                    {
                        'id': r.id,
                        'name': r.name,
                        'description': r.description,
                        'cost': float(r.cost),
                    }
                    for r in responses
                ]
                submission = DecisionSubmission.objects.filter(
                    team_id=team_id,
                    round__game=game,
                    round__round_number=current_round,
                ).first()
                if submission:
                    existing_response = DecisionEventResponse.objects.filter(
                        submission=submission,
                        event_instance=event,
                    ).first()
                    event_data['team_response_id'] = (
                        existing_response.response_id if existing_response else None
                    )
                else:
                    event_data['team_response_id'] = None

                response_required.append(event_data)
            else:
                informational.append(event_data)

        return Response({
            'response_required': response_required,
            'informational': informational,
        })


# ---------------------------------------------------------------------------
# Event History Endpoint
# ---------------------------------------------------------------------------

class EventHistoryView(APIView):
    """
    GET /api/games/{game_id}/teams/{team_id}/events/history/
    Returns all events fired across all rounds for this game.
    """

    def get(self, request, game_id, team_id):
        try:
            game = Game.objects.get(id=game_id)
        except Game.DoesNotExist:
            return Response({'error': 'Game not found.'}, status=404)

        events = EventInstance.objects.filter(
            game=game,
        ).select_related(
            'event_template', 'target_market',
        ).order_by('round_number', 'created_at')

        result = []
        for event in events:
            template = event.event_template

            team_response = None
            submission = DecisionSubmission.objects.filter(
                team_id=team_id,
                round__game=game,
                round__round_number=event.round_number,
            ).first()
            if submission:
                resp = DecisionEventResponse.objects.filter(
                    submission=submission,
                    event_instance=event,
                ).select_related('response').first()
                if resp:
                    team_response = {
                        'response_id': resp.response_id,
                        'response_name': resp.response.name,
                        'cost': float(resp.response.cost),
                    }

            result.append({
                'id': event.id,
                'round_number': event.round_number,
                'name': template.name,
                'narrative': event.narrative,
                'category': template.category,
                'severity': template.severity,
                'market': event.target_market.name if event.target_market else 'Global',
                'response_required': template.response_required,
                'team_response': team_response,
            })

        return Response(result)


# ---------------------------------------------------------------------------
# Research Query Endpoint (CC-11 enhanced)
# ---------------------------------------------------------------------------

# Market keyword expansions for better retrieval
_MARKET_EXPANSIONS = {
    'asia': 'East Asia APAC China emerging market',
    'europe': 'Western Europe EU regulation sustainability',
    'america': 'North America USA mature market',
    'na': 'North America USA',
    'eu': 'Europe EU',
    'apac': 'East Asia APAC',
    'africa': 'Africa emerging market developing',
    'afr': 'Africa emerging market developing',
    'latin': 'Latin America Brazil emerging market',
    'south america': 'South America Latin America Brazil emerging market',
    'latam': 'Latin America South America Brazil emerging market',
}


def enhance_query(raw_query, team_context=None):
    """
    Add context to the raw query for better embedding match.
    """
    parts = [raw_query]

    for keyword, expansion in _MARKET_EXPANSIONS.items():
        if keyword in raw_query.lower():
            parts.append(expansion)
            break

    if team_context:
        markets = team_context.get('active_markets', [])
        if markets:
            parts.append(f"Operating in: {', '.join(markets)}")

    return ' '.join(parts)


class ResearchQueryView(APIView):
    """
    POST /api/games/{game_id}/teams/{team_id}/research/query/
    Query the RAG article collection for market intelligence.
    """

    def post(self, request, game_id, team_id):
        try:
            game = Game.objects.get(id=game_id)
            team = Team.objects.get(id=team_id)
        except (Game.DoesNotExist, Team.DoesNotExist):
            return Response({'error': 'Game or team not found.'}, status=404)

        # Check RAG is enabled
        rag_enabled = get_config(game.scenario, 'rag_enabled', False, bool)
        if not rag_enabled:
            return Response(
                {'error': 'Market research AI is not enabled for this scenario.'},
                status=400,
            )

        query_text = request.data.get('query', '').strip()
        if not query_text:
            return Response({'error': 'Query text is required.'}, status=400)

        # Check query limit per round
        from core.models.rag import ResearchQueryLog
        max_queries = get_config(
            game.scenario, 'max_research_queries_per_round', 5, int,
        )
        existing_queries = ResearchQueryLog.objects.filter(
            team=team,
            round_number=game.current_round,
        ).count()
        if existing_queries >= max_queries:
            return Response(
                {'error': f'Query limit reached ({max_queries} per round).'},
                status=429,
            )

        try:
            # Build team context for query enhancement
            from core.models.team_state import TeamMarketPresence
            team_context = {
                'active_markets': list(
                    TeamMarketPresence.objects.filter(
                        team=team, status='active',
                    ).values_list('market__name', flat=True)
                ),
            }

            # Enhance query
            enhanced_query = enhance_query(query_text, team_context)

            # Translate query for English-only embedding models (Part D4)
            from core.rag.embeddings import get_embedding, translate_query_if_needed
            from core.utils.localization import get_team_language
            language = get_team_language(team)
            embedding_query = translate_query_if_needed(enhanced_query, language)

            # Generate embedding
            query_embedding = get_embedding(embedding_query)

            # Search Qdrant
            from core.rag.client import search_articles
            results = search_articles(query_embedding, limit=5)

            if not results:
                response_text = (
                    "No relevant research found for this query. "
                    "Try broadening your search terms or asking about specific markets, "
                    "entry strategies, or competitive dynamics."
                )
            else:
                response_text = synthesize_research_brief(
                    query_text, results, team_context,
                    language=language,
                )

            # Log the query
            ResearchQueryLog.objects.create(
                team=team,
                round_number=game.current_round,
                query_text=query_text,
                response_text=response_text,
                source_tags_used=','.join(set(
                    tag for r in results for tag in r.get('tags', [])
                )),
            )

            return Response({
                'query': query_text,
                'response': response_text,
                'sources_count': len(results),
                'queries_remaining': max_queries - existing_queries - 1,
            })

        except Exception as e:
            return Response(
                {'error': f'Research system unavailable: {str(e)}'},
                status=503,
            )


# ---------------------------------------------------------------------------
# Research brief synthesis (CC-11 enhanced)
# ---------------------------------------------------------------------------

def synthesize_research_brief(query, search_results, team_context=None,
                              language='en'):
    """
    Generate an intelligence brief from Qdrant search results.
    Uses DashScope/Qwen with structured prompting.
    Falls back to structured excerpts if LLM is unavailable.
    """
    from django.conf import settings

    if not settings.DASHSCOPE_API_KEY:
        return _fallback_brief(search_results)

    try:
        import dashscope
        from dashscope import Generation
        dashscope.api_key = settings.DASHSCOPE_API_KEY

        # Build context from search results
        context_parts = []
        for i, result in enumerate(search_results[:5]):
            source = result.get('title', result.get('source', 'Unknown'))
            section = result.get('section', '')
            text = result['text'][:600]
            context_parts.append(f"Source {i+1} [{source}, {section}]:\n{text}")
        context = "\n\n---\n\n".join(context_parts)

        # Build team context string
        team_info = ""
        if team_context:
            markets = ', '.join(team_context.get('active_markets', []))
            if markets:
                team_info = f"\nThe team currently operates in: {markets}."

        system_prompt = (
            "You are a strategic market research analyst at a global consulting firm, "
            "providing intelligence briefs to an executive team managing an international "
            "technology company. Your briefs must be:\n"
            "- Concise: 4-6 sentences maximum\n"
            "- Actionable: focus on implications for strategic decisions\n"
            "- Grounded: base insights on the provided research sources\n"
            "- Professional: write as 'Our research indicates...' or 'Market analysis suggests...'\n"
            "- Balanced: acknowledge uncertainty and competing perspectives where they exist\n\n"
            "Do NOT cite specific article titles or authors. "
            "Do NOT say 'according to Source 1' — synthesize across sources naturally. "
            "Do NOT provide generic business advice — be specific to the question asked."
        )

        from core.engine.llm_runner import build_language_instruction
        lang_instruction = build_language_instruction(language)

        user_prompt = (
            f"Executive query: {query}\n"
            f"{team_info}\n\n"
            f"Research sources:\n{context}\n\n"
            f"Provide a concise intelligence brief addressing the query."
            + lang_instruction
        )

        response = Generation.call(
            model=settings.DASHSCOPE_MODEL,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            max_tokens=400,
            temperature=0.3,
        )

        return response.output.text

    except Exception:
        return _fallback_brief(search_results)


def _fallback_brief(search_results):
    """Fallback when LLM is unavailable — return structured excerpts."""
    parts = []
    for r in search_results[:3]:
        title = r.get('title', 'Research source')
        text = r['text'][:250]
        parts.append(f"**{title}:** {text}...")
    return "Research excerpts (AI synthesis unavailable):\n\n" + "\n\n".join(parts)
