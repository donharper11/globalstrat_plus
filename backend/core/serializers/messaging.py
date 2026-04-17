from rest_framework import serializers
from core.models.messaging import (
    Message, MessageResponse, MessageThread,
    NotificationLog, TeamNotification, Feedback,
)


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'


class MessageResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageResponse
        fields = '__all__'


class MessageThreadSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageThread
        fields = '__all__'


class TeamNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamNotification
        fields = '__all__'


class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = '__all__'


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = '__all__'
