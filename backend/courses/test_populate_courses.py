"""
Tests for ``populate_robotics_course`` and ``populate_java_course`` (Phase 65).

Before this phase neither command had ANY test coverage, and both opened every
run with ``course.units.all().delete()`` while their module docstrings claimed
to be NON-DESTRUCTIVE. The headline assertions here are the ones that make the
claim true: a second run moves no primary key and destroys no student work.

These run the real 8,000-line blueprints, so they are slower than the rest of
the suite. That is the point — the blueprint is the thing under test.
"""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import User
from courses.models import (
    Course, Lesson, LessonProgress, LessonQuestion, LessonQuestionAnswer,
    LessonSection, Unit,
)
from gamification.models import GameProfile, XPEvent
from gamification.services import award_lesson_completion
from quizzes.models import Question, Quiz, QuizAttempt

COMMANDS = [
    ('populate_robotics_course', 'ROB101', 6, 24, 6),
    ('populate_java_course', 'JAVA101', 5, 20, 5),
]


@pytest.fixture
def seed_instructor():
    """The instructor both commands look for by name."""
    return User.objects.create_user(
        email='cesar@test.com', password='pw', is_instructor=True,
        first_name='Cesar', last_name='Villarreal',
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        email='seed-student@test.com', password='pw', is_instructor=False
    )


def content_snapshot(code):
    return {
        'units': Unit.objects.filter(course__code=code).count(),
        'lessons': Lesson.objects.filter(unit__course__code=code).count(),
        'quizzes': Quiz.objects.filter(unit__course__code=code).count(),
        'sections': LessonSection.objects.filter(
            lesson__unit__course__code=code
        ).count(),
        'lesson_questions': LessonQuestion.objects.filter(
            lesson__unit__course__code=code
        ).count(),
        'quiz_questions': Question.objects.filter(
            quiz__unit__course__code=code
        ).count(),
    }


def lesson_pks(code):
    return dict(
        Lesson.objects.filter(unit__course__code=code)
        .values_list('content_key', 'pk')
    )


# --------------------------------------------------------------------------
# Shape of a fresh seed
# --------------------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize('command,code,units,lessons,quizzes', COMMANDS)
class TestSeedShape:
    def test_creates_the_expected_content(
        self, seed_instructor, command, code, units, lessons, quizzes
    ):
        call_command(command)

        snapshot = content_snapshot(code)
        assert snapshot['units'] == units
        assert snapshot['lessons'] == lessons
        assert snapshot['quizzes'] == quizzes
        assert Course.objects.get(code=code).instructor == seed_instructor

    def test_every_lesson_and_quiz_carries_a_blueprint_key(
        self, seed_instructor, command, code, units, lessons, quizzes
    ):
        call_command(command)

        prefix = code.lower()
        lesson_keys = list(
            Lesson.objects.filter(unit__course__code=code)
            .values_list('content_key', flat=True)
        )
        quiz_keys = list(
            Quiz.objects.filter(unit__course__code=code)
            .values_list('content_key', flat=True)
        )
        assert len(lesson_keys) == lessons
        assert len(quiz_keys) == quizzes
        assert all(k.startswith(f'{prefix}-') for k in lesson_keys + quiz_keys)
        # No auto: keys survive a seed run, and no key is used twice.
        assert not any(k.startswith('auto:') for k in lesson_keys + quiz_keys)
        assert len(set(lesson_keys + quiz_keys)) == lessons + quizzes

    def test_seeded_requires_quiz_matches_the_has_questions_rule(
        self, seed_instructor, command, code, units, lessons, quizzes
    ):
        """Phase-55 invariant, preserved through the upsert rewrite."""
        call_command(command)

        for lesson in Lesson.objects.filter(unit__course__code=code):
            has_questions = lesson.questions.exists()
            assert lesson.requires_quiz == has_questions, lesson.title


