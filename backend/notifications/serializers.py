from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'type', 'title', 'message',
            'is_read', 'related_url', 'created_at'
        ]
        read_only_fields = ['recipient', 'type', 'title', 'message', 'related_url', 'created_at']
