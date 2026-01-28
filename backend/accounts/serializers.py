from rest_framework import serializers
from dj_rest_auth.registration.serializers import RegisterSerializer as BaseRegisterSerializer
from .models import User, UserPreferences


class UserPreferencesSerializer(serializers.ModelSerializer):
    """Serializer for user preferences."""
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = UserPreferences
        fields = [
            'theme',
            'timezone',
            'avatar_url',
            'email_announcements',
            'email_grades',
            'email_submissions',
            'email_due_reminders',
        ]

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the User model."""
    preferences = UserPreferencesSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'is_instructor',
            'created_at',
            'preferences',
        ]
        read_only_fields = ['id', 'email', 'created_at']


class RegisterSerializer(BaseRegisterSerializer):
    """Custom registration serializer that includes is_instructor field."""

    username = None  # Remove username field
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    is_instructor = serializers.BooleanField(default=False, required=False)

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data['first_name'] = self.validated_data.get('first_name', '')
        data['last_name'] = self.validated_data.get('last_name', '')
        data['is_instructor'] = self.validated_data.get('is_instructor', False)
        return data

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.is_instructor = self.cleaned_data.get('is_instructor', False)
        user.save()
        return user