# --------------------------------------------------------------------------
# The headline guarantee: a second run is non-destructive
# --------------------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize('command,code,units,lessons,quizzes', COMMANDS)
class TestSecondRunIsNonDestructive:
    def test_counts_and_lesson_pks_are_identical(
        self, seed_instructor, command, code, units, lessons, quizzes
    ):
        call_command(command)
        before_counts = content_snapshot(code)
        before_pks = lesson_pks(code)
        before_quiz_pks = dict(
            Quiz.objects.filter(unit__course__code=code)
            .values_list('content_key', 'pk')
        )

        call_command(command)

        assert content_snapshot(code) == before_counts
        assert lesson_pks(code) == before_pks
        assert dict(
            Quiz.objects.filter(unit__course__code=code)
            .values_list('content_key', 'pk')
        ) == before_quiz_pks

    def test_student_progress_survives(
        self, seed_instructor, student, command, code, units, lessons, quizzes
    ):
        """
        The guarantee the whole phase exists for. Before Phase 65 every one of
        these rows was destroyed by the cascade behind ``units.all().delete()``.
        """
        call_command(command)
        lesson = Lesson.objects.filter(
            unit__course__code=code, requires_quiz=True
        ).order_by('pk').first()
        question = lesson.questions.order_by('order').first()
        choice = question.choices.order_by('order').first()
        quiz = Quiz.objects.filter(unit__course__code=code).order_by('pk').first()

        progress = LessonProgress.objects.create(
            user=student, lesson=lesson, completed=True
        )
        answer = LessonQuestionAnswer.objects.create(
            user=student, question=question, selected_choice=choice,
            is_correct=choice.is_correct,
        )
        attempt = QuizAttempt.objects.create(
            quiz=quiz, student=student, score=90, passed=True
        )

        call_command(command)

        progress.refresh_from_db()
        assert progress.completed is True
        assert progress.lesson_id == lesson.pk

        answer.refresh_from_db()
        assert answer.question_id == question.pk
        assert answer.selected_choice_id == choice.pk

        attempt.refresh_from_db()
        assert attempt.quiz_id == quiz.pk
        assert attempt.passed is True

    def test_student_xp_is_unchanged_after_a_reseed_and_re_completion(
        self, seed_instructor, student, command, code, units, lessons, quizzes
    ):
        """
        The bug in one test, at the command level: reseed, redo the lesson,
        and the student must not be paid twice.
        """
        call_command(command)
        lesson = Lesson.objects.filter(
            unit__course__code=code
        ).order_by('pk').first()
        award_lesson_completion(student, lesson)
        assert GameProfile.objects.get(user=student).total_xp == 50

        call_command(command)

        rebuilt = Lesson.objects.get(content_key=lesson.content_key)
        award_lesson_completion(student, rebuilt)

        assert GameProfile.objects.get(user=student).total_xp == 50
        assert XPEvent.objects.filter(user=student).count() == 1

    def test_edited_content_is_restored_without_re_creating_the_row(
        self, seed_instructor, command, code, units, lessons, quizzes
    ):
        """A refresh is still a refresh: content is corrected, in place."""
        call_command(command)
        lesson = Lesson.objects.filter(
            unit__course__code=code
        ).order_by('pk').first()
        original_title = lesson.title
        original_pk = lesson.pk
        Lesson.objects.filter(pk=lesson.pk).update(title='Vandalized')

        call_command(command)

        restored = Lesson.objects.get(content_key=lesson.content_key)
        assert restored.title == original_title
        assert restored.pk == original_pk


