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
    # (gamification.avatar_catalog); unlock state is derived from data already
    # on this model plus earned badges, so there are no per-user unlock rows.
    # A stale key (item later removed from the catalog) renders as the slot
    # default.
    #
    # Phase 64 widened this to eight slots and three unlock axes: derived
    # level, an earned badge key, or ``longest_streak``. Streak gates read
    # ``longest_streak`` and never ``current_streak`` so an unlock, once
    # earned, is permanent — the same guarantee level and badge gates give.
    mascot_name = models.CharField(max_length=20, default='Circuit')
    avatar_color = models.CharField(max_length=30, default='classic')
    avatar_headgear = models.CharField(max_length=30, default='none')
    avatar_eyes = models.CharField(max_length=30, default='none')
    avatar_accessory = models.CharField(max_length=30, default='none')
    avatar_backdrop = models.CharField(max_length=30, default='plain')
    # These three carry db_default as well as default, unlike the phase-33
    # fields above. Migrations are applied to Neon by hand BEFORE the new code
    # deploys, and `AddField(default=...)` backfills and then DROPs the database
    # default — leaving NOT NULL columns the running (old) code doesn't know to
    # populate. GameProfile rows are created lazily by `get_or_create` on the
    # dashboard and in every XP award, so during that window a student without a
    # profile row would 500. `db_default` keeps the default in the schema and
    # closes the gap.
    avatar_companion = models.CharField(max_length=30, default='none', db_default='none')
    avatar_aura = models.CharField(max_length=30, default='none', db_default='none')
    avatar_held = models.CharField(max_length=30, default='none', db_default='none')
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

    The uniqueness on ``(user, source_type, source_key)`` is the correctness
    core of the whole feature: it guarantees each source (a lesson completion,
    a quiz pass) can award XP at most once, so re-completing / re-passing never
    re-awards and the backfill is idempotent.

    Phase 65 moved that guarantee from ``source_id`` to ``source_key``. The id
    is a bare primary key with no foreign key, so a content rebuild that
    deleted and recreated a lesson handed it a NEW pk and the student was paid
    again. ``source_key`` holds the target's ``content_key``, which survives
    delete-and-recreate, so the ledger is now immune to it.

    XP never decreases (decision 4): an ``XPEvent`` whose source is later
    deleted is kept and its XP stays summed into ``GameProfile.total_xp``. The
    backfill labels those rows ``orphan:<source_type>:<source_id>``.
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
    # DORMANT (Phase 65): superseded by ``source_key`` as the dedupe key. It is
    # still written on every award and kept as the audit trail of which primary
    # key originally paid — that history is the only way to reconcile the rows
    # a destructive reseed orphaned. Do not dedupe on it; do not read it for
    # correctness. Dropping the column is a change of its own (same treatment
    # as the phase-53 ``Lesson.content`` block, courses/models.py:95-114).
    #
    # Nullable as of Phase 65. The legacy ``(user, source_type, source_id)``
    # uniqueness below is still live, so a caller that supplies no id must not
    # be coerced to a sentinel like 0 — every such row would then collide with
    # every other one. NULL keeps them distinct under a Postgres unique index.
    source_id = models.PositiveIntegerField(null=True, blank=True)
    source_key = models.CharField(
        max_length=100, null=True, blank=True,
        help_text="The target's content_key. This is what dedupes; source_id is history.",
    )
    amount = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gamification_xpevent'
        # Both constraints are live. The source_id one is legacy and stays only
        # so old rows keep their guarantee; source_key is what new awards dedupe
        # on. See the class docstring.
        unique_together = [
            ['user', 'source_type', 'source_id'],
            ['user', 'source_type', 'source_key'],
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} +{self.amount} XP ({self.source_type}#{self.source_key})"


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
