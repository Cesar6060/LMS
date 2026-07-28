import logging

from allauth.account.forms import default_token_generator
from allauth.account.utils import user_pk_to_url_str
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from rest_framework import serializers
from dj_rest_auth.forms import AllAuthPasswordResetForm
from dj_rest_auth.registration.serializers import RegisterSerializer as BaseRegisterSerializer
from dj_rest_auth.serializers import (
    PasswordChangeSerializer as BasePasswordChangeSerializer,
    PasswordResetConfirmSerializer as BasePasswordResetConfirmSerializer,
    PasswordResetSerializer as BasePasswordResetSerializer,
)
from core.demo import is_demo_user, require_not_demo
from .models import User, UserPreferences

logger = logging.getLogger(__name__)


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
    # Lets the frontend know it's rendering the shared demo session (banner,
    # disabled forms). Enforcement never trusts this field — it's derived
    # server-side and read-only.
    is_demo = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'is_instructor',
            'is_demo',
            'created_at',
            'preferences',
        ]
        # is_instructor MUST stay read-only: this serializer backs the
        # self-service profile PUT/PATCH, and a writable role field would let any
        # logged-in user (including the shared demo student) promote themselves to
        # instructor. Role changes happen only via Django admin.
        read_only_fields = ['id', 'email', 'is_instructor', 'created_at']

    def get_is_demo(self, obj):
        return is_demo_user(obj)

    def update(self, instance, validated_data):
        # The choke point every profile-write route shares. Guarding the
        # views alone was not enough: dj-rest-auth mounts UserDetailsView
        # with an optional-slash regex, so /api/auth/user (no slash) routed
        # around the guarded shadow and renamed the shared demo account.
        # Enforcing here means any future route reusing this serializer
        # inherits the block.
        require_not_demo(instance)
        return super().update(instance, validated_data)


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


class FrontendPasswordResetForm(AllAuthPasswordResetForm):
    """Reset form that emails a frontend link using the branded templates.

    The stock AllAuthPasswordResetForm sends allauth's bare
    `account/email/password_reset_key` template with a link into Django's own
    `/reset/<uid>/<token>/` view — a page that doesn't exist for API clients.
    This override keeps the parts that must stay allauth-compatible (uid is
    base36 via `user_pk_to_url_str`, token from allauth's generator — exactly
    what /api/auth/password/reset/confirm/ decodes) and swaps only the email:
    branded templates under templates/registration/ whose link points at the
    frontend's /reset-password page.
    """

    def save(self, request, **kwargs):
        token_generator = kwargs.get('token_generator', default_token_generator)
        extra_context = kwargs.get('extra_email_context') or {}
        frontend_url = extra_context.get('frontend_url', settings.FRONTEND_URL)

        for user in self.users:
            # The demo account's mailbox isn't ours (jdoe@demo.com), and its
            # password is operator-managed — never email a working reset link
            # for it. Silently skipping keeps the endpoint's response identical
            # to the unknown-email case (no account enumeration).
            if is_demo_user(user):
                logger.warning(
                    'Refusing to send password-reset email for the demo account.'
                )
                continue

            uid = user_pk_to_url_str(user)
            token = token_generator.make_token(user)
            context = {
                'user': user,
                'uid': uid,
                'token': token,
                'reset_url': (
                    f'{frontend_url}/reset-password?uid={uid}&token={token}'
                ),
                **extra_context,
            }

            subject = render_to_string(
                'registration/password_reset_subject.txt', context)
            # Subject must be a single line or SMTP rejects it.
            subject = ' '.join(subject.split())
            text_body = render_to_string(
                'registration/password_reset_email.txt', context)
            html_body = render_to_string(
                'registration/password_reset_email.html', context)

            message = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            message.attach_alternative(html_body, 'text/html')
            message.send()

        return self.cleaned_data['email']


class PasswordResetSerializer(BasePasswordResetSerializer):
    """Password reset that emails the frontend's /reset-password link.

    Registered as REST_AUTH['PASSWORD_RESET_SERIALIZER'].
    """

    @property
    def password_reset_form_class(self):
        return FrontendPasswordResetForm

    def get_email_options(self):
        return {
            'extra_email_context': {'frontend_url': settings.FRONTEND_URL},
        }


class ProtectedPasswordChangeSerializer(BasePasswordChangeSerializer):
    """Password change that refuses to touch the shared public demo account.

    The demo credentials are published, so without this any visitor could change
    the password and lock everyone else out of the demo. All other users change
    their password normally.

    Denies with the standard demo_blocked 403 (phase 56) rather than a 400
    validation error, so the frontend's central handler shows the same
    friendly message here as on every other blocked demo write.
    """

    def validate(self, attrs):
        user = getattr(self, 'user', None) or self.context['request'].user
        require_not_demo(user)
        return super().validate(attrs)


class ProtectedPasswordResetConfirmSerializer(BasePasswordResetConfirmSerializer):
    """Reset-confirm that refuses to touch the demo account's password.

    The sibling of ProtectedPasswordChangeSerializer, and the same
    invariant: no request may change the shared demo password, or one
    visitor locks out every other until an operator re-runs
    seed_demo_account. FrontendPasswordResetForm already declines to *email*
    the demo account a reset link, but that only closes the delivery path —
    this closes the write itself, so any token that reaches this endpoint by
    another route (log leak, a future admin "resend link" tool, a reused
    SECRET_KEY) still can't land. Found by the phase-56 adversarial pass.
    """

    def validate(self, attrs):
        # super().validate() resolves self.user from the uid; run it first so
        # an invalid uid/token still fails as a bad token rather than
        # revealing anything about the demo account.
        attrs = super().validate(attrs)
        require_not_demo(self.user)
        return attrs
