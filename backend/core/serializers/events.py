from rest_framework import serializers
from core.models.events import (
    TriggeredEvent,
)


class TriggeredEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TriggeredEvent
        fields = '__all__'
