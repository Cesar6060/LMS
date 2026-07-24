from django.conf import settings
from dj_rest_auth.views import PasswordResetView
from PIL import Image
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, parser_classes, throttle_classes,
)
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from core.throttling import ClientIPScopedRateThrottle
from .models import User, UserPreferences
from .serializers import UserSerializer, UserPreferencesSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def registration_disabled(request):
    """Stand-in for the registration endpoint when self-signup is turned off.

    The live site is a public demo — visitors log in as the shared demo student,
    not their own accounts — so registration is disabled. Returning an explicit
    403 (rather than leaving the real endpoint mounted) means no request can
    create an account no matter what payload it carries.
    """
    return Response(
        {'detail': 'Registration is disabled. This is a demo — log in with the demo account.'},
        status=status.HTTP_403_FORBIDDEN,
    )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ClientIPScopedRateThrottle])
def demo_login(request):
    """One-click login as the shared demo student.

    Issues a JWT pair for settings.DEMO_ACCOUNT_EMAIL server-side, so the demo
    password never appears in the client (it's a rotated secret in production).
    The response mirrors dj-rest-auth's login body — access/refresh/user — so
    the frontend consumes it through the exact same code path.
    """
    user = User.objects.filter(
        email=settings.DEMO_ACCOUNT_EMAIL, is_active=True,
    ).first()
    if user is None:
        return Response(
            {'detail': 'The demo account is not available. If you run this '
                       'instance, seed it with `manage.py seed_demo_account`.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user, context={'request': request}).data,
    })


# @api_view exposes the generated view class as `.cls`; ScopedRateThrottle
# reads its scope from there. Rate comes from THROTTLE_DEMO_LOGIN (unset =
# unlimited, same env-gated pattern as THROTTLE_ANON).
demo_login.cls.throttle_scope = 'demo_login'


class ThrottledPasswordResetView(PasswordResetView):
    """dj-rest-auth's password reset with its own scoped rate limit.

    The endpoint is anonymous and (since Phase 47) sends real email in
    production, so it gets a tight per-IP rate on top of the general anon
    throttle. Rate comes from THROTTLE_PASSWORD_RESET (unset = unlimited,
    same env-gated pattern as THROTTLE_DEMO_LOGIN). Mounted in accounts.urls
    ahead of the dj_rest_auth include so it shadows the stock view.
    """
    throttle_classes = [ClientIPScopedRateThrottle]
    throttle_scope = 'password_reset'


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    Get or update the current user's profile.
    """
    user = request.user

    if request.method == 'GET':
        serializer = UserSerializer(user, context={'request': request})
        return Response(serializer.data)

    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = UserSerializer(user, data=request.data, partial=partial, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_settings(request):
    """
    Get or update user preferences/settings.
    """
    # Ensure preferences exist (should be created by signal, but just in case)
    preferences, _ = UserPreferences.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        serializer = UserPreferencesSerializer(preferences, context={'request': request})
        return Response(serializer.data)

    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = UserPreferencesSerializer(
            preferences,
            data=request.data,
            partial=partial,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_avatar(request):
    """
    Upload or update user avatar.

    The file is validated on size, extension, content type, and actual image
    bytes before it is stored — ImageField's own validation only runs through
    full_clean(), which save() skips, so an .svg or a renamed .html would
    otherwise land in media and be served same-origin under DEBUG.
    """
    preferences, _ = UserPreferences.objects.get_or_create(user=request.user)

    if 'avatar' not in request.FILES:
        return Response(
            {'error': 'No avatar file provided'},
            status=status.HTTP_400_BAD_REQUEST
        )

    avatar_file = request.FILES['avatar']
    if avatar_file.size > settings.AVATAR_MAX_UPLOAD_BYTES:
        limit_mb = settings.AVATAR_MAX_UPLOAD_BYTES // (1024 * 1024)
        return Response(
            {'error': f'Avatar must be {limit_mb}MB or smaller.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Allowed image extensions (whitelist). svg is deliberately excluded: it can
    # carry inline scripts and media is served same-origin under DEBUG, so an
    # uploaded .svg is a stored-XSS vector. Same rationale as lesson attachments.
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ALLOWED_CONTENT_TYPES = {
        'image/png', 'image/jpeg', 'image/gif', 'image/webp',
    }

    file_ext = (
        avatar_file.name.rsplit('.', 1)[-1].lower()
        if '.' in (avatar_file.name or '') else ''
    )
    if not file_ext or file_ext not in ALLOWED_EXTENSIONS:
        return Response(
            {'error': f'Avatar type ".{file_ext}" is not allowed. '
                      f'Allowed types: {", ".join(sorted(ALLOWED_EXTENSIONS))}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if (avatar_file.content_type or '').lower() not in ALLOWED_CONTENT_TYPES:
        return Response(
            {'error': 'Avatar must be a PNG, JPEG, GIF, or WebP image.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Extension and content type are both client-supplied, so confirm the bytes
    # really are an image. Pillow's verify() raises a broad, undocumented set of
    # exceptions on malformed input (OSError, SyntaxError, DecompressionBomb,
    # struct errors from plugins), so catch Exception rather than guess.
    #
    # verify() alone is NOT enough: it accepts anything Pillow can decode, so
    # TIFF/BMP/PPM bytes named ".png" with content_type "image/png" sail
    # through and the allowlist above buys nothing. That matters because the
    # allowlist's real job is bounding which Pillow *decoders* untrusted bytes
    # can reach — the less-common codecs are where most of the ~20 CVEs behind
    # this phase's Pillow bump live. So pin the detected format too.
    #
    # `.format` must be read BEFORE verify(), which leaves the Image unusable.
    EXTENSION_FORMATS = {
        'png': {'PNG'},
        'jpg': {'JPEG'},
        'jpeg': {'JPEG'},
        'gif': {'GIF'},
        'webp': {'WEBP'},
    }
    try:
        image = Image.open(avatar_file)
        detected_format = image.format
        image.verify()
    except Exception:
        return Response(
            {'error': 'Avatar is not a valid image file.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if detected_format not in EXTENSION_FORMATS[file_ext]:
        return Response(
            {'error': f'Avatar contents are {detected_format or "an unknown format"}, '
                      f'which does not match its ".{file_ext}" extension.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # verify() consumes the file and leaves it unusable — rewind before saving.
    avatar_file.seek(0)

    # Delete old avatar if exists
    if preferences.avatar:
        preferences.avatar.delete(save=False)

    preferences.avatar = avatar_file
    preferences.save()

    serializer = UserPreferencesSerializer(preferences, context={'request': request})
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_avatar(request):
    """
    Delete user avatar.
    """
    preferences, _ = UserPreferences.objects.get_or_create(user=request.user)

    if preferences.avatar:
        preferences.avatar.delete(save=True)

    serializer = UserPreferencesSerializer(preferences, context={'request': request})
    return Response(serializer.data)
