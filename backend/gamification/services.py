"""
The award service — the ONLY place that mutates gamification state.

Every XP path goes through ``_award_xp`` (nothing increments ``total_xp``
directly); the ``XPEvent`` uniqueness guarantees award-once. All public
award functions skip instructors and accept an injectable ``today`` so the
streak logic is deterministically testable.
"""
from dataclasses import dataclass, field
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .leveling import level_for_xp, level_progress
from .models import GameProfile, XPEvent, Badge, UserBadge

XP_LESSON = 50
XP_QUIZ = 20
XP_LESSON_QUIZ = 20
MAX_STREAK_FREEZES = 2


@dataclass
class GamificationResult:
    """The delta surfaced to the API after an award attempt."""
    xp_awarded: int = 0
    total_xp: int = 0
    level: int = 1
    leveled_up: bool = False
    new_badges: list = field(default_factory=list)  # list[Badge]
    current_streak: int = 0
    streak_freezes: int = 0
    freezes_earned: int = 0
    freezes_used: int = 0

    def as_dict(self):
        return {
            'xp_awarded': self.xp_awarded,
            'total_xp': self.total_xp,
            'level': self.level,
            'leveled_up': self.leveled_up,
            'new_badges': [_badge_brief(b) for b in self.new_badges],
            'current_streak': self.current_streak,
            'streak_freezes': self.streak_freezes,
            'freezes_earned': self.freezes_earned,
            'freezes_used': self.freezes_used,
        }


def _badge_brief(badge):
    return {
        'key': badge.key,
        'name': badge.name,
        'description': badge.description,
        'icon': badge.icon,
    }


# ---------------------------------------------------------------------------
# Time / streak
# ---------------------------------------------------------------------------

def _resolve_today(user, today=None):
    """Current date in the user's saved timezone (fallback settings.TIME_ZONE)."""
    if today is not None:
        return today
    tz_name = settings.TIME_ZONE
    prefs = getattr(user, 'preferences', None)
    if prefs is not None and prefs.timezone:
        tz_name = prefs.timezone
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo(settings.TIME_ZONE)
    return timezone.now().astimezone(tz).date()


def _update_streak(profile, today):
    """
    Advance/reset the daily streak. Called ONLY on lesson completion.

    Streak freezes (Phase 32): a gap of N missed days is absorbed when the
    profile holds at least N freezes — they are consumed and the streak
    continues (+1 for today). A gap larger than the freeze balance resets
    the streak to 1 and consumes nothing. Returns the number of freezes used.
    """
    last = profile.last_activity_date
    if last == today:
        return 0  # already counted today

    freezes_used = 0
    missed_days = (today - last).days - 1 if last is not None else None
    if missed_days == 0:
        profile.current_streak += 1
    elif missed_days is not None and 0 < missed_days <= profile.streak_freezes:
        profile.streak_freezes -= missed_days
        freezes_used = missed_days
        profile.current_streak += 1
    else:
        profile.current_streak = 1
    profile.last_activity_date = today
    if profile.current_streak > profile.longest_streak:
        profile.longest_streak = profile.current_streak
    profile.save(update_fields=[
        'current_streak', 'last_activity_date', 'longest_streak',
        'streak_freezes', 'updated_at',
    ])
    return freezes_used


# ---------------------------------------------------------------------------
# XP
# ---------------------------------------------------------------------------

def _award_xp(user, source_type, source_id, amount):
    """
    Award ``amount`` XP for a source exactly once. Returns whether a new
    XPEvent (and therefore an XP increment) was created. Assumes the user's
    GameProfile already exists.
    """
    _event, created = XPEvent.objects.get_or_create(
        user=user,
        source_type=source_type,
        source_id=source_id,
        defaults={'amount': amount},
    )
    if created:
        GameProfile.objects.filter(user=user).update(total_xp=F('total_xp') + amount)
    return created


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------

