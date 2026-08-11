from django.conf import settings
from dj_rest_auth.views import (
    LoginView, PasswordResetConfirmView, PasswordResetView, UserDetailsView,
)
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, parser_classes, throttle_classes,
)
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from core.demo import require_not_demo
from core.permissions import NotDemoAccountForWrites
from core.throttling import (
    GLOBAL_THROTTLES, ClientIPScopedRateThrottle, LoginEmailRateThrottle,
)
from core.uploads import verify_image
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
@throttle_classes([ClientIPScopedRateThrottle, *GLOBAL_THROTTLES])
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
# reads its scope from there. Rate comes from THROTTLE_DEMO_LOGIN, which since
# phase 73 defaults to a real value rather than to unlimited.
demo_login.cls.throttle_scope = 'demo_login'


class DemoSafeUserDetailsView(UserDetailsView):
    """dj-rest-auth's /api/auth/user/ with demo writes blocked.

    The route uses the same UserSerializer as /api/auth/profile/, so without
    this shadow a demo visitor blocked on the profile endpoint could rename
    the shared account through this one instead. Mounted in accounts.urls
    ahead of the dj_rest_auth include.
    """
    permission_classes = [IsAuthenticated, NotDemoAccountForWrites]


class ThrottledPasswordResetView(PasswordResetView):
    """dj-rest-auth's password reset with its own scoped rate limit.

    The endpoint is anonymous and (since Phase 47) sends real email in
    production, so it gets a tight per-IP rate on top of the general anon
    throttle. Rate comes from THROTTLE_PASSWORD_RESET. Mounted in accounts.urls
    ahead of the dj_rest_auth include so it shadows the stock view.
    """
    throttle_classes = [ClientIPScopedRateThrottle, *GLOBAL_THROTTLES]
    throttle_scope = 'password_reset'


class ThrottledPasswordResetConfirmView(PasswordResetConfirmView):
    """dj-rest-auth's reset *confirm* with its own scoped rate limit.

    Phase 73. Requesting a reset was throttled from phase 47; submitting the
    emailed token was not, so the token was open to brute force at whatever the
    general anon rate happened to be — and that rate defaulted to unlimited
    until this phase. A guessed token is a full account takeover, so it gets the
    same tight ceiling as requesting one.
    """
    throttle_classes = [ClientIPScopedRateThrottle, *GLOBAL_THROTTLES]
    throttle_scope = 'password_reset_confirm'


class ThrottledLoginView(LoginView):
    """dj-rest-auth's login, capped per source address AND per account.

    Phase 73. Nothing capped password guessing here before: there was no scoped
    throttle, and the global anon rate it fell back to defaulted to unlimited.

    Two ceilings, because each is blind to the other's attack. The 'login'
    scope is keyed on the client address and bounds how fast one source can
    guess. LoginEmailRateThrottle is keyed on the submitted account and bounds
    how many guesses one victim receives no matter how many addresses they come
    from — the distributed case, which no per-IP rate can see.
    """
    throttle_classes = [
        ClientIPScopedRateThrottle, LoginEmailRateThrottle, *GLOBAL_THROTTLES,
    ]
    throttle_scope = 'login'


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
        # The demo profile is shared by every visitor — no renaming Jordan Doe.
        require_not_demo(user)
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
        require_not_demo(request.user)
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
    require_not_demo(request.user)
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
    # really are an image, and that they are the format the extension claims —
    # "is decodable by Pillow" alone would let TIFF/BMP/PPM bytes named ".png"
    # through, and the allowlist's real job is bounding which Pillow *decoders*
    # untrusted bytes can reach. Phase 73 moved the check into core.uploads so
    # avatars, slide imports and lesson attachments share one implementation.
    content_error = verify_image(avatar_file, file_ext)
    if content_error:
        return Response(
            {'error': content_error},
            status=status.HTTP_400_BAD_REQUEST
        )

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
    require_not_demo(request.user)
    preferences, _ = UserPreferences.objects.get_or_create(user=request.user)

    if preferences.avatar:
        preferences.avatar.delete(save=True)

    serializer = UserPreferencesSerializer(preferences, context={'request': request})
    return Response(serializer.data)
