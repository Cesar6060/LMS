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

                    # Lesson completions -> +50 each (source_type='lesson').
                    lesson_ids = LessonProgress.objects.filter(
                        user=user, completed=True
                    ).values_list('lesson_id', flat=True)
                    for lesson_id in lesson_ids:
                        if _award_xp(user, XPEvent.SOURCE_LESSON, lesson_id, XP_LESSON):
                            total_xp_events += 1

                    # Distinct passed unit quizzes -> +20 each (source_type='quiz').
                    quiz_ids = QuizAttempt.objects.filter(
                        student=user, passed=True
                    ).values_list('quiz_id', flat=True).distinct()
                    for quiz_id in quiz_ids:
                        if _award_xp(user, XPEvent.SOURCE_QUIZ, quiz_id, XP_QUIZ):
                            total_xp_events += 1

                    # Distinct passed lesson quizzes -> +20 each ('lesson_quiz').
                    lq_lesson_ids = LessonQuizAttempt.objects.filter(
                        user=user, passed=True
                    ).values_list('lesson_id', flat=True).distinct()
                    for lesson_id in lq_lesson_ids:
                        if _award_xp(user, XPEvent.SOURCE_LESSON_QUIZ, lesson_id, XP_LESSON_QUIZ):
                            total_xp_events += 1

                    profile.refresh_from_db()
                    new_badges = _evaluate_badges(user, profile)
                    total_badges += len(new_badges)

        self.stdout.write(self.style.SUCCESS(
            f'Backfill complete: {students.count()} students, '
            f'{total_xp_events} new XP events, {total_badges} new badges.'
        ))
