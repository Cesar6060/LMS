"""
The fixed, code-defined avatar cosmetic catalog (Phase 33, widened Phase 64).

Like the badge catalog, this lives in code — no DB table. Unlock state is a
pure function of data the profile already carries, so unlocks are permanent,
retroactive, and need no per-user rows. Three gates exist (``unlock_type``):

``level``   ``level >= required_level`` — the derived level from total XP.
``badge``   ``required_badge`` is in the student's earned badge keys.
``streak``  ``longest_streak >= required_streak``. Deliberately *longest*, not
            *current*: a gate that revokes would silently downgrade an equipped
            item back to the slot default the morning after a missed day.

Keys are unique *within a slot* (the shared ``'none'`` default appears in
every non-color slot), so lookups always take the slot.
"""

from django.core.exceptions import ImproperlyConfigured

from .catalog import BADGE_CATALOG

SLOTS = (
    'color', 'headgear', 'eyes', 'accessory', 'backdrop',
    # Phase 64. Appended, not interleaved — the tuple order drives iteration
    # in update_avatar and avatar_payload, and the original five keep their
    # relative order so payload key order is stable.
    #
    # The 'aura' slot was retired after phase 64: its rings framed the whole
    # figure and made every other cosmetic hard to read. The GameProfile
    # column is deliberately LEFT IN PLACE — dropping it is irreversible and
    # would break any still-running old code. Absent from SLOTS, it simply
    # stops being read or served.
    'companion', 'held',
)

# The level-1 default key per slot — what a fresh profile wears, and what a
# stale/removed/locked key falls back to.
SLOT_DEFAULTS = {
    'color': 'classic',
    'headgear': 'none',
    'eyes': 'none',
    'accessory': 'none',
    'backdrop': 'plain',
    'companion': 'none',
    'held': 'none',
}

UNLOCK_LEVEL = 'level'
UNLOCK_BADGE = 'badge'
UNLOCK_STREAK = 'streak'
UNLOCK_TYPES = (UNLOCK_LEVEL, UNLOCK_BADGE, UNLOCK_STREAK)

