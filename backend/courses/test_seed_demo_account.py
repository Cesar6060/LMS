"""
Tests for the seed_demo_account management command (Phase 41).

The command manages the public portfolio demo account: a plain student
(jdoe@demo.com) enrolled in JAVA101 with a fixed baseline of progress.
"""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import User, UserPreferences
from allauth.account.models import EmailAddress
from discussions.models import Thread, Reply
from gamification.models import Badge, GameProfile, UserBadge, XPEvent
from notifications.models import Notification
from quizzes.models import Quiz, Question, Choice, QuizAttempt, AttemptAnswer
from .models import (
    Course, Unit, Lesson, LessonSection, Enrollment, LessonProgress,
    LessonQuestion, LessonQuestionChoice, LessonQuizAttempt,
    LessonAttemptAnswer,
)

DEMO_EMAIL = 'jdoe@demo.com'
DEMO_PASSWORD = 'Admin123!'


@pytest.fixture
def java_instructor():
    return User.objects.create_user(
        email='java-instructor@test.com',
        password='testpass123',
        is_instructor=True,
    )


@pytest.fixture
def java_course(java_instructor):
    """JAVA101 with two units: Unit 1 (2 lessons), Unit 2 (2 lessons).

    The first Unit 2 lesson has 4 sections so the mid-lesson baseline
    (current_section = count // 2) lands on section 2.
    """
    course = Course.objects.create(
        code='JAVA101',
        title='Introduction to Java',
        instructor=java_instructor,
    )
    unit1 = Unit.objects.create(course=course, title='Getting Started', order=0)
    Lesson.objects.create(unit=unit1, title='Hello World', order=0)
    Lesson.objects.create(unit=unit1, title='Comments', order=1)
    unit2 = Unit.objects.create(course=course, title='Variables & Operators', order=1)
    lesson = Lesson.objects.create(unit=unit2, title='Number Types', order=0)
    for i in range(4):
        LessonSection.objects.create(lesson=lesson, title=f'Section {i}', order=i)
    Lesson.objects.create(unit=unit2, title='Text and Boolean Types', order=1)
    return course


def demo_user():
    return User.objects.get(email=DEMO_EMAIL)


