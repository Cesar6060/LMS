"""
Idempotent backfill of XP + badges for existing students from their
completion / quiz history. Streaks are intentionally left at 0 (they start
fresh at launch). Re-running is a no-op thanks to XPEvent / UserBadge
uniqueness.

MUST be run manually after deploy — it does NOT run on migrate.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import LessonProgress, LessonQuizAttempt
from quizzes.models import QuizAttempt
from gamification.catalog import seed_badges
from gamification.models import GameProfile, XPEvent, Badge
from gamification.services import (
    _award_xp, _evaluate_badges, XP_LESSON, XP_QUIZ, XP_LESSON_QUIZ,
)


def _key(content_key, source_type, source_id):
    """Mirror of ``services._source_key_for`` for the (id, key) pairs below."""
    return content_key or f'legacy:{source_type}:{source_id}'
from gamification.signals import suppress_badge_notifications

User = get_user_model()


class Command(BaseCommand):
    help = 'Backfill XP and badges for existing students (idempotent). Streaks stay 0.'

    def handle(self, *args, **options):
        # Ensure the badge catalog exists (no-op if the data migration ran).
        seed_badges(Badge)

        students = User.objects.filter(is_instructor=False)
        total_xp_events = 0
        total_badges = 0

        # Backfilled badges are historical — suppress the badge-earned bell
        # notifications so existing students aren't hit with a burst of
        # (wrongly-framed "just earned") notifications at launch.
        with suppress_badge_notifications():
            for user in students:
                with transaction.atomic():
                    profile, _ = GameProfile.objects.get_or_create(user=user)

                    # Phase 65: the dedupe key is the target's content_key, so
                    # each loop fetches it alongside the id. The id still rides
                    # along as the audit trail of which pk paid.

                    # Lesson completions -> +50 each (source_type='lesson').
                    lessons = LessonProgress.objects.filter(
                        user=user, completed=True
                    ).values_list('lesson__content_key', 'lesson_id')
                    for content_key, lesson_id in lessons:
                        key = _key(content_key, XPEvent.SOURCE_LESSON, lesson_id)
                        if _award_xp(user, XPEvent.SOURCE_LESSON, key, XP_LESSON,
                                     source_id=lesson_id):
                            total_xp_events += 1

                    # Distinct passed unit quizzes -> +20 each (source_type='quiz').
                    quizzes = QuizAttempt.objects.filter(
                        student=user, passed=True
                    ).values_list('quiz__content_key', 'quiz_id').distinct()
                    for content_key, quiz_id in quizzes:
                        key = _key(content_key, XPEvent.SOURCE_QUIZ, quiz_id)
                        if _award_xp(user, XPEvent.SOURCE_QUIZ, key, XP_QUIZ,
                                     source_id=quiz_id):
                            total_xp_events += 1

                    # Distinct passed lesson quizzes -> +20 each ('lesson_quiz').
                    lesson_quizzes = LessonQuizAttempt.objects.filter(
                        user=user, passed=True
                    ).values_list('lesson__content_key', 'lesson_id').distinct()
                    for content_key, lesson_id in lesson_quizzes:
                        key = _key(content_key, XPEvent.SOURCE_LESSON_QUIZ, lesson_id)
                        if _award_xp(user, XPEvent.SOURCE_LESSON_QUIZ, key,
                                     XP_LESSON_QUIZ, source_id=lesson_id):
                            total_xp_events += 1

                    profile.refresh_from_db()
                    new_badges = _evaluate_badges(user, profile)
                    total_badges += len(new_badges)

        self.stdout.write(self.style.SUCCESS(
            f'Backfill complete: {students.count()} students, '
            f'{total_xp_events} new XP events, {total_badges} new badges.'
        ))