# Badge-gated and streak-gated items keep required_level at 1 so the level
# gate never double-blocks them.
CATALOG = [
    # -- Color schemes (palette swaps) --------------------------------------
    {'key': 'classic', 'slot': 'color', 'name': 'Classic Green',
     'description': "Circuit's original STEM Quest look",
     'required_level': 1, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'ember', 'slot': 'color', 'name': 'Ember',
     'description': 'A fiery orange glow',
     'required_level': 2, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'ocean', 'slot': 'color', 'name': 'Ocean',
     'description': 'Cool deep-sea blue',
     'required_level': 3, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'mint', 'slot': 'color', 'name': 'Mint Circuit',
     'description': 'Fresh and cool-headed',
     'required_level': 4, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'bubblegum', 'slot': 'color', 'name': 'Bubblegum',
     'description': 'Playful pink circuits',
     'required_level': 5, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'gold', 'slot': 'color', 'name': 'Gold',
     'description': 'Shimmering champion gold',
     'required_level': 7, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'violet', 'slot': 'color', 'name': 'Violet Surge',
     'description': 'High-voltage purple',
     'required_level': 9, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'crimson', 'slot': 'color', 'name': 'Crimson',
     'description': 'Deep red alloy',
     'required_level': 12, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'chrome', 'slot': 'color', 'name': 'Chrome',
     'description': 'Polished to a mirror finish',
     'required_level': 15, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'aurora', 'slot': 'color', 'name': 'Aurora Alloy',
     'description': 'Shifting colors, earned by finishing a course',
     'required_level': 1, 'unlock_type': UNLOCK_BADGE,
     'required_badge': 'course_done'},

    # -- Headgear -----------------------------------------------------------
    {'key': 'none', 'slot': 'headgear', 'name': 'No Headgear',
     'description': 'Just the antenna',
     'required_level': 1, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'cap', 'slot': 'headgear', 'name': 'Quest Cap',
     'description': 'A sporty baseball cap',
     'required_level': 2, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'headphones', 'slot': 'headgear', 'name': 'Headphones',
     'description': 'Lo-fi beats to debug to',
     'required_level': 3, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'beanie', 'slot': 'headgear', 'name': 'Beanie',
     'description': 'Warm, slouchy, unbothered',
     'required_level': 4, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'wizard_hat', 'slot': 'headgear', 'name': 'Wizard Hat',
     'description': 'For masters of the arcane arts',
     'required_level': 5, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'crown', 'slot': 'headgear', 'name': 'Crown',
     'description': 'Royalty of the leaderless leaderboard',
     'required_level': 6, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'halo', 'slot': 'headgear', 'name': 'Halo',
     'description': 'Practically perfect',
     'required_level': 8, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'hard_hat', 'slot': 'headgear', 'name': 'Hard Hat',
     'description': 'Robotics lab safety first',
     'required_level': 9, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'space_helmet', 'slot': 'headgear', 'name': 'Space Helmet',
     'description': 'Rated for vacuum and pop quizzes',
     'required_level': 11, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'laurel', 'slot': 'headgear', 'name': 'Laurel Wreath',
     'description': 'For finishing everything a course had to teach',
     'required_level': 1, 'unlock_type': UNLOCK_BADGE,
     'required_badge': 'course_done'},
    {'key': 'flame_crest', 'slot': 'headgear', 'name': 'Flame Crest',
     'description': 'Two solid weeks without missing a day',
     'required_level': 1, 'unlock_type': UNLOCK_STREAK,
     'required_streak': 14},

    # -- Eyes / face styles -------------------------------------------------
    {'key': 'none', 'slot': 'eyes', 'name': 'Classic Eyes',
     'description': "Circuit's standard-issue optics",
     'required_level': 1, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'visor', 'slot': 'eyes', 'name': 'Visor',
     'description': 'A sleek glowing eye-band',
     'required_level': 2, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'sleepy', 'slot': 'eyes', 'name': 'Sleepy Eyes',
     'description': 'Studied late. Worth it.',
     'required_level': 3, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'glasses', 'slot': 'eyes', 'name': 'Smart Glasses',
     'description': 'Plus 10 to studying',
     'required_level': 4, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'starry', 'slot': 'eyes', 'name': 'Starry Eyes',
     'description': 'Full of wonder',
     'required_level': 6, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'shades', 'slot': 'eyes', 'name': 'Shades',
     'description': 'Deal with it',
     'required_level': 7, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'heart', 'slot': 'eyes', 'name': 'Heart Eyes',
     'description': 'In love with learning',
     'required_level': 9, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'scanner', 'slot': 'eyes', 'name': 'Scanner Beam',
     'description': 'A single sweeping sensor eye',
     'required_level': 12, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'laser', 'slot': 'eyes', 'name': 'Laser Eyes',
     'description': 'Unlocked by a perfect quiz score',
     'required_level': 1, 'unlock_type': UNLOCK_BADGE,
     'required_badge': 'perfect_quiz'},
    {'key': 'focus', 'slot': 'eyes', 'name': 'Focus Eyes',
     'description': 'A full week of showing up',
     'required_level': 1, 'unlock_type': UNLOCK_STREAK,
     'required_streak': 7},

    # -- Accessories --------------------------------------------------------
    {'key': 'none', 'slot': 'accessory', 'name': 'No Accessory',
     'description': 'Travel light',
     'required_level': 1, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'bowtie', 'slot': 'accessory', 'name': 'Bow Tie',
     'description': 'Bow ties are cool',
     'required_level': 2, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'scarf', 'slot': 'accessory', 'name': 'Scarf',
     'description': 'Cozy adventuring gear',
     'required_level': 3, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'medal', 'slot': 'accessory', 'name': 'Medal',
     'description': 'Earned, never given',
     'required_level': 4, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'backpack', 'slot': 'accessory', 'name': 'Quest Backpack',
     'description': 'Everything you need for the road',
     'required_level': 4, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'cape', 'slot': 'accessory', 'name': 'Hero Cape',
     'description': 'Not all heroes wear capes. This one does.',
     'required_level': 6, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'jetpack', 'slot': 'accessory', 'name': 'Jetpack',
     'description': 'To the moon',
     'required_level': 8, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'sash', 'slot': 'accessory', 'name': 'Champion Sash',
     'description': 'Worn by those who kept going',
     'required_level': 10, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'wings', 'slot': 'accessory', 'name': 'Circuit Wings',
     'description': 'Lighter than they look',
     'required_level': 13, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'marksman_pin', 'slot': 'accessory', 'name': 'Marksman Pin',
     'description': 'Awarded for a flawless quiz',
     'required_level': 1, 'unlock_type': UNLOCK_BADGE,
     'required_badge': 'perfect_quiz'},

    # -- Backdrops ----------------------------------------------------------
    {'key': 'plain', 'slot': 'backdrop', 'name': 'Plain Panel',
     'description': 'A simple tidy backdrop',
     'required_level': 1, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'none', 'slot': 'backdrop', 'name': 'No Backdrop',
     'description': 'Circuit, unframed',
     'required_level': 1, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'grid', 'slot': 'backdrop', 'name': 'Circuit Grid',
     'description': 'Straight off the motherboard',
     'required_level': 2, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'stars', 'slot': 'backdrop', 'name': 'Night Sky',
     'description': 'A calm starfield',
     'required_level': 4, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'sunset', 'slot': 'backdrop', 'name': 'Sunset',
     'description': 'Golden-hour gradients',
     'required_level': 5, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'forest', 'slot': 'backdrop', 'name': 'Emerald Forest',
     'description': 'Quiet green canopy',
     'required_level': 6, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'galaxy', 'slot': 'backdrop', 'name': 'Galaxy',
     'description': 'Deep-space vibes',
     'required_level': 7, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'arcade', 'slot': 'backdrop', 'name': 'Arcade Neon',
     'description': 'Insert coin to continue',
     'required_level': 10, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'aurora_sky', 'slot': 'backdrop', 'name': 'Aurora Borealis',
     'description': 'Ribbons of light over a frozen sky',
     'required_level': 14, 'unlock_type': UNLOCK_LEVEL},

    # -- Companions (Phase 64) ----------------------------------------------
    {'key': 'none', 'slot': 'companion', 'name': 'No Companion',
     'description': 'Going solo',
     'required_level': 1, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'drone', 'slot': 'companion', 'name': 'Scout Drone',
     'description': 'A little rotor buddy',
     'required_level': 2, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'chip', 'slot': 'companion', 'name': 'Chip Sprite',
     'description': 'A friendly floating microchip',
     'required_level': 5, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'robo_cat', 'slot': 'companion', 'name': 'Robo-Cat',
     'description': 'Purrs in binary',
     'required_level': 8, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'owl', 'slot': 'companion', 'name': 'Byte Owl',
     'description': 'Wise, nocturnal, well-read',
     'required_level': 12, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'dragon', 'slot': 'companion', 'name': 'Pixel Dragon',
     'description': 'Small, but genuinely a dragon',
     'required_level': 15, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'phoenix', 'slot': 'companion', 'name': 'Streak Phoenix',
     'description': 'Thirty days without missing one',
     'required_level': 1, 'unlock_type': UNLOCK_STREAK,
     'required_streak': 30},

    # -- Held items (Phase 64) ----------------------------------------------
    {'key': 'none', 'slot': 'held', 'name': 'Empty Hands',
     'description': 'Ready for anything',
     'required_level': 1, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'wrench', 'slot': 'held', 'name': 'Wrench',
     'description': 'For when it needs a tighten',
     'required_level': 2, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'controller', 'slot': 'held', 'name': 'Game Controller',
     'description': 'Player one, always',
     'required_level': 4, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'codex', 'slot': 'held', 'name': 'Codex',
     'description': 'The good documentation',
     'required_level': 7, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'debug_blade', 'slot': 'held', 'name': 'Debug Blade',
     'description': 'Cuts through any stack trace',
     'required_level': 11, 'unlock_type': UNLOCK_LEVEL},
    {'key': 'torch', 'slot': 'held', 'name': 'Streak Torch',
     'description': 'Carried for fourteen days straight',
     'required_level': 1, 'unlock_type': UNLOCK_STREAK,
     'required_streak': 14},
    {'key': 'trophy', 'slot': 'held', 'name': 'Trophy',
     'description': 'Held high after a perfect quiz',
     'required_level': 1, 'unlock_type': UNLOCK_BADGE,
     'required_badge': 'perfect_quiz'},
]