@pytest.mark.django_db
class TestSeedDemoAccount:

    def test_creates_user_with_correct_flags_and_verified_email(self, java_course):
        call_command('seed_demo_account')

        user = demo_user()
        assert user.first_name == 'Jordan'
        assert user.last_name == 'Doe'
        assert user.is_instructor is False
        assert user.is_staff is False
        assert user.is_superuser is False
        assert user.is_active is True
        assert user.check_password(DEMO_PASSWORD)

        email = EmailAddress.objects.get(user=user, email=DEMO_EMAIL)
        assert email.verified is True
        assert email.primary is True

    def test_enrolls_in_java101_with_baseline_progress(self, java_course):
        call_command('seed_demo_account')

        user = demo_user()
        enrollment = Enrollment.objects.get(user=user, course=java_course)
        assert enrollment.is_active is True

        unit1_lessons = Lesson.objects.filter(unit__order=0, unit__course=java_course)
        for lesson in unit1_lessons:
            progress = LessonProgress.objects.get(user=user, lesson=lesson)
            assert progress.completed is True
            assert progress.completed_at is not None

        partial = LessonProgress.objects.get(user=user, lesson__title='Number Types')
        assert partial.completed is False
        assert partial.completed_at is None
        assert partial.current_section == 2  # 4 sections // 2

        # Nothing beyond: unit1 (2) + first unit2 lesson (1) = 3 rows total
        assert LessonProgress.objects.filter(user=user).count() == 3

    def test_errors_cleanly_when_java101_absent(self):
        with pytest.raises(CommandError, match='JAVA101'):
            call_command('seed_demo_account')
        # Never creates the course, nor a half-configured user
        assert not Course.objects.filter(code='JAVA101').exists()
        assert not User.objects.filter(email=DEMO_EMAIL).exists()

    def test_running_twice_is_a_no_op(self, java_course):
        call_command('seed_demo_account')
        user = demo_user()
        first_run = {
            p.lesson_id: (p.completed, p.completed_at, p.current_section)
            for p in LessonProgress.objects.filter(user=user)
        }

        call_command('seed_demo_account')

        user.refresh_from_db()
        assert user.check_password(DEMO_PASSWORD)
        assert not (user.is_staff or user.is_superuser or user.is_instructor)
        assert User.objects.filter(email=DEMO_EMAIL).count() == 1
        assert EmailAddress.objects.filter(user=user).count() == 1
        assert Enrollment.objects.filter(user=user).count() == 1
        second_run = {
            p.lesson_id: (p.completed, p.completed_at, p.current_section)
            for p in LessonProgress.objects.filter(user=user)
        }
        assert second_run == first_run

    def test_plain_rerun_does_not_downgrade_visitor_progress(self, java_course):
        call_command('seed_demo_account')
        user = demo_user()
        partial = LessonProgress.objects.get(user=user, lesson__title='Number Types')
        partial.current_section = 3
        partial.save()

        call_command('seed_demo_account')

        partial.refresh_from_db()
        assert partial.current_section == 3

    def test_reset_wipes_extras_and_restores_baseline(self, java_course, java_instructor):
        call_command('seed_demo_account')
        user = demo_user()

        # --- Simulate a visitor trashing the account ---
        # Progress beyond baseline + advanced partial lesson
        beyond = Lesson.objects.get(title='Text and Boolean Types')
        LessonProgress.objects.create(user=user, lesson=beyond, completed=True)
        partial = LessonProgress.objects.get(user=user, lesson__title='Number Types')
        partial.completed = True
        partial.current_section = 3
        partial.save()
        # Unit quiz attempt with answers
        unit1 = Unit.objects.get(course=java_course, order=0)
        quiz = Quiz.objects.create(unit=unit1, title='Unit 1 Quiz')
        question = Question.objects.create(quiz=quiz, text='Q?', order=1)
        choice = Choice.objects.create(question=question, text='A', is_correct=True, order=1)
        attempt = QuizAttempt.objects.create(quiz=quiz, student=user, score=100, passed=True)
        AttemptAnswer.objects.create(
            attempt=attempt, question=question, selected_choice=choice, is_correct=True
        )
        # Lesson-quiz attempt with answers
        lesson1 = Lesson.objects.get(title='Hello World')
        lq = LessonQuestion.objects.create(lesson=lesson1, text='LQ?', order=1)
        lq_choice = LessonQuestionChoice.objects.create(
            question=lq, text='A', is_correct=True, order=1
        )
        lesson_attempt = LessonQuizAttempt.objects.create(
            user=user, lesson=lesson1, score=1, total_questions=1, passed=True
        )
        LessonAttemptAnswer.objects.create(
            attempt=lesson_attempt, question=lq, selected_choice=lq_choice, is_correct=True
        )
        # Discussion thread + reply, notification, gamification, preferences
        thread = Thread.objects.create(
            course=java_course, author=user, title='Spam', content='spam'
        )
        Reply.objects.create(thread=thread, author=user, content='more spam')
        Notification.objects.create(
            recipient=user, type='reply', title='n', message='m'
        )
        badge = Badge.objects.create(
            key='first-lesson', name='First!', description='d', icon='🏅',
            criteria_type='lessons_done', threshold=1,
        )
        GameProfile.objects.create(user=user, total_xp=500, mascot_name='Hacked')
        XPEvent.objects.create(user=user, source_type='lesson', source_id=1, amount=500)
        UserBadge.objects.create(user=user, badge=badge)
        prefs = user.preferences
        prefs.theme = 'dark'
        prefs.save()
        # Enrolled themselves in another course
        other_course = Course.objects.create(
            code='CS101', title='Other', instructor=java_instructor
        )
        Enrollment.objects.create(user=user, course=other_course)
        # Changed profile via settings
        user.first_name = 'Hacker'
        user.set_password('changed-by-visitor')
        user.save()

        # Another user's data must survive the reset untouched
        other = User.objects.create_user(email='other@test.com', password='x')
        other_progress = LessonProgress.objects.create(
            user=other, lesson=beyond, completed=True
        )
        other_thread = Thread.objects.create(
            course=java_course, author=other, title='Legit', content='keep me'
        )

        call_command('seed_demo_account', '--reset')

        user.refresh_from_db()
        assert user.first_name == 'Jordan'
        assert user.check_password(DEMO_PASSWORD)
        # Baseline shape restored exactly
        assert LessonProgress.objects.filter(user=user).count() == 3
        partial = LessonProgress.objects.get(user=user, lesson__title='Number Types')
        assert partial.completed is False
        assert partial.completed_at is None
        assert partial.current_section == 2
        assert not LessonProgress.objects.filter(user=user, lesson=beyond).exists()
        # Extras wiped
        assert not QuizAttempt.objects.filter(student=user).exists()
        assert not AttemptAnswer.objects.filter(attempt__student=user).exists()
        assert not LessonQuizAttempt.objects.filter(user=user).exists()
        assert not LessonAttemptAnswer.objects.filter(attempt__user=user).exists()
        assert not Thread.objects.filter(author=user).exists()
        assert not Reply.objects.filter(author=user).exists()
        assert not Notification.objects.filter(recipient=user).exists()
        assert not GameProfile.objects.filter(user=user).exists()
        assert not XPEvent.objects.filter(user=user).exists()
        assert not UserBadge.objects.filter(user=user).exists()
        assert not Enrollment.objects.filter(user=user, course=other_course).exists()
        assert Enrollment.objects.filter(user=user, course=java_course).exists()
        # Preferences back to defaults
        prefs = UserPreferences.objects.get(user=user)
        assert prefs.theme == 'system'
        # Non-demo data untouched
        assert LessonProgress.objects.filter(pk=other_progress.pk).exists()
        assert Thread.objects.filter(pk=other_thread.pk).exists()
        assert Badge.objects.filter(pk=badge.pk).exists()
        assert Quiz.objects.filter(pk=quiz.pk).exists()
        assert Question.objects.filter(pk=question.pk).exists()

    def test_never_leaves_privilege_flags_set(self, java_course):
        # Even if someone escalated the account in /admin/, the command
        # forces it back to a plain student.
        User.objects.create_user(
            email=DEMO_EMAIL, password='x',
            is_instructor=True, is_staff=True, is_superuser=True,
        )

        call_command('seed_demo_account')

        user = demo_user()
        assert user.is_instructor is False
        assert user.is_staff is False
        assert user.is_superuser is False
