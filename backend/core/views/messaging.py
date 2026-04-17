from rest_framework import viewsets
from core.views.mixins import InstanceScopedMixin

from core.models.messaging import (
    Message, MessageResponse, MessageThread,
    NotificationLog, TeamNotification, Feedback,
)
from core.serializers.messaging import (
    MessageSerializer, MessageResponseSerializer,
    MessageThreadSerializer,
    NotificationLogSerializer, TeamNotificationSerializer,
    FeedbackSerializer,
)


class MessageViewSet(InstanceScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        recipient_type = self.request.query_params.get('recipient_type')
        recipient_id = self.request.query_params.get('recipient_id')
        sender_type = self.request.query_params.get('sender_type')
        persona_key = self.request.query_params.get('persona_key')
        severity = self.request.query_params.get('severity')
        source = self.request.query_params.get('source')
        round_number = self.request.query_params.get('round_number')
        if recipient_type:
            qs = qs.filter(recipient_type=recipient_type)
        if recipient_id:
            qs = qs.filter(recipient_id=recipient_id)
        if sender_type:
            qs = qs.filter(sender_type=sender_type)
        if persona_key:
            qs = qs.filter(persona_key=persona_key)
        if severity:
            qs = qs.filter(severity=severity)
        if source:
            qs = qs.filter(source=source)
        if round_number:
            qs = qs.filter(round_number=round_number)
        return qs.order_by('-created_at')


class MessageResponseViewSet(viewsets.ModelViewSet):
    queryset = MessageResponse.objects.all()
    serializer_class = MessageResponseSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        message_id = self.request.query_params.get('message_id')
        team_id = self.request.query_params.get('team_id')
        if message_id:
            qs = qs.filter(message_id=message_id)
        if team_id:
            qs = qs.filter(team_id=team_id)
        return qs


class MessageThreadViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MessageThread.objects.all()
    serializer_class = MessageThreadSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        thread_status = self.request.query_params.get('thread_status')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        if thread_status:
            qs = qs.filter(thread_status=thread_status)
        return qs


class TeamNotificationViewSet(InstanceScopedMixin, viewsets.ModelViewSet):
    queryset = TeamNotification.objects.all()
    serializer_class = TeamNotificationSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        is_read = self.request.query_params.get('is_read')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if is_read is not None and is_read != '':
            qs = qs.filter(is_read=is_read.lower() in ('true', '1'))
        return qs


class NotificationLogViewSet(InstanceScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = NotificationLog.objects.all()
    serializer_class = NotificationLogSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        recipient_id = self.request.query_params.get('recipient_id')
        round_id = self.request.query_params.get('round_id')
        if recipient_id:
            qs = qs.filter(recipient_id=recipient_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        return qs


class FeedbackViewSet(InstanceScopedMixin, viewsets.ModelViewSet):
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        return qs
