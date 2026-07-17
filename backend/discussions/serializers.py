from rest_framework import serializers

from accounts.serializers import UserSerializer
from .models import Thread, Reply


class ReplySerializer(serializers.ModelSerializer):
    """Serializer for a single reply."""
    author = UserSerializer(read_only=True)

    class Meta:
        model = Reply
        fields = ['id', 'author', 'content', 'created_at', 'updated_at']


class ReplyCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a reply."""
    class Meta:
        model = Reply
        fields = ['id', 'content']


class ThreadListSerializer(serializers.ModelSerializer):
    """Serializer for listing threads with activity metadata."""
    author = UserSerializer(read_only=True)
    author_name = serializers.SerializerMethodField()
    reply_count = serializers.IntegerField(read_only=True)
    last_activity = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Thread
        fields = [
            'id', 'title', 'author', 'author_name', 'is_pinned', 'is_locked',
            'reply_count', 'last_activity', 'created_at'
        ]

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.email


class ThreadDetailSerializer(serializers.ModelSerializer):
    """Serializer for thread detail, including nested replies."""
    course_code = serializers.CharField(source='course.code', read_only=True)
    author = UserSerializer(read_only=True)
    replies = ReplySerializer(many=True, read_only=True)

    class Meta:
        model = Thread
        fields = [
            'id', 'course_code', 'title', 'content', 'author',
            'is_pinned', 'is_locked', 'created_at', 'updated_at', 'replies'
        ]


class ThreadCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating a thread."""
    class Meta:
        model = Thread
        fields = ['id', 'title', 'content']
