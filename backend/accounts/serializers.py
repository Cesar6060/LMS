from django.conf import settings
from rest_framework import serializers
from dj_rest_auth.registration.serializers import RegisterSerializer as BaseRegisterSerializer
from dj_rest_auth.serializers import PasswordChangeSerializer as BasePasswordChangeSerializer
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
        # is_instructor MUST stay read-only: this serializer backs the
        # self-service profile PUT/PATCH, and a writable role field would let any
        # logged-in user (including the shared demo student) promote themselves to
        # instructor. Role changes happen only via Django admin.
        read_only_fields = ['id', 'email', 'is_instructor', 'created_at']


class RegisterSerializer(BaseRegisterSerializer):
    """Custom registration serializer with first/last name support.

    Note: is_instructor is intentionally NOT accepted here for security.
    Only Django admins can promote users to instructor status.
    """

    username = None  # Remove username field
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data['first_name'] = self.validated_data.get('first_name', '')
        data['last_name'] = self.validated_data.get('last_name', '')
        return data

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.save()
        return user


class ProtectedPasswordChangeSerializer(BasePasswordChangeSerializer):
    """Password change that refuses to touch the shared public demo account.

    The demo credentials are published, so without this any visitor could change
    the password and lock everyone else out of the demo. All other users change
    their password normally.
    """

    def validate(self, attrs):
        user = getattr(self, 'user', None) or self.context['request'].user
        if user and user.email == settings.DEMO_ACCOUNT_EMAIL:
            raise serializers.ValidationError(
                "The demo account's password is fixed and cannot be changed."
            )
        return super().validate(attrs)
