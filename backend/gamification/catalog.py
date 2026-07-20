"""
The fixed, code-seeded badge catalog. Referenced by both the seed data
migration and the backfill command so there is a single definition.
"""

# key, name, description, icon, criteria_type, threshold, order
BADGE_CATALOG = [
    {
        'key': 'first_lesson',
        'name': 'First Steps',
        'description': 'Complete your first lesson',
        'icon': '👣',
        'criteria_type': 'lessons_done',
        'threshold': 1,
        'order': 1,
    },
    {
        'key': 'streak_7',
        'name': 'On Fire',
        'description': 'Reach a 7-day streak',
        'icon': '🔥',
        'criteria_type': 'streak',
        'threshold': 7,
        'order': 2,
    },
    {
        'key': 'perfect_quiz',
        'name': 'Sharpshooter',
        'description': 'Score 100% on any quiz',
        'icon': '🎯',
        'criteria_type': 'perfect_quiz',
        'threshold': None,
        'order': 3,
    },
    {
        'key': 'course_done',
        'name': 'Scholar',
        'description': 'Complete every lesson in a course',
        'icon': '🎓',
        'criteria_type': 'course_complete',
        'threshold': None,
        'order': 4,
    },
    {
        'key': 'xp_100',
        'name': 'Getting Going',
        'description': 'Earn 100 XP',
        'icon': '⭐',
        'criteria_type': 'xp',
        'threshold': 100,
        'order': 5,
    },
    {
        'key': 'xp_500',
        'name': 'Committed',
        'description': 'Earn 500 XP',
        'icon': '🌟',
        'criteria_type': 'xp',
        'threshold': 500,
        'order': 6,
    },
    {
        'key': 'xp_1000',
        'name': 'Unstoppable',
        'description': 'Earn 1000 XP',
        'icon': '🚀',
        'criteria_type': 'xp',
        'threshold': 1000,
        'order': 7,
    },
]


def seed_badges(Badge):
    """
    Idempotently ensure the catalog exists / is up to date. ``Badge`` is
    passed in so this works both from a migration (historical model) and from
    live code. Keyed on ``key`` so re-running is a no-op.
    """
    for entry in BADGE_CATALOG:
        Badge.objects.update_or_create(
            key=entry['key'],
            defaults={
                'name': entry['name'],
                'description': entry['description'],
                'icon': entry['icon'],
                'criteria_type': entry['criteria_type'],
                'threshold': entry['threshold'],
                'order': entry['order'],
            },
        )
