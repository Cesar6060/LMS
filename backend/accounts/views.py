from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .models import UserPreferences
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

    # Delete old avatar if exists
    if preferences.avatar:
        preferences.avatar.delete(save=False)

    preferences.avatar = request.FILES['avatar']
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
