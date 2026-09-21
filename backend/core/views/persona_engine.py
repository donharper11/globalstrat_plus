"""
Views for the unified Persona Messaging system.
- Reply to a persona thread
- Start a new consultation
- List personas
- Get thread messages
- Get consultation usage
"""
from rest_framework import status
from rest_framework.response import Response
from core.utils.participant_messages import (
    localise_refusal, participant_refusal)
from rest_framework.views import APIView

from core.models.messaging import Message
from core.serializers.messaging import MessageSerializer
from core.services.persona_engine import (
    reply_to_thread, start_consultation, get_consultation_usage, PERSONAS,
)


class PersonaReplyView(APIView):
    """
    POST: Reply to a persona message thread.
    Body: { team_id, message_id, reply_text }
    """

    def post(self, request):
        team_id = request.data.get('team_id')
        message_id = request.data.get('message_id')
        reply_text = request.data.get('reply_text', '')

        if not team_id or not message_id or not reply_text.strip():
            # Which sentence, not whether: the page supplies the two ids, the
            # student supplies the text.
            return Response(
                participant_refusal(
                    request, 'request_incomplete'
                    if not team_id or not message_id
                    else 'persona_reply_required'),
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = reply_to_thread(
            team_id=int(team_id),
            message_id=int(message_id),
            reply_text=reply_text.strip(),
        )

        # The service knows no request; its refusal gets its language here.
        localise_refusal(request, result)
        if 'error' in result and 'student_message' not in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        if 'error' in result:
            return Response(result, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(result)


class PersonaConsultView(APIView):
    """
    POST: Start a new consultation with a persona.
    Body: { team_id, persona_key, question }
    """

    def post(self, request):
        team_id = request.data.get('team_id')
        persona_key = request.data.get('persona_key')
        question = request.data.get('question', '')

        if not team_id or not persona_key or not question.strip():
            return Response(
                participant_refusal(
                    request, 'request_incomplete'
                    if not team_id or not persona_key
                    else 'persona_question_required'),
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = start_consultation(
            team_id=int(team_id),
            persona_key=persona_key,
            question=question.strip(),
        )

        # The service knows no request; its refusal gets its language here.
        localise_refusal(request, result)
        if 'error' in result and 'student_message' not in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        if 'error' in result:
            return Response(result, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(result)


class PersonaListView(APIView):
    """GET: List available personas."""

    def get(self, request):
        result = []
        for key, persona in PERSONAS.items():
            result.append({
                'key': key,
                'name': persona['name'],
                'title': persona['title'],
                'avatar': persona['avatar'],
            })
        return Response(result)


class ThreadMessagesView(APIView):
    """GET: Get all messages in a thread."""

    def get(self, request, thread_root_id):
        messages = Message.objects.filter(
            thread_root_id=thread_root_id
        ).order_by('created_at')
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)


class ConsultationUsageView(APIView):
    """GET: Get consultation usage for a team."""

    def get(self, request):
        team_id = request.query_params.get('team_id')
        if not team_id:
            return Response(
                participant_refusal(request, 'request_incomplete'),
                status=status.HTTP_400_BAD_REQUEST,
            )
        usage = get_consultation_usage(int(team_id))
        return Response(usage)
