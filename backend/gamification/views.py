from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .avatar_catalog import SLOTS, get_item
from .models import GameProfile, Badge, UserBadge
from .serializers import BadgeSerializer
from .services import avatar_payload, profile_payload


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gamification_profile(request):
    """
    Return the current user's gamification profile.

    Students get the full payload (level ring, streak, badges). Instructors
    get an inert ``{is_gamified: false}`` — they accrue nothing and see no UI.
    """
    user = request.user
    if user.is_instructor:
        return Response({'is_gamified': False})

    profile, _ = GameProfile.objects.get_or_create(user=user)

    earned_map = {
        ub.badge_id: ub.earned_at
        for ub in UserBadge.objects.filter(user=user).select_related('badge')
    }
    all_badges = Badge.objects.all()
    serializer = BadgeSerializer(
        all_badges, many=True, context={'earned_map': earned_map}
    )
    all_badge_data = serializer.data
    earned_badges = [b for b in all_badge_data if b['earned']]

    payload = profile_payload(profile)
    payload.update({
        'is_gamified': True,
        'badges': earned_badges,
        'all_badges': all_badge_data,
    })
    return Response(payload)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_avatar(request):
    """
    Partially update the student's Circuit avatar (Phase 33).

    Accepts any of: ``mascot_name`` plus one key per slot (``color``,
    ``headgear``, ``eyes``, ``accessory``). All-or-nothing: any invalid
    field is a 400 and nothing persists. Returns the refreshed avatar block.
    """
    user = request.user
    if user.is_instructor:
        raise PermissionDenied('Avatar customization is only available to students.')

    profile, _ = GameProfile.objects.get_or_create(user=user)
    update_fields = []

    if 'mascot_name' in request.data:
        name = request.data.get('mascot_name')
        name = name.strip() if isinstance(name, str) else ''
        if not 1 <= len(name) <= 20:
            return Response(
                {'detail': 'Name must be 1-20 characters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile.mascot_name = name
        update_fields.append('mascot_name')

    for slot in SLOTS:
        if slot not in request.data:
            continue
        key = request.data.get(slot)
        item = get_item(slot, key) if isinstance(key, str) else None
        if item is None:
            return Response(
                {'detail': f'Unknown {slot} item: {key!r}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if profile.level < item['required_level']:
            return Response(
                {'detail': f"'{item['name']}' unlocks at level {item['required_level']}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        setattr(profile, f'avatar_{slot}', key)
        update_fields.append(f'avatar_{slot}')

    if update_fields:
        profile.save(update_fields=update_fields + ['updated_at'])
    return Response(avatar_payload(profile))