# --------------------------------------------------------------------------
# Adoption of pre-existing (unkeyed / auto:) production content
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestAdoption:
    def test_auto_keyed_row_at_the_blueprint_position_is_adopted(
        self, seed_instructor, student
    ):
        """
        How production content joins the scheme: no manual step, no course
        content hardcoded into a migration.
        """
        course = Course.objects.create(
            code='ROB101', title='Robotics 1', instructor=seed_instructor
        )
        unit = Unit.objects.create(
            course=course, title='Robots, Careers & Teamwork', order=0
        )
        pre_existing = Lesson.objects.create(
            unit=unit, title='What Is a Robot?', order=0
        )
        assert pre_existing.content_key.startswith('auto:')
        LessonProgress.objects.create(
            user=student, lesson=pre_existing, completed=True
        )

        call_command('populate_robotics_course')

        pre_existing.refresh_from_db()
        assert pre_existing.content_key == 'rob101-what-is-a-robot'
        assert LessonProgress.objects.get(user=student).lesson_id == pre_existing.pk

    def test_unkeyed_row_is_adopted_too(self, seed_instructor):
        """A null key is only reachable mid-deploy, but must still adopt."""
        course = Course.objects.create(
            code='ROB101', title='Robotics 1', instructor=seed_instructor
        )
        unit = Unit.objects.create(
            course=course, title='Robots, Careers & Teamwork', order=0
        )
        pre_existing = Lesson.objects.create(
            unit=unit, title='What Is a Robot?', order=0, content_key=None
        )

        call_command('populate_robotics_course')

        pre_existing.refresh_from_db()
        assert pre_existing.content_key == 'rob101-what-is-a-robot'

    def test_adoption_leaves_no_auto_keys_behind(self, seed_instructor):
        course = Course.objects.create(
            code='ROB101', title='Robotics 1', instructor=seed_instructor
        )
        unit = Unit.objects.create(
            course=course, title='Robots, Careers & Teamwork', order=0
        )
        for order, title in enumerate(
            ['What Is a Robot?', 'Careers in Robotics', 'Working on a Robotics Team']
        ):
            Lesson.objects.create(unit=unit, title=title, order=order)

        call_command('populate_robotics_course')

        assert not Lesson.objects.filter(
            unit__course__code='ROB101', content_key__startswith='auto:'
        ).exists()


# --------------------------------------------------------------------------
# --prune
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestPruneFlag:
    def _seed_with_a_stray(self, seed_instructor):
        call_command('populate_robotics_course')
        unit = Unit.objects.get(course__code='ROB101', order=0)
        stray = Lesson.objects.create(
            unit=unit, title='Retired lesson', order=90,
            content_key='rob101-retired',
        )
        return stray

    def test_default_run_warns_and_deletes_nothing(self, seed_instructor, capsys):
        stray = self._seed_with_a_stray(seed_instructor)

        call_command('populate_robotics_course')

        assert Lesson.objects.filter(pk=stray.pk).exists()
        output = capsys.readouterr().out
        assert 'Retired lesson' in output
        assert '--prune' in output

    def test_prune_deletes_the_stray(self, seed_instructor):
        stray = self._seed_with_a_stray(seed_instructor)

        call_command('populate_robotics_course', '--prune')

        assert not Lesson.objects.filter(pk=stray.pk).exists()
        # ...and the blueprint's own content is untouched.
        assert Lesson.objects.filter(unit__course__code='ROB101').count() == 24

    def test_prune_does_not_touch_another_course(self, seed_instructor):
        other = Course.objects.create(
            code='OTHER1', title='Other', instructor=seed_instructor
        )
        other_unit = Unit.objects.create(course=other, title='U', order=0)
        other_lesson = Lesson.objects.create(unit=other_unit, title='L', order=0)

        call_command('populate_robotics_course', '--prune')

        assert Lesson.objects.filter(pk=other_lesson.pk).exists()


# --------------------------------------------------------------------------
# Guard rails
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestInstructorGuard:
    def test_robotics_fails_loudly_without_the_instructor(self):
        """A seeding step must not silently no-op."""
        with pytest.raises(CommandError):
            call_command('populate_robotics_course')

    def test_robotics_ignores_a_student_namesake(self, seed_instructor):
        User.objects.create_user(
            email='impostor@test.com', password='pw', is_instructor=False,
            first_name='Cesar', last_name='Villarreal',
        )

        call_command('populate_robotics_course')

        assert Course.objects.get(code='ROB101').instructor == seed_instructor
