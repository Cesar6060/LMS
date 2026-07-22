"""
Management command to create/reset the public portfolio demo account.

The demo account (settings.DEMO_ACCOUNT_EMAIL, default jdoe@demo.com) is a
plain student enrolled in JAVA101 with a fixed baseline of progress: all
Unit 1 lessons completed, first Unit 2 lesson partially read. Every visitor
shares it via the one-click demo login, so anything the account owns is
world-editable — this command re-asserts the baseline.

Usage: python manage.py seed_demo_account           (create / re-assert)
       python manage.py seed_demo_account --reset   (wipe visitor changes,
                                                     restore exact baseline)

Safe to run against production (see docs/runbooks/phase-38-deploy-steps.txt
Step 1 for the DATABASE_URL pattern). Every write is scoped to the demo
user; course content and other users are never touched.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User, UserPreferences
from allauth.account.models import EmailAddress
from courses.models import (
    Course, Enrollment, LessonProgress, LessonQuestionAnswer,
    LessonQuizAttempt,
)
from discussions.models import Thread, Reply
from gamification.models import GameProfile, XPEvent, UserBadge
from notifications.models import Notification
from quizzes.models import QuizAttempt

# Email and password come from settings (DEMO_ACCOUNT_EMAIL /
# DEMO_ACCOUNT_PASSWORD) so production can rotate the password via env var.
DEMO_FIRST_NAME = 'Jordan'
DEMO_LAST_NAME = 'Doe'
COURSE_CODE = 'JAVA101'


class Command(BaseCommand):
    help = (
        'Creates or resets the public demo student account '
        f'(settings.DEMO_ACCOUNT_EMAIL, enrolled in {COURSE_CODE} with '
        f'baseline progress)'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete everything the demo user owns beyond the baseline '
                 '(progress, quiz attempts, posts, notifications, XP/badges, '
                 'preference changes), then restore the exact baseline.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            course = Course.objects.get(code=COURSE_CODE)
        except Course.DoesNotExist:
            raise CommandError(
                f'Course {COURSE_CODE} does not exist. Refusing to create it — '
                f'run populate_java_course first.'
            )

        units = list(course.units.order_by('order'))
        if len(units) < 2:
            raise CommandError(
                f'{COURSE_CODE} has {len(units)} unit(s); need at least 2 '
                f'to apply the baseline (Unit 1 complete, Unit 2 started).'
            )

        user = self._assert_account()

        if options['reset']:
            self._wipe_visitor_data(user, course)

        enrollment, _ = Enrollment.objects.get_or_create(user=user, course=course)
        if not enrollment.is_active:
            enrollment.is_active = True
            enrollment.save(update_fields=['is_active'])

        self._apply_baseline_progress(user, units, force=options['reset'])

        self.stdout.write(self.style.SUCCESS(
            f'Demo account ready: {settings.DEMO_ACCOUNT_EMAIL} enrolled in '
            f'{COURSE_CODE}'
            + (' (reset to baseline)' if options['reset'] else '')
        ))

    def _assert_account(self):
        """Create the demo user, or force it back to known-good state."""
        demo_email = settings.DEMO_ACCOUNT_EMAIL
        user, created = User.objects.get_or_create(
            email=demo_email,
            defaults={
                'first_name': DEMO_FIRST_NAME,
                'last_name': DEMO_LAST_NAME,
                'is_instructor': False,
            }
        )

        # Re-assert everything a visitor could have changed via settings —
        # and, defensively, privilege flags that must never be true even if
        # someone flipped them in /admin/.
        user.first_name = DEMO_FIRST_NAME
        user.last_name = DEMO_LAST_NAME
        user.is_instructor = False
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True
        user.set_password(settings.DEMO_ACCOUNT_PASSWORD)
        user.save()

        # Verified allauth email is required for login.
        email_address, _ = EmailAddress.objects.get_or_create(
            user=user,
            email=demo_email,
            defaults={'verified': True, 'primary': True}
        )
        if not (email_address.verified and email_address.primary):
            email_address.verified = True
            email_address.primary = True
            email_address.save(update_fields=['verified', 'primary'])
        EmailAddress.objects.filter(user=user).exclude(email=demo_email).delete()

        self.stdout.write(
            f'  {"Created" if created else "Re-asserted"} user {demo_email} '
            f'(student, verified email)'
        )
        return user

    def _wipe_visitor_data(self, user, course):
        """Delete every row the demo user owns beyond the baseline.

        Everything here is scoped to the demo user; cascades only follow
        rows the demo user owns (e.g. replies under the demo user's threads).
        """
        deleted = {
            'lesson progress': LessonProgress.objects.filter(user=user).delete()[0],
            'unit-quiz attempts': QuizAttempt.objects.filter(student=user).delete()[0],
            'lesson-quiz attempts': LessonQuizAttempt.objects.filter(user=user).delete()[0],
            'lesson-question answers': LessonQuestionAnswer.objects.filter(user=user).delete()[0],
            'replies': Reply.objects.filter(author=user).delete()[0],
            'threads': Thread.objects.filter(author=user).delete()[0],
            'notifications': Notification.objects.filter(recipient=user).delete()[0],
            'XP events': XPEvent.objects.filter(user=user).delete()[0],
            'badges': UserBadge.objects.filter(user=user).delete()[0],
            'game profile': GameProfile.objects.filter(user=user).delete()[0],
            'other enrollments': Enrollment.objects.filter(user=user).exclude(course=course).delete()[0],
        }

        # Preferences back to defaults (theme, timezone, avatar, emails).
        UserPreferences.objects.filter(user=user).delete()
        UserPreferences.objects.get_or_create(user=user)

        summary = ', '.join(f'{count} {label}' for label, count in deleted.items() if count)
        self.stdout.write(f'  Wiped visitor data: {summary or "nothing to wipe"}')

    def _apply_baseline_progress(self, user, units, force=False):
        """Baseline: Unit 1 fully complete, first Unit 2 lesson mid-read.

        Without --reset this only fills gaps (never downgrades progress a
        visitor legitimately made); with --reset it sets the exact shape.
        """
        unit1, unit2 = units[0], units[1]

        for lesson in unit1.lessons.order_by('order'):
            progress, created = LessonProgress.objects.get_or_create(
                user=user,
                lesson=lesson,
                defaults={'completed': True, 'completed_at': timezone.now()},
            )
            if not created and not progress.completed:
                progress.completed = True
                progress.completed_at = timezone.now()
                progress.save(update_fields=['completed', 'completed_at'])

        first_lesson = unit2.lessons.order_by('order').first()
        if first_lesson is None:
            raise CommandError(
                f'{COURSE_CODE} unit "{unit2.title}" has no lessons; '
                f'cannot apply partial-read baseline.'
            )
        mid_section = first_lesson.sections.count() // 2
        progress, created = LessonProgress.objects.get_or_create(
            user=user,
            lesson=first_lesson,
            defaults={'completed': False, 'current_section': mid_section},
        )
        if force and not created:
            progress.completed = False
            progress.completed_at = None
            progress.current_section = mid_section
            progress.video_position = 0
            progress.save()

        self.stdout.write(
            f'  Baseline progress: "{unit1.title}" complete, '
            f'"{first_lesson.title}" at section {mid_section}'
        )
