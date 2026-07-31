from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

import unicodedata

from core.demo import require_not_demo
from .avatar_catalog import SLOTS, get_item, is_unlocked, unlock_label
from .models import GameProfile, Badge, UserBadge
from .serializers import BadgeSerializer
from .services import avatar_payload, earned_badge_keys_for, profile_payload


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

    # Reuse the badge data already serialized above — the avatar block needs
    # the earned keys for its badge-gated items and must not re-query.
    payload = profile_payload(profile, {b['key'] for b in earned_badges})
    payload.update({
        'is_gamified': True,
        'badges': earned_badges,
        'all_badges': all_badge_data,
    })
    return Response(payload)


def clean_mascot_name(raw):
    """
    Normalize and validate a submitted mascot name, or return None if it is
    not acceptable.

    Length alone is not enough. Anything in Unicode's "other" categories has
    to go before the value reaches Postgres:

    - ``Cc`` control characters — a bare NUL makes psycopg raise ``DataError``
      at ``save()``, which surfaces as an unhandled 500 rather than a 400.
    - ``Cf`` format characters — a zero-width space passes ``str.strip()`` and
      ``len() >= 1``, so a "blank" name would slip through the length rule;
      a right-to-left override can visually reverse the rendered name.
    - ``Cs``/``Co``/``Cn`` surrogates, private-use and unassigned code points.

    Normalizing to NFKC first collapses compatibility forms so the length
    check measures what the student will actually see.
    """
    name = unicodedata.normalize('NFKC', raw).strip()
    if not 1 <= len(name) <= 20:
        return None
    if any(unicodedata.category(ch).startswith('C') for ch in name):
        return None
    return name


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_avatar(request):
    """
    Partially update the student's Circuit avatar (Phase 33, Phase 64).

    Accepts any of: ``mascot_name`` plus one key per slot (the eight in
    ``avatar_catalog.SLOTS``). All-or-nothing: any invalid field is a 400 and
    nothing persists. Returns the refreshed avatar block.

    Demo policy (Phase 64): the shared demo account may equip cosmetics —
    they are self-scoped, reversible, and the whole point of a public demo —
    but ``mascot_name`` stays blocked because it is free text on a profile
    every visitor shares.
    """
    user = request.user
    if user.is_instructor:
        raise PermissionDenied('Avatar customization is only available to students.')

    profile, _ = GameProfile.objects.get_or_create(user=user)
    update_fields = []

    if 'mascot_name' in request.data:
        # Raises the standard demo 403 before anything is validated or saved,
        # so a body mixing a rename with valid slot equips persists nothing.
        require_not_demo(user)
        name = request.data.get('mascot_name')
        name = clean_mascot_name(name) if isinstance(name, str) else None
        if name is None:
            return Response(
                {'detail': 'Name must be 1-20 characters, letters and numbers.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile.mascot_name = name
        update_fields.append('mascot_name')

    # Fetched once for the whole request — badge-gated items must not cost a
    # query each. Skipped entirely when the body touches no slots, so a
    # rename-only PATCH doesn't pay for a badge lookup it never reads.
    # None (not an empty set) when unfetched: avatar_payload treats None as
    # "fetch it yourself" but would treat an empty set as "this user has no
    # badges", which would render every badge-gated item as locked.
    touches_slots = any(slot in request.data for slot in SLOTS)
    earned_badge_keys = earned_badge_keys_for(user) if touches_slots else None
    level = profile.level

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
        if not is_unlocked(item, level, earned_badge_keys, profile.longest_streak):
            return Response(
                {'detail': f"'{item['name']}' unlocks at {unlock_label(item)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        setattr(profile, f'avatar_{slot}', key)
        update_fields.append(f'avatar_{slot}')

    if update_fields:
        profile.save(update_fields=update_fields + ['updated_at'])
    return Response(avatar_payload(profile, earned_badge_keys))