_BADGE_NAMES = {entry['key']: entry['name'] for entry in BADGE_CATALOG}


def items_for_slot(slot):
    """All catalog items for ``slot``, in catalog (level) order."""
    return [item for item in CATALOG if item['slot'] == slot]


def get_item(slot, key):
    """The catalog item for ``(slot, key)``, or None if it doesn't exist."""
    for item in CATALOG:
        if item['slot'] == slot and item['key'] == key:
            return item
    return None


def is_unlocked(item, level, earned_badge_keys=(), longest_streak=0):
    """
    Whether ``item`` is available to a student with this level / badge set /
    longest streak. The single source of gate truth — the payload builder,
    the PATCH validator and the tests all route through here.
    """
    unlock_type = item['unlock_type']
    if unlock_type == UNLOCK_BADGE:
        return item['required_badge'] in earned_badge_keys
    if unlock_type == UNLOCK_STREAK:
        return longest_streak >= item['required_streak']
    return level >= item['required_level']


def unlock_label(item):
    """
    Short human-readable gate for the UI chip: ``'Lv 9'``,
    ``'Sharpshooter badge'``, ``'14-day streak'``.
    """
    unlock_type = item['unlock_type']
    if unlock_type == UNLOCK_BADGE:
        return f"{_BADGE_NAMES[item['required_badge']]} badge"
    if unlock_type == UNLOCK_STREAK:
        return f"{item['required_streak']}-day streak"
    return f"Lv {item['required_level']}"


