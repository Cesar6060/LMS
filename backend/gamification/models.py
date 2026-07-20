from django.db import models
from django.conf import settings

from .leveling import level_for_xp


class GameProfile(models.Model):
    """
    Per-student gamification state. OneToOne onto the User.

    Level is NOT stored — it is derived from ``total_xp`` via the single
    backend formula (see ``gamification.leveling``) so it can never drift.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='game_profile'
    )
    total_xp = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    streak_freezes = models.PositiveSmallIntegerField(
        default=0, help_text='Earned on level-up (max 2), auto-consumed on missed days'
    )
    # Phase 33: Circuit avatar. Equipped keys reference the code catalog
    # (gamification.avatar_catalog); unlock state is derived from level, so
    # there are no per-user unlock rows. A stale key (item later removed from
    # the catalog) renders as the slot default.
    mascot_name = models.CharField(max_length=20, default='Circuit')
    avatar_color = models.CharField(max_length=30, default='classic')
    avatar_headgear = models.CharField(max_length=30, default='none')
    avatar_eyes = models.CharField(max_length=30, default='none')
    avatar_accessory = models.CharField(max_length=30, default='none')
    avatar_backdrop = models.CharField(max_length=30, default='plain')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gamification_gameprofile'

    def __str__(self):
        return f"{self.user.email}: {self.total_xp} XP (Lv {self.level})"

    @property
    def level(self):
        """Derived level for the current total XP (never stored)."""
        return level_for_xp(self.total_xp)


class XPEvent(models.Model):
    """
    Immutable ledger row for a single XP award.

    The ``unique_together`` constraint is the correctness core of the whole
    feature: it guarantees each source (a lesson completion, a quiz pass) can
    award XP at most once, so re-completing / re-passing never re-awards and
    the backfill is idempotent.
    """
    SOURCE_LESSON = 'lesson'
    SOURCE_QUIZ = 'quiz'
    SOURCE_LESSON_QUIZ = 'lesson_quiz'
    SOURCE_TYPE_CHOICES = [
        (SOURCE_LESSON, 'Lesson completion'),
        (SOURCE_QUIZ, 'Unit quiz pass'),
        (SOURCE_LESSON_QUIZ, 'Lesson comprehension quiz pass'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='xp_events'
    )
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    source_id = models.PositiveIntegerField()
    amount = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gamification_xpevent'
        unique_together = ['user', 'source_type', 'source_id']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} +{self.amount} XP ({self.source_type}#{self.source_id})"


class Badge(models.Model):
    """
    A catalog entry for a milestone badge. Seeded from code and fixed this
    phase (no instructor UI). Uniquely keyed by ``key`` so seeding is a no-op
    on re-run.
    """
    CRITERIA_LESSONS_DONE = 'lessons_done'
    CRITERIA_STREAK = 'streak'
    CRITERIA_PERFECT_QUIZ = 'perfect_quiz'
    CRITERIA_COURSE_COMPLETE = 'course_complete'
    CRITERIA_XP = 'xp'
    CRITERIA_TYPE_CHOICES = [
        (CRITERIA_LESSONS_DONE, 'Lessons completed'),
        (CRITERIA_STREAK, 'Streak reached'),
        (CRITERIA_PERFECT_QUIZ, 'Perfect quiz score'),
        (CRITERIA_COURSE_COMPLETE, 'Course completed'),
        (CRITERIA_XP, 'Total XP earned'),
    ]

    key = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    icon = models.CharField(max_length=10, help_text='Emoji icon')
    criteria_type = models.CharField(max_length=30, choices=CRITERIA_TYPE_CHOICES)
    threshold = models.PositiveIntegerField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'gamification_badge'
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.icon} {self.name} ({self.key})"


class UserBadge(models.Model):
    """A badge earned by a user. Uniqueness prevents duplicate awards."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_badges'
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name='earned_by'
    )
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gamification_userbadge'
        unique_together = ['user', 'badge']
        ordering = ['-earned_at']

    def __str__(self):
        return f"{self.user.email} earned {self.badge.key}"
