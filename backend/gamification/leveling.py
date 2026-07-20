"""
Level math — the single backend source of truth.

Cumulative XP required to *reach* level L:  xp_for_level(L) = 50 * L * (L - 1)
    Lv1: 0, Lv2: 100, Lv3: 300, Lv4: 600, Lv5: 1000, Lv6: 1500, ...

Inverse (level for a given XP, min 1):
    level = floor((1 + sqrt(1 + 0.08 * xp)) / 2)

These are pure functions with no DB access. The API returns the derived level
and ring fields so the frontend never re-implements the math (no drift).
"""
import math


def xp_for_level(level):
    """Cumulative XP required to reach ``level`` (level >= 1 -> 0 at Lv1)."""
    if level < 1:
        level = 1
    return 50 * level * (level - 1)


def level_for_xp(xp):
    """The level a student with ``xp`` total XP is at (minimum 1)."""
    if xp <= 0:
        return 1
    level = int((1 + math.sqrt(1 + 0.08 * xp)) / 2)
    return max(1, level)


def level_progress(total_xp):
    """
    Return the ring fields for the current level given ``total_xp``.

    Keys: level, level_floor_xp, next_level_xp, xp_into_level, level_span,
    level_progress_pct.
    """
    level = level_for_xp(total_xp)
    level_floor_xp = xp_for_level(level)
    next_level_xp = xp_for_level(level + 1)
    level_span = next_level_xp - level_floor_xp
    xp_into_level = total_xp - level_floor_xp
    level_progress_pct = (
        round(100 * xp_into_level / level_span) if level_span > 0 else 0
    )
    return {
        'level': level,
        'level_floor_xp': level_floor_xp,
        'next_level_xp': next_level_xp,
        'xp_into_level': xp_into_level,
        'level_span': level_span,
        'level_progress_pct': level_progress_pct,
    }