def _validate_catalog():
    """
    Fail at import rather than serve a blank unlock chip or an unequippable
    slot. Every rule here also has a test, but the import guard is what stops
    a bad entry reaching a running server at all.
    """
    seen = set()
    for item in CATALOG:
        ref = f"{item['slot']}/{item['key']}"
        if item['slot'] not in SLOTS:
            raise ImproperlyConfigured(f'Avatar item {ref}: unknown slot.')
        if (item['slot'], item['key']) in seen:
            raise ImproperlyConfigured(f'Avatar item {ref}: duplicate key in slot.')
        seen.add((item['slot'], item['key']))

        unlock_type = item.get('unlock_type')
        if unlock_type not in UNLOCK_TYPES:
            raise ImproperlyConfigured(
                f'Avatar item {ref}: unlock_type must be one of {UNLOCK_TYPES}.'
            )
        if unlock_type == UNLOCK_BADGE and item.get('required_badge') not in _BADGE_NAMES:
            raise ImproperlyConfigured(
                f'Avatar item {ref}: required_badge '
                f'{item.get("required_badge")!r} is not in BADGE_CATALOG.'
            )
        if unlock_type == UNLOCK_STREAK and not item.get('required_streak', 0) > 0:
            raise ImproperlyConfigured(
                f'Avatar item {ref}: streak gate needs a positive required_streak.'
            )
        if not isinstance(item.get('required_level'), int) or item['required_level'] < 1:
            raise ImproperlyConfigured(f'Avatar item {ref}: required_level must be >= 1.')

    for slot in SLOTS:
        default_key = SLOT_DEFAULTS.get(slot)
        if default_key is None:
            raise ImproperlyConfigured(f'Slot {slot!r} has no SLOT_DEFAULTS entry.')
        default = get_item(slot, default_key)
        if default is None:
            raise ImproperlyConfigured(
                f'Slot {slot!r} default {default_key!r} is not in the catalog.'
            )
        # The fallback must be reachable by everyone, or a stale key would
        # resolve to something the student still can't use.
        if default['unlock_type'] != UNLOCK_LEVEL or default['required_level'] != 1:
            raise ImproperlyConfigured(
                f'Slot {slot!r} default {default_key!r} must be an unconditional '
                'level-1 item.'
            )


_validate_catalog()
