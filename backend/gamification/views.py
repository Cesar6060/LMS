from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import GameProfile, Badge, UserBadge
from .serializers import BadgeSerializer
from .services import profile_payload


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