def _badge_satisfied(user, profile, badge):
    from courses.models import Lesson, LessonProgress, LessonQuizAttempt
    from quizzes.models import QuizAttempt

    criteria = badge.criteria_type
    if criteria == Badge.CRITERIA_XP:
        return profile.total_xp >= (badge.threshold or 0)
    if criteria == Badge.CRITERIA_STREAK:
        return profile.longest_streak >= (badge.threshold or 0)
    if criteria == Badge.CRITERIA_LESSONS_DONE:
        done = LessonProgress.objects.filter(user=user, completed=True).count()
        return done >= (badge.threshold or 0)
    if criteria == Badge.CRITERIA_PERFECT_QUIZ:
        if QuizAttempt.objects.filter(student=user, score=100).exists():
            return True
        return LessonQuizAttempt.objects.filter(
            user=user, total_questions__gt=0, score=F('total_questions')
        ).exists()
    if criteria == Badge.CRITERIA_COURSE_COMPLETE:
        from courses.models import Enrollment
        course_ids = Enrollment.objects.filter(
            user=user, is_active=True
        ).values_list('course_id', flat=True)
        for course_id in course_ids:
            total = Lesson.objects.filter(unit__course_id=course_id).count()
            if total == 0:
                continue
            completed = LessonProgress.objects.filter(
                user=user, completed=True, lesson__unit__course_id=course_id
            ).count()
            if completed >= total:
                return True
        return False
    return False


def _evaluate_badges(user, profile):
    """get_or_create every satisfied catalog badge; return the newly created."""
    new_badges = []
    for badge in Badge.objects.all():
        if _badge_satisfied(user, profile, badge):
            _ub, created = UserBadge.objects.get_or_create(user=user, badge=badge)
            if created:
                new_badges.append(badge)
    return new_badges


# ---------------------------------------------------------------------------
# Public award functions
# ---------------------------------------------------------------------------

def _award(user, source_type, source_id, amount, advance_streak=False, today=None):
    """Shared award pipeline. Returns a GamificationResult."""
    if user.is_instructor:
        return GamificationResult()  # inert — instructors accrue nothing

    with transaction.atomic():
        profile, _ = GameProfile.objects.get_or_create(user=user)
        before_xp = profile.total_xp

        created = _award_xp(user, source_type, source_id, amount)

        freezes_used = 0
        if advance_streak:
            resolved_today = _resolve_today(user, today)
            freezes_used = _update_streak(profile, resolved_today)

        profile.refresh_from_db()

        # Streak freezes: +1 per level gained, capped at MAX_STREAK_FREEZES.
        levels_gained = level_for_xp(profile.total_xp) - level_for_xp(before_xp)
        freezes_earned = 0
        if levels_gained > 0:
            freezes_earned = min(
                levels_gained, MAX_STREAK_FREEZES - profile.streak_freezes
            )
            if freezes_earned > 0:
                profile.streak_freezes += freezes_earned
                profile.save(update_fields=['streak_freezes', 'updated_at'])

        new_badges = _evaluate_badges(user, profile)

    after_xp = profile.total_xp
    return GamificationResult(
        xp_awarded=amount if created else 0,
        total_xp=after_xp,
        level=level_for_xp(after_xp),
        leveled_up=level_for_xp(before_xp) < level_for_xp(after_xp),
        new_badges=new_badges,
        current_streak=profile.current_streak,
        streak_freezes=profile.streak_freezes,
        freezes_earned=freezes_earned,
        freezes_used=freezes_used,
    )


def award_lesson_completion(user, lesson, today=None):
    """+50 XP for completing a lesson, advance the streak, evaluate badges."""
    return _award(
        user, XPEvent.SOURCE_LESSON, lesson.id, XP_LESSON,
        advance_streak=True, today=today,
    )


def award_quiz_pass(user, quiz, today=None):
    """+20 XP for passing a unit quiz (no streak change), evaluate badges."""
    return _award(user, XPEvent.SOURCE_QUIZ, quiz.id, XP_QUIZ, today=today)


def award_lesson_quiz_pass(user, lesson, today=None):
    """+20 XP for passing a lesson comprehension quiz, evaluate badges."""
    return _award(user, XPEvent.SOURCE_LESSON_QUIZ, lesson.id, XP_LESSON_QUIZ, today=today)


def profile_payload(profile):
    """
    Build the read-endpoint dict for a student's GameProfile (level ring +
    streak fields). Badge lists are attached by the serializer/view.
    """
    ring = level_progress(profile.total_xp)
    return {
        'total_xp': profile.total_xp,
        'current_streak': profile.current_streak,
        'longest_streak': profile.longest_streak,
        'last_activity_date': profile.last_activity_date,
        'streak_freezes': profile.streak_freezes,
        **ring,
    }
