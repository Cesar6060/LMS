"""
The fixed, code-defined avatar cosmetic catalog (Phase 33).

Like the badge catalog, this lives in code — no DB table. Unlock state is a
pure function of the profile's derived level (``level >= required_level``),
so unlocks are permanent, retroactive, and need no per-user rows.

Keys are unique *within a slot* (the shared ``'none'`` default appears in
every non-color slot), so lookups always take the slot.
"""

SLOTS = ('color', 'headgear', 'eyes', 'accessory', 'backdrop')

# The level-1 default key per slot — what a fresh profile wears, and what a
# stale/removed key falls back to.
SLOT_DEFAULTS = {
    'color': 'classic',
    'headgear': 'none',
    'eyes': 'none',
    'accessory': 'none',
    'backdrop': 'plain',
}

CATALOG = [
    # -- Color schemes (palette swaps) --------------------------------------
    {'key': 'classic', 'slot': 'color', 'name': 'Classic Green',
     'description': "Circuit's original STEM Quest look", 'required_level': 1},
    {'key': 'ember', 'slot': 'color', 'name': 'Ember',
     'description': 'A fiery orange glow', 'required_level': 2},
    {'key': 'ocean', 'slot': 'color', 'name': 'Ocean',
     'description': 'Cool deep-sea blue', 'required_level': 3},
    {'key': 'bubblegum', 'slot': 'color', 'name': 'Bubblegum',
     'description': 'Playful pink circuits', 'required_level': 5},
    {'key': 'gold', 'slot': 'color', 'name': 'Gold',
     'description': 'Shimmering champion gold', 'required_level': 7},

    # -- Headgear -----------------------------------------------------------
    {'key': 'none', 'slot': 'headgear', 'name': 'No Headgear',
     'description': 'Just the antenna', 'required_level': 1},
    {'key': 'cap', 'slot': 'headgear', 'name': 'Quest Cap',
     'description': 'A sporty baseball cap', 'required_level': 2},
    {'key': 'headphones', 'slot': 'headgear', 'name': 'Headphones',
     'description': 'Lo-fi beats to debug to', 'required_level': 3},
    {'key': 'wizard_hat', 'slot': 'headgear', 'name': 'Wizard Hat',
     'description': 'For masters of the arcane arts', 'required_level': 5},
    {'key': 'crown', 'slot': 'headgear', 'name': 'Crown',
     'description': 'Royalty of the leaderless leaderboard', 'required_level': 6},
    {'key': 'halo', 'slot': 'headgear', 'name': 'Halo',
     'description': 'Practically perfect', 'required_level': 8},

    # -- Eyes / face styles -------------------------------------------------
    {'key': 'none', 'slot': 'eyes', 'name': 'Classic Eyes',
     'description': "Circuit's standard-issue optics", 'required_level': 1},
    {'key': 'visor', 'slot': 'eyes', 'name': 'Visor',
     'description': 'A sleek glowing eye-band', 'required_level': 2},
    {'key': 'glasses', 'slot': 'eyes', 'name': 'Smart Glasses',
     'description': 'Plus 10 to studying', 'required_level': 4},
    {'key': 'starry', 'slot': 'eyes', 'name': 'Starry Eyes',
     'description': 'Full of wonder', 'required_level': 6},
    {'key': 'shades', 'slot': 'eyes', 'name': 'Shades',
     'description': 'Deal with it', 'required_level': 7},

    # -- Accessories --------------------------------------------------------
    {'key': 'none', 'slot': 'accessory', 'name': 'No Accessory',
     'description': 'Travel light', 'required_level': 1},
    {'key': 'bowtie', 'slot': 'accessory', 'name': 'Bow Tie',
     'description': 'Bow ties are cool', 'required_level': 2},
    {'key': 'scarf', 'slot': 'accessory', 'name': 'Scarf',
     'description': 'Cozy adventuring gear', 'required_level': 3},
    {'key': 'medal', 'slot': 'accessory', 'name': 'Medal',
     'description': 'Earned, never given', 'required_level': 4},
    {'key': 'cape', 'slot': 'accessory', 'name': 'Hero Cape',
     'description': 'Not all heroes wear capes. This one does.', 'required_level': 6},
    {'key': 'jetpack', 'slot': 'accessory', 'name': 'Jetpack',
     'description': 'To the moon', 'required_level': 8},

    # -- Backdrops ----------------------------------------------------------
    {'key': 'plain', 'slot': 'backdrop', 'name': 'Plain Panel',
     'description': 'A simple tidy backdrop', 'required_level': 1},
    {'key': 'none', 'slot': 'backdrop', 'name': 'No Backdrop',
     'description': 'Circuit, unframed', 'required_level': 1},
    {'key': 'grid', 'slot': 'backdrop', 'name': 'Circuit Grid',
     'description': 'Straight off the motherboard', 'required_level': 2},
    {'key': 'stars', 'slot': 'backdrop', 'name': 'Night Sky',
     'description': 'A calm starfield', 'required_level': 4},
    {'key': 'sunset', 'slot': 'backdrop', 'name': 'Sunset',
     'description': 'Golden-hour gradients', 'required_level': 5},
    {'key': 'galaxy', 'slot': 'backdrop', 'name': 'Galaxy',
     'description': 'Deep-space vibes', 'required_level': 7},
]


def items_for_slot(slot):
    """All catalog items for ``slot``, in catalog (level) order."""
    return [item for item in CATALOG if item['slot'] == slot]


def get_item(slot, key):
    """The catalog item for ``(slot, key)``, or None if it doesn't exist."""
    for item in CATALOG:
        if item['slot'] == slot and item['key'] == key:
            return item
    return None
