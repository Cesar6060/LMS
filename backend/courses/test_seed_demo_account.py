"""
Tests for the seed_demo_account (Phase 41) and clone_course_for_demo
(Phase 51) management commands.

seed_demo_account manages the public portfolio demo account: a plain
student (jdoe@demo.com) enrolled in DEMO101 — the demo clone of JAVA101 —
with a fixed baseline of progress. clone_course_for_demo produces DEMO101.
"""

from io import BytesIO

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from PIL import Image as PILImage

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
def course_instructor():
    return User.objects.create_user(
        email='java-instructor@test.com',
        password='testpass123',
        is_instructor=True,
    )


@pytest.fixture
def demo_course(course_instructor):
    """DEMO101 with two units: Unit 1 (2 lessons), Unit 2 (2 lessons).

    Built directly rather than via clone_course_for_demo — seed_demo_account
    only cares that DEMO101 exists. The first Unit 2 lesson has 4 sections
    so the mid-lesson baseline (current_section = count // 2) lands on
    section 2.
    """
    course = Course.objects.create(
        code='DEMO101',
        title='Java Fundamentals — Demo',
        instructor=course_instructor,
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

    def test_creates_user_with_correct_flags_and_verified_email(self, demo_course):
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

    def test_enrolls_in_demo101_with_baseline_progress(self, demo_course):
        call_command('seed_demo_account')

        user = demo_user()
        enrollment = Enrollment.objects.get(user=user, course=demo_course)
        assert enrollment.is_active is True

        unit1_lessons = Lesson.objects.filter(unit__order=0, unit__course=demo_course)
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

    def test_errors_cleanly_when_demo101_absent(self):
        with pytest.raises(CommandError, match='DEMO101'):
            call_command('seed_demo_account')
        # Never creates the course, nor a half-configured user
        assert not Course.objects.filter(code='DEMO101').exists()
        assert not User.objects.filter(email=DEMO_EMAIL).exists()

    def test_plain_run_removes_enrollments_outside_demo101(
            self, demo_course, course_instructor):
        """Phase 51: the demo account must end up enrolled only in DEMO101,
        even without --reset (e.g. the legacy JAVA101 enrollment)."""
        call_command('seed_demo_account')
        user = demo_user()
        java = Course.objects.create(
            code='JAVA101', title='Introduction to Java',
            instructor=course_instructor,
        )
        Enrollment.objects.create(user=user, course=java)

        call_command('seed_demo_account')

        enrollments = Enrollment.objects.filter(user=user)
        assert enrollments.count() == 1
        assert enrollments.first().course == demo_course

    def test_running_twice_is_a_no_op(self, demo_course):
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

    def test_plain_rerun_does_not_downgrade_visitor_progress(self, demo_course):
        call_command('seed_demo_account')
        user = demo_user()
        partial = LessonProgress.objects.get(user=user, lesson__title='Number Types')
        partial.current_section = 3
        partial.save()

        call_command('seed_demo_account')

        partial.refresh_from_db()
        assert partial.current_section == 3

    def test_reset_wipes_extras_and_restores_baseline(self, demo_course, course_instructor):
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
        unit1 = Unit.objects.get(course=demo_course, order=0)
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
            course=demo_course, author=user, title='Spam', content='spam'
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
            code='CS101', title='Other', instructor=course_instructor
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
            course=demo_course, author=other, title='Legit', content='keep me'
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
        assert Enrollment.objects.filter(user=user, course=demo_course).exists()
        # Preferences back to defaults
        prefs = UserPreferences.objects.get(user=user)
        assert prefs.theme == 'system'
        # Non-demo data untouched
        assert LessonProgress.objects.filter(pk=other_progress.pk).exists()
        assert Thread.objects.filter(pk=other_thread.pk).exists()
        assert Badge.objects.filter(pk=badge.pk).exists()
        assert Quiz.objects.filter(pk=quiz.pk).exists()
        assert Question.objects.filter(pk=question.pk).exists()

    def test_never_leaves_privilege_flags_set(self, demo_course):
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


@pytest.fixture
def java_course(course_instructor):
    """A JAVA101 source course exercising every copied relation:
    units, lessons, sections, lesson questions/choices, and unit quizzes with
    questions/choices."""
    course = Course.objects.create(
        code='JAVA101',
        title='Introduction to Java',
        description='Learn Java.',
        instructor=course_instructor,
    )
    unit1 = Unit.objects.create(course=course, title='Getting Started', order=0)
    lesson1 = Lesson.objects.create(unit=unit1, title='Hello World', order=0)
    for i in range(3):
        LessonSection.objects.create(lesson=lesson1, title=f'Section {i}', order=i)
    lq = LessonQuestion.objects.create(lesson=lesson1, text='LQ?', order=1)
    LessonQuestionChoice.objects.create(question=lq, text='A', is_correct=True, order=1)
    LessonQuestionChoice.objects.create(question=lq, text='B', is_correct=False, order=2)

    quiz = Quiz.objects.create(unit=unit1, title='Unit 1 Quiz', points=10, passing_score=70)
    q = Question.objects.create(quiz=quiz, text='Q?', order=1)
    Choice.objects.create(question=q, text='A', is_correct=True, order=1)
    Choice.objects.create(question=q, text='B', is_correct=False, order=2)

    unit2 = Unit.objects.create(course=course, title='Variables', order=1)
    Lesson.objects.create(unit=unit2, title='Number Types', order=0)
    return course


def content_counts(course):
    return {
        'units': Unit.objects.filter(course=course).count(),
        'lessons': Lesson.objects.filter(unit__course=course).count(),
        'sections': LessonSection.objects.filter(lesson__unit__course=course).count(),
        'lesson_questions': LessonQuestion.objects.filter(lesson__unit__course=course).count(),
        'quizzes': Quiz.objects.filter(unit__course=course).count(),
        'quiz_questions': Question.objects.filter(quiz__unit__course=course).count(),
        'quiz_choices': Choice.objects.filter(question__quiz__unit__course=course).count(),
    }


@pytest.mark.django_db
class TestCloneCourseForDemo:

    def test_clones_all_content_with_demo_owner(self, java_course):
        call_command('clone_course_for_demo')

        demo = Course.objects.get(code='DEMO101')
        assert demo.title == 'Java Fundamentals — Demo'
        assert demo.instructor.email == 'instructor@demo.com'
        assert demo.instructor.is_instructor is True
        assert not demo.instructor.has_usable_password()
        assert content_counts(demo) == content_counts(java_course)

        # Every lesson lands under a unit of the *clone*, never the source.
        # (Phase 55 (C4) dropped `required_quiz`, so the old remap assertion
        # went with it — this keeps the "clone is self-contained" check.)
        cloned_lesson = Lesson.objects.get(
            unit__course=demo, title='Number Types')
        assert cloned_lesson.unit.course == demo

    def test_clone_preserves_section_layout(self, java_course):
        """Phase 60: a source section's `layout` survives the clone."""
        source_section = LessonSection.objects.get(
            lesson__unit__course=java_course, title='Section 1'
        )
        source_section.layout = 'slide'
        source_section.save(update_fields=['layout'])

        call_command('clone_course_for_demo')

        demo = Course.objects.get(code='DEMO101')
        cloned = LessonSection.objects.get(
            lesson__unit__course=demo, title='Section 1'
        )
        assert cloned.layout == 'slide'
        # Siblings keep the default.
        assert LessonSection.objects.get(
            lesson__unit__course=demo, title='Section 0'
        ).layout == 'doc'

    def test_rerun_is_idempotent_and_preserves_enrollment_code(self, java_course):
        call_command('clone_course_for_demo')
        demo = Course.objects.get(code='DEMO101')
        first_counts = content_counts(demo)
        first_code = demo.enrollment_code

        call_command('clone_course_for_demo')

        assert Course.objects.filter(code='DEMO101').count() == 1
        demo.refresh_from_db()
        assert content_counts(demo) == first_counts
        assert demo.enrollment_code == first_code
        # Source untouched
        assert content_counts(java_course) == first_counts

    def test_refuses_without_java101(self):
        with pytest.raises(CommandError, match='JAVA101'):
            call_command('clone_course_for_demo')
        assert not Course.objects.filter(code='DEMO101').exists()

    def test_clone_then_seed_leaves_demo_only_in_demo101(self, java_course):
        """End-to-end demo separation: after clone + seed, the demo account
        is enrolled in DEMO101 and nowhere else."""
        # Legacy state: demo user enrolled in JAVA101.
        legacy = User.objects.create_user(email=DEMO_EMAIL, password='x')
        Enrollment.objects.create(user=legacy, course=java_course)

        call_command('clone_course_for_demo')
        call_command('seed_demo_account')

        user = demo_user()
        enrollments = Enrollment.objects.filter(user=user)
        assert enrollments.count() == 1
        assert enrollments.first().course.code == 'DEMO101'


def png_bytes():
    buf = BytesIO()
    PILImage.new('RGB', (4, 4), color=(10, 120, 60)).save(buf, format='PNG')
    return buf.getvalue()


@pytest.mark.django_db
class TestCloneSlideImages:
    """Phase 61: clone_course_for_demo duplicates slide image blobs so the
    original and the clone never share a storage object (the section DELETE
    view deletes the blob with the row), and re-runs delete the previous
    demo copies instead of orphaning them."""

    @pytest.fixture(autouse=True)
    def media_tmp(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path

    @pytest.fixture
    def source_slide(self, java_course):
        section = LessonSection.objects.get(
            lesson__unit__course=java_course, title='Section 1')
        section.layout = 'slide'
        section.image_alt = 'A diagram'
        section.save(update_fields=['layout', 'image_alt'])
        section.image.save('deck-page.png', ContentFile(png_bytes()), save=True)
        return section

    def demo_clone_of(self, source_section):
        return LessonSection.objects.get(
            lesson__unit__course__code='DEMO101', title=source_section.title)

    def test_clone_duplicates_image_blob(self, source_slide):
        call_command('clone_course_for_demo')

        cloned = self.demo_clone_of(source_slide)
        storage = cloned.image.storage
        assert cloned.image
        assert cloned.image_alt == 'A diagram'
        assert cloned.layout == 'slide'
        # Its own object, not a shared reference to the source's file.
        assert cloned.image.name != source_slide.image.name
        assert storage.exists(source_slide.image.name)
        assert storage.exists(cloned.image.name)

        # Deleting the original's blob must leave the clone's file intact.
        source_slide.image.delete(save=False)
        assert storage.exists(cloned.image.name)

    def test_sections_without_images_clone_without_blobs(self, source_slide):
        call_command('clone_course_for_demo')

        sibling = LessonSection.objects.get(
            lesson__unit__course__code='DEMO101', title='Section 0')
        assert not sibling.image

    def test_rerun_deletes_previous_demo_blobs(self, source_slide):
        call_command('clone_course_for_demo')
        first_clone = self.demo_clone_of(source_slide)
        first_name = first_clone.image.name
        storage = first_clone.image.storage
        assert storage.exists(first_name)

        call_command('clone_course_for_demo')

        # The refresh replaced the demo sections; the old copy's blob must
        # not be orphaned in storage.
        assert not storage.exists(first_name)
        second_clone = self.demo_clone_of(source_slide)
        assert second_clone.image.name != first_name
        assert storage.exists(second_clone.image.name)
        # Source blob untouched by the refresh.
        assert storage.exists(source_slide.image.name)


# --------------------------------------------------------------------------
# Phase 65 — the clone is an upsert, and its keys are demo:-prefixed
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestCloneContentKeys:
    """
    ``_clone`` used to copy every concrete field, which after Phase 65 would
    have carried the source's ``content_key`` into DEMO101 and blown the
    unique index on the first run. Every clone now derives ``demo:<source
    key>`` instead — stable across re-clones, distinct from the source.
    """

    def test_first_clone_succeeds_and_keys_are_demo_prefixed(self, java_course):
        call_command('clone_course_for_demo')

        demo = Course.objects.get(code='DEMO101')
        lesson_keys = list(
            Lesson.objects.filter(unit__course=demo)
            .values_list('content_key', flat=True)
        )
        quiz_keys = list(
            Quiz.objects.filter(unit__course=demo)
            .values_list('content_key', flat=True)
        )
        assert lesson_keys and quiz_keys
        assert all(k.startswith('demo:') for k in lesson_keys + quiz_keys)

    def test_demo_keys_never_collide_with_the_source(self, java_course):
        call_command('clone_course_for_demo')

        demo = Course.objects.get(code='DEMO101')
        source_keys = set(
            Lesson.objects.filter(unit__course=java_course)
            .values_list('content_key', flat=True)
        )
        demo_keys = set(
            Lesson.objects.filter(unit__course=demo)
            .values_list('content_key', flat=True)
        )
        assert source_keys and demo_keys
        assert source_keys.isdisjoint(demo_keys)

    def test_reclone_is_stable_and_keeps_demo_lesson_pks(self, java_course):
        """The headline: a refresh updates in place, it does not re-create."""
        call_command('clone_course_for_demo')
        demo = Course.objects.get(code='DEMO101')
        before = dict(
            Lesson.objects.filter(unit__course=demo)
            .values_list('content_key', 'pk')
        )
        quiz_before = dict(
            Quiz.objects.filter(unit__course=demo)
            .values_list('content_key', 'pk')
        )

        call_command('clone_course_for_demo')
        call_command('clone_course_for_demo')

        after = dict(
            Lesson.objects.filter(unit__course=demo)
            .values_list('content_key', 'pk')
        )
        quiz_after = dict(
            Quiz.objects.filter(unit__course=demo)
            .values_list('content_key', 'pk')
        )
        assert after == before
        assert quiz_after == quiz_before

    def test_reclone_preserves_demo_student_progress(self, java_course):
        """
        The reason the wipe had to go: demo progress used to die on every
        refresh. Content that still exists in the source now survives.
        """
        call_command('clone_course_for_demo')
        demo = Course.objects.get(code='DEMO101')
        lesson = Lesson.objects.filter(unit__course=demo).order_by('pk').first()
        visitor = User.objects.create_user(
            email='demo-visitor@test.com', password='pw', is_instructor=False
        )
        progress = LessonProgress.objects.create(
            user=visitor, lesson=lesson, completed=True
        )

        call_command('clone_course_for_demo')

        progress.refresh_from_db()
        assert progress.completed is True
        assert progress.lesson_id == lesson.pk

    def test_reclone_drops_content_the_source_no_longer_has(self, java_course):
        """DEMO101 is a mirror, so its prune is unconditional."""
        call_command('clone_course_for_demo')
        demo = Course.objects.get(code='DEMO101')
        before = Lesson.objects.filter(unit__course=demo).count()

        Lesson.objects.filter(
            unit__course=java_course, title='Number Types'
        ).delete()
        call_command('clone_course_for_demo')

        titles = set(
            Lesson.objects.filter(unit__course=demo).values_list('title', flat=True)
        )
        assert 'Number Types' not in titles
        assert Lesson.objects.filter(unit__course=demo).count() == before - 1

    def test_source_content_is_not_re_keyed_by_the_clone(self, java_course):
        before = dict(
            Lesson.objects.filter(unit__course=java_course)
            .values_list('pk', 'content_key')
        )
        call_command('clone_course_for_demo')
        after = dict(
            Lesson.objects.filter(unit__course=java_course)
            .values_list('pk', 'content_key')
        )
        assert after == before
