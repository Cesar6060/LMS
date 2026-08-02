"""
Tests for ``courses.management.commands._content_upsert`` (Phase 65).

This module is where the real risk of the phase lives — not in the 8,000 lines
of curriculum prose that call into it. Each helper gets its own test, and the
survival of the three student-owned answer tables is asserted directly rather
than inferred from "the seed ran clean".
"""
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import User
from courses.models import (
    Course, Lesson, LessonAttemptAnswer, LessonProgress, LessonQuestion,
    LessonQuestionAnswer, LessonQuestionChoice, LessonQuizAttempt,
    LessonSection, Unit,
)
from quizzes.models import AttemptAnswer, Choice, Question, Quiz, QuizAttempt

from courses.management.commands._content_upsert import (
    PARK_OFFSET, is_adoptable, prune_stale, upsert_lesson,
    upsert_lesson_questions, upsert_quiz, upsert_quiz_questions,
    upsert_sections, upsert_unit,
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def instructor():
    return User.objects.create_user(
        email='upsert-instructor@test.com', password='pw', is_instructor=True
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        email='upsert-student@test.com', password='pw', is_instructor=False
    )


@pytest.fixture
def course(instructor):
    return Course.objects.create(
        code='UPS101', title='Upsert Course', instructor=instructor
    )


@pytest.fixture
def unit(course):
    return Unit.objects.create(course=course, title='Unit 1', order=0)


QUESTIONS = [
    {
        'text': 'What does a sensor do?',
        'choices': [
            ('It measures something about the world', True),
            ('It stores program code', False),
            ('It supplies power', False),
        ],
    },
    {
        'text': 'What does an actuator do?',
        'choices': [
            ('It makes something move', True),
            ('It measures temperature', False),
        ],
    },
]


def _tiny_image():
    """A 1x1 GIF — enough for storage to write a real object."""
    return SimpleUploadedFile(
        'slide.gif',
        b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
        b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00'
        b'\x00\x02\x02D\x01\x00;',
        content_type='image/gif',
    )


# --------------------------------------------------------------------------
# is_adoptable / upsert_unit
# --------------------------------------------------------------------------

@pytest.mark.parametrize('key,expected', [
    (None, True),
    ('', True),
    ('auto:deadbeef', True),
    ('rob101-what-is-a-robot', False),
    ('demo:java101-hello-world', False),
    ('seed:vgd101-intro', False),
])
def test_is_adoptable(key, expected):
    assert is_adoptable(key) is expected


@pytest.mark.django_db
class TestUpsertUnit:
    def test_creates_then_updates_in_place(self, course):
        first = upsert_unit(course, 0, 'Original title')
        second = upsert_unit(course, 0, 'Renamed title')

        assert second.pk == first.pk
        assert second.title == 'Renamed title'
        assert course.units.count() == 1


# --------------------------------------------------------------------------
# upsert_lesson — the adoption rule (decision 5)
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestUpsertLesson:
    def test_creates_with_the_blueprint_key(self, unit):
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        assert lesson.content_key == 'ups101-intro'
        assert lesson.title == 'Intro'

    def test_second_run_keeps_the_same_pk(self, unit):
        first = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        second = upsert_lesson(unit, 'ups101-intro', 0, title='Intro, revised')

        assert second.pk == first.pk
        assert second.title == 'Intro, revised'
        assert Lesson.objects.filter(unit=unit).count() == 1

    def test_adopts_an_auto_keyed_row_at_the_blueprint_position(self, unit):
        """How existing prod content joins the scheme, with no manual step."""
        existing = Lesson.objects.create(unit=unit, title='Intro', order=0)
        assert existing.content_key.startswith('auto:')

        adopted = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')

        assert adopted.pk == existing.pk
        assert adopted.content_key == 'ups101-intro'
        assert Lesson.objects.filter(unit=unit).count() == 1

    def test_adopts_an_unkeyed_row(self, unit):
        """A null key is only reachable mid-deploy, but must still adopt."""
        existing = Lesson.objects.create(
            unit=unit, title='Intro', order=0, content_key=None,
        )
        adopted = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')

        assert adopted.pk == existing.pk
        assert adopted.content_key == 'ups101-intro'

    def test_refuses_to_re_key_a_row_holding_a_different_blueprint_key(self, unit):
        """
        Re-keying by position would transfer one lesson's XP to another — the
        exact failure mode positional keys were rejected for (decision 2).
        """
        squatter = Lesson.objects.create(
            unit=unit, title='Sensors', order=0, content_key='ups101-sensors',
        )

        created = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')

        assert created.pk != squatter.pk
        assert created.content_key == 'ups101-intro'
        squatter.refresh_from_db()
        assert squatter.content_key == 'ups101-sensors'
        # The squatter was moved out of the contested slot, not destroyed.
        assert Lesson.objects.filter(pk=squatter.pk).exists()

    def test_adoption_never_steals_a_keyed_lesson_progress(self, unit, student):
        squatter = Lesson.objects.create(
            unit=unit, title='Sensors', order=0, content_key='ups101-sensors',
        )
        LessonProgress.objects.create(user=student, lesson=squatter, completed=True)

        upsert_lesson(unit, 'ups101-intro', 0, title='Intro')

        progress = LessonProgress.objects.get(user=student)
        assert progress.lesson_id == squatter.pk

    def test_keyed_lesson_follows_its_key_across_units(self, course, unit):
        """A lesson may move between units without becoming new content."""
        other = Unit.objects.create(course=course, title='Unit 2', order=1)
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')

        moved = upsert_lesson(other, 'ups101-intro', 0, title='Intro')

        assert moved.pk == lesson.pk
        assert moved.unit_id == other.pk

    def test_reorder_parks_the_displaced_lesson_instead_of_colliding(self, unit):
        """
        Lessons are unique on (unit, order), so swapping two of them has to
        move the occupant out of the way first.
        """
        a = upsert_lesson(unit, 'ups101-a', 0, title='A')
        b = upsert_lesson(unit, 'ups101-b', 1, title='B')

        # Blueprint now lists B first.
        upsert_lesson(unit, 'ups101-b', 0, title='B')
        upsert_lesson(unit, 'ups101-a', 1, title='A')

        a.refresh_from_db()
        b.refresh_from_db()
        assert (b.order, a.order) == (0, 1)
        assert Lesson.objects.filter(unit=unit).count() == 2


# --------------------------------------------------------------------------
# upsert_quiz
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestUpsertQuiz:
    def test_second_run_keeps_the_same_pk(self, unit):
        first = upsert_quiz(unit, 'ups101-quiz-1', 0, title='Quiz 1')
        second = upsert_quiz(unit, 'ups101-quiz-1', 0, title='Quiz 1 revised')

        assert second.pk == first.pk
        assert second.title == 'Quiz 1 revised'
        assert Quiz.objects.filter(unit=unit).count() == 1

    def test_adopts_an_auto_keyed_quiz_at_the_position(self, unit):
        existing = Quiz.objects.create(unit=unit, title='Quiz 1', order=0)
        adopted = upsert_quiz(unit, 'ups101-quiz-1', 0, title='Quiz 1')

        assert adopted.pk == existing.pk
        assert adopted.content_key == 'ups101-quiz-1'

    def test_refuses_to_re_key_an_authored_quiz(self, unit):
        squatter = Quiz.objects.create(
            unit=unit, title='Other', order=0, content_key='ups101-quiz-other',
        )
        created = upsert_quiz(unit, 'ups101-quiz-1', 0, title='Quiz 1')

        assert created.pk != squatter.pk
        squatter.refresh_from_db()
        assert squatter.content_key == 'ups101-quiz-other'

    def test_pre_existing_duplicate_position_takes_the_lowest_pk(self, unit, caplog):
        """
        Quiz has no (unit, order) uniqueness, so prod may already hold
        duplicates from an earlier destructive reseed. Adopt the oldest.
        """
        older = Quiz.objects.create(unit=unit, title='Quiz 1', order=0)
        newer = Quiz.objects.create(unit=unit, title='Quiz 1 dup', order=0)
        assert newer.pk > older.pk

        with caplog.at_level('WARNING'):
            adopted = upsert_quiz(unit, 'ups101-quiz-1', 0, title='Quiz 1')

        assert adopted.pk == older.pk
        assert 'quizzes at order' in caplog.text

    def test_quiz_attempts_survive_a_reseed(self, unit, student):
        quiz = upsert_quiz(unit, 'ups101-quiz-1', 0, title='Quiz 1')
        QuizAttempt.objects.create(
            quiz=quiz, student=student, score=90, passed=True
        )

        upsert_quiz(unit, 'ups101-quiz-1', 0, title='Quiz 1')

        assert QuizAttempt.objects.filter(student=student, quiz=quiz).count() == 1


# --------------------------------------------------------------------------
# upsert_sections
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestUpsertSections:
    def test_creates_updates_in_place_and_deletes_trailing_extras(self, unit):
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        upsert_sections(lesson, [
            {'title': 'One', 'content': 'first'},
            {'title': 'Two', 'content': 'second'},
            {'title': 'Three', 'content': 'third'},
        ])
        pks = list(
            LessonSection.objects.filter(lesson=lesson)
            .order_by('order').values_list('pk', flat=True)
        )

        upsert_sections(lesson, [
            {'title': 'One', 'content': 'first, edited'},
            {'title': 'Two', 'content': 'second'},
        ])

        remaining = list(LessonSection.objects.filter(lesson=lesson).order_by('order'))
        assert [s.pk for s in remaining] == pks[:2]
        assert remaining[0].content == 'first, edited'

    def test_video_fields_round_trip(self, unit):
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        upsert_sections(lesson, [
            {'title': 'Watch', 'content': '', 'video_type': 'youtube',
             'video_id': 'abc123'},
        ])
        section = LessonSection.objects.get(lesson=lesson)
        assert (section.video_type, section.video_id) == ('youtube', 'abc123')

    def test_removed_section_takes_its_image_blob_with_it(
        self, unit, django_capture_on_commit_callbacks
    ):
        """
        Without this the row DELETE orphans the storage object, and every
        reseed leaks a deck's worth of R2 blobs.

        The delete is deferred to ``on_commit`` on purpose — storage is not
        transactional, so dropping the blob inline and then rolling back would
        leave surviving rows pointing at objects that are gone.
        """
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        upsert_sections(lesson, [
            {'title': 'One', 'content': 'a'},
            {'title': 'Two', 'content': 'b'},
        ])
        doomed = LessonSection.objects.get(lesson=lesson, order=1)
        doomed.image.save('slide.gif', _tiny_image(), save=True)
        doomed.refresh_from_db()
        storage = doomed.image.storage
        blob_name = doomed.image.name
        assert storage.exists(blob_name)

        with django_capture_on_commit_callbacks(execute=True):
            upsert_sections(lesson, [{'title': 'One', 'content': 'a'}])

        assert not LessonSection.objects.filter(lesson=lesson, order=1).exists()
        assert not storage.exists(blob_name)

    def test_blob_delete_is_deferred_until_commit(
        self, unit, django_capture_on_commit_callbacks
    ):
        """A rollback must not leave a live row pointing at a deleted object."""
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        upsert_sections(lesson, [
            {'title': 'One', 'content': 'a'},
            {'title': 'Two', 'content': 'b'},
        ])
        doomed = LessonSection.objects.get(lesson=lesson, order=1)
        doomed.image.save('slide.gif', _tiny_image(), save=True)
        doomed.refresh_from_db()
        storage, blob_name = doomed.image.storage, doomed.image.name

        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            upsert_sections(lesson, [{'title': 'One', 'content': 'a'}])
            # Row is gone, blob is not — the delete is still pending.
            assert storage.exists(blob_name)

        assert len(callbacks) == 1
        storage.delete(blob_name)

    def test_surviving_section_keeps_its_image(self, unit):
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        upsert_sections(lesson, [{'title': 'One', 'content': 'a'}])
        kept = LessonSection.objects.get(lesson=lesson, order=0)
        kept.image.save('slide.gif', _tiny_image(), save=True)
        blob_name = kept.image.name

        upsert_sections(lesson, [{'title': 'One', 'content': 'a, edited'}])

        kept.refresh_from_db()
        assert kept.image.name == blob_name
        assert kept.image.storage.exists(blob_name)


# --------------------------------------------------------------------------
# upsert_lesson_questions — the student-owned tables that CASCADE off a question
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestUpsertLessonQuestions:
    def test_creates_questions_and_gates_the_lesson(self, unit):
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        assert lesson.requires_quiz is False

        upsert_lesson_questions(lesson, QUESTIONS)

        lesson.refresh_from_db()
        assert lesson.requires_quiz is True
        assert LessonQuestion.objects.filter(lesson=lesson).count() == 2
        assert LessonQuestionChoice.objects.filter(question__lesson=lesson).count() == 5

    def test_empty_questions_data_is_an_early_return(self, unit):
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        upsert_lesson_questions(lesson, QUESTIONS)

        upsert_lesson_questions(lesson, [])

        assert LessonQuestion.objects.filter(lesson=lesson).count() == 2

    def test_question_pks_survive_a_reseed(self, unit):
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        upsert_lesson_questions(lesson, QUESTIONS)
        pks = list(
            LessonQuestion.objects.filter(lesson=lesson)
            .order_by('order').values_list('pk', flat=True)
        )

        upsert_lesson_questions(lesson, QUESTIONS)

        assert list(
            LessonQuestion.objects.filter(lesson=lesson)
            .order_by('order').values_list('pk', flat=True)
        ) == pks

    def test_lesson_question_answer_survives_a_reseed(self, unit, student):
        """``LessonQuestionAnswer`` CASCADEs off the question."""
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        upsert_lesson_questions(lesson, QUESTIONS)
        question = LessonQuestion.objects.get(lesson=lesson, order=0)
        choice = question.choices.get(order=0)
        answer = LessonQuestionAnswer.objects.create(
            user=student, question=question, selected_choice=choice,
            is_correct=True,
        )

        upsert_lesson_questions(lesson, QUESTIONS)

        answer.refresh_from_db()
        assert answer.selected_choice_id == choice.pk
        assert answer.is_correct is True

    def test_lesson_attempt_answer_survives_a_reseed(self, unit, student):
        """``LessonAttemptAnswer`` CASCADEs off the question too."""
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        upsert_lesson_questions(lesson, QUESTIONS)
        question = LessonQuestion.objects.get(lesson=lesson, order=0)
        choice = question.choices.get(order=0)
        attempt = LessonQuizAttempt.objects.create(
            user=student, lesson=lesson, score=1, total_questions=2, passed=False,
        )
        session_answer = LessonAttemptAnswer.objects.create(
            attempt=attempt, question=question, selected_choice=choice,
            is_correct=True,
        )

        upsert_lesson_questions(lesson, QUESTIONS)

        session_answer.refresh_from_db()
        assert session_answer.selected_choice_id == choice.pk
        assert LessonQuizAttempt.objects.filter(user=student, lesson=lesson).exists()

    def test_edited_choice_text_keeps_the_choice_pk(self, unit, student):
        """
        The silent-wrong-answer case. Deleting and recreating a choice
        SET_NULLs the student's selection, and ``LessonQuestionAnswer.save()``
        recomputes ``is_correct`` from the choice — so a NULLed choice would
        rewrite a correct answer to incorrect the next time the row is saved.
        """
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        upsert_lesson_questions(lesson, QUESTIONS)
        question = LessonQuestion.objects.get(lesson=lesson, order=0)
        choice = question.choices.get(order=0)
        answer = LessonQuestionAnswer.objects.create(
            user=student, question=question, selected_choice=choice,
            is_correct=True,
        )

        reworded = [
            {
                'text': QUESTIONS[0]['text'],
                'choices': [
                    ('It measures something about the world around it', True),
                    ('It stores program code', False),
                    ('It supplies power', False),
                ],
            },
            QUESTIONS[1],
        ]
        upsert_lesson_questions(lesson, reworded)

        answer.refresh_from_db()
        assert answer.selected_choice_id == choice.pk
        choice.refresh_from_db()
        assert choice.text == 'It measures something about the world around it'
        assert choice.is_correct is True
        # The re-save that would have flipped it now still sees a correct choice.
        answer.save()
        answer.refresh_from_db()
        assert answer.is_correct is True

    def test_trailing_questions_and_choices_are_deleted(self, unit):
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        upsert_lesson_questions(lesson, QUESTIONS)

        shortened = [{
            'text': QUESTIONS[0]['text'],
            'choices': QUESTIONS[0]['choices'][:2],
        }]
        upsert_lesson_questions(lesson, shortened)

        assert LessonQuestion.objects.filter(lesson=lesson).count() == 1
        assert LessonQuestionChoice.objects.filter(question__lesson=lesson).count() == 2

    def test_reworded_question_text_is_updated_in_place(self, unit):
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        upsert_lesson_questions(lesson, QUESTIONS)
        pk = LessonQuestion.objects.get(lesson=lesson, order=0).pk

        upsert_lesson_questions(lesson, [
            {'text': 'What, precisely, does a sensor do?',
             'choices': QUESTIONS[0]['choices']},
            QUESTIONS[1],
        ])

        question = LessonQuestion.objects.get(lesson=lesson, order=0)
        assert question.pk == pk
        assert question.text == 'What, precisely, does a sensor do?'

    def test_pre_existing_duplicate_question_position_is_deduped(self, unit, caplog):
        lesson = upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        older = LessonQuestion.objects.create(lesson=lesson, text='Q', order=0)
        LessonQuestion.objects.create(lesson=lesson, text='Q dup', order=0)

        with caplog.at_level('WARNING'):
            upsert_lesson_questions(lesson, [QUESTIONS[0]])

        remaining = LessonQuestion.objects.filter(lesson=lesson)
        assert remaining.count() == 1
        assert remaining.first().pk == older.pk
        assert 'Duplicate LessonQuestion' in caplog.text


# --------------------------------------------------------------------------
# upsert_quiz_questions — AttemptAnswer is the table at risk here
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestUpsertQuizQuestions:
    def test_attempt_answer_survives_a_reseed(self, unit, student):
        quiz = upsert_quiz(unit, 'ups101-quiz-1', 0, title='Quiz 1')
        upsert_quiz_questions(quiz, QUESTIONS)
        question = Question.objects.get(quiz=quiz, order=0)
        choice = question.choices.get(order=0)
        attempt = QuizAttempt.objects.create(
            quiz=quiz, student=student, score=100, passed=True
        )
        answer = AttemptAnswer.objects.create(
            attempt=attempt, question=question, selected_choice=choice,
            is_correct=True,
        )

        upsert_quiz_questions(quiz, QUESTIONS)

        answer.refresh_from_db()
        assert answer.question_id == question.pk
        assert answer.selected_choice_id == choice.pk
        assert answer.is_correct is True

    def test_question_and_choice_pks_are_stable(self, unit):
        quiz = upsert_quiz(unit, 'ups101-quiz-1', 0, title='Quiz 1')
        upsert_quiz_questions(quiz, QUESTIONS)
        before = list(
            Choice.objects.filter(question__quiz=quiz)
            .order_by('question__order', 'order').values_list('pk', flat=True)
        )

        upsert_quiz_questions(quiz, QUESTIONS)

        after = list(
            Choice.objects.filter(question__quiz=quiz)
            .order_by('question__order', 'order').values_list('pk', flat=True)
        )
        assert after == before

    def test_trailing_questions_deleted(self, unit):
        quiz = upsert_quiz(unit, 'ups101-quiz-1', 0, title='Quiz 1')
        upsert_quiz_questions(quiz, QUESTIONS)

        upsert_quiz_questions(quiz, QUESTIONS[:1])

        assert Question.objects.filter(quiz=quiz).count() == 1

    def test_choice_correctness_can_be_corrected_in_place(self, unit):
        quiz = upsert_quiz(unit, 'ups101-quiz-1', 0, title='Quiz 1')
        upsert_quiz_questions(quiz, QUESTIONS[:1])
        pks = list(
            Choice.objects.filter(question__quiz=quiz)
            .order_by('order').values_list('pk', flat=True)
        )

        upsert_quiz_questions(quiz, [{
            'text': QUESTIONS[0]['text'],
            'choices': [
                ('It measures something about the world', False),
                ('It stores program code', True),
                ('It supplies power', False),
            ],
        }])

        choices = list(
            Choice.objects.filter(question__quiz=quiz).order_by('order')
        )
        assert [c.pk for c in choices] == pks
        assert [c.is_correct for c in choices] == [False, True, False]


# --------------------------------------------------------------------------
# prune_stale
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestPruneStale:
    def _seed(self, course):
        unit = upsert_unit(course, 0, 'Unit 1')
        kept = upsert_lesson(unit, 'ups101-keep', 0, title='Keep')
        quiz = upsert_quiz(unit, 'ups101-quiz-1', 0, title='Quiz 1')
        return unit, kept, quiz

    def test_dry_run_reports_and_deletes_nothing(self, course):
        unit, kept, quiz = self._seed(course)
        stray = Lesson.objects.create(unit=unit, title='Stray', order=5)

        report = prune_stale(
            course, {'ups101-keep'}, {'ups101-quiz-1'}, dry_run=True
        )

        assert report.deleted is False
        assert [lesson.pk for lesson in report.lessons] == [stray.pk]
        assert report.quizzes == []
        assert report.units == []
        assert Lesson.objects.filter(pk=stray.pk).exists()

    def test_prune_deletes_blueprint_absent_content(self, course):
        unit, kept, quiz = self._seed(course)
        stray = Lesson.objects.create(unit=unit, title='Stray', order=5)
        stray_quiz = Quiz.objects.create(unit=unit, title='Stray quiz', order=5)

        report = prune_stale(
            course, {'ups101-keep'}, {'ups101-quiz-1'}, dry_run=False
        )

        assert report.deleted is True
        assert not Lesson.objects.filter(pk=stray.pk).exists()
        assert not Quiz.objects.filter(pk=stray_quiz.pk).exists()
        assert Lesson.objects.filter(pk=kept.pk).exists()
        assert Quiz.objects.filter(pk=quiz.pk).exists()

    def test_prune_reports_a_wholly_untouched_unit(self, course):
        self._seed(course)
        orphan_unit = Unit.objects.create(course=course, title='Retired', order=9)
        Lesson.objects.create(unit=orphan_unit, title='Retired lesson', order=0)

        report = prune_stale(
            course, {'ups101-keep'}, {'ups101-quiz-1'}, dry_run=False
        )

        assert [u.pk for u in report.units] == [orphan_unit.pk]
        assert not Unit.objects.filter(pk=orphan_unit.pk).exists()

    def test_prune_deletes_slide_blobs_of_removed_lessons(
        self, course, django_capture_on_commit_callbacks
    ):
        unit, _kept, _quiz = self._seed(course)
        stray = Lesson.objects.create(unit=unit, title='Stray', order=5)
        section = LessonSection.objects.create(lesson=stray, title='S', order=0)
        section.image.save('slide.gif', _tiny_image(), save=True)
        section.refresh_from_db()
        storage, blob_name = section.image.storage, section.image.name
        assert storage.exists(blob_name)

        with django_capture_on_commit_callbacks(execute=True):
            prune_stale(course, {'ups101-keep'}, {'ups101-quiz-1'}, dry_run=False)

        assert not storage.exists(blob_name)

    def test_parked_orders_are_settled_even_on_a_dry_run(self, course):
        unit = upsert_unit(course, 0, 'Unit 1')
        squatter = Lesson.objects.create(
            unit=unit, title='Squatter', order=0, content_key='ups101-squatter',
        )
        upsert_lesson(unit, 'ups101-keep', 0, title='Keep')
        squatter.refresh_from_db()
        assert squatter.order >= PARK_OFFSET

        prune_stale(course, {'ups101-keep'}, set(), dry_run=True)

        squatter.refresh_from_db()
        assert squatter.order == 1
        assert Lesson.objects.filter(pk=squatter.pk).exists()


@pytest.mark.django_db
class TestNullKeyIsRejected:
    """
    ``filter(content_key=None)`` becomes ``IS NULL`` in SQL, which matches an
    arbitrary keyless row in ANY course. The upsert would reassign that row's
    unit, and because a null key can never match ``exclude(content_key__in=…)``
    ``prune_stale`` would then delete it — silent cross-course data loss.
    """

    @pytest.mark.parametrize('bad_key', [None, ''])
    def test_upsert_lesson_refuses_a_falsy_key(self, unit, bad_key):
        with pytest.raises(ValueError, match='non-empty content key'):
            upsert_lesson(unit, bad_key, 0, title='Intro')

    @pytest.mark.parametrize('bad_key', [None, ''])
    def test_upsert_quiz_refuses_a_falsy_key(self, unit, bad_key):
        with pytest.raises(ValueError, match='non-empty content key'):
            upsert_quiz(unit, bad_key, 0, title='Quiz')

    def test_a_keyless_lesson_in_another_course_is_never_hijacked(
        self, course, unit, instructor
    ):
        other_course = Course.objects.create(
            code='OTH101', title='Other', instructor=instructor
        )
        other_unit = Unit.objects.create(course=other_course, title='U', order=0)
        bystander = Lesson.objects.create(
            unit=other_unit, title='Bystander', order=0, content_key=None
        )

        upsert_lesson(unit, 'ups101-intro', 0, title='Intro')
        prune_stale(course, {'ups101-intro'}, set(), dry_run=False)

        bystander.refresh_from_db()
        assert bystander.unit_id == other_unit.pk
        assert Lesson.objects.filter(pk=bystander.pk).exists()


@pytest.mark.django_db
class TestCrossCourseKeyCollision:
    """
    Promoted from an adversarial probe, which proved these paths silently
    corrupted data before the guard existed.

    Matching by key is global, so a slug authored in two blueprints used to
    pull the row across the course boundary: the source course was emptied,
    its content overwritten, and every LessonProgress dragged along with the
    pk — leaving students "already complete" on content they never saw.
    Nothing writes `content_key` through the API, so this is an authoring
    mistake, and it now fails loudly instead of silently.
    """

    @pytest.fixture
    def other_course(self, instructor):
        course = Course.objects.create(
            code='OTH200', title='Other', instructor=instructor
        )
        return Unit.objects.create(course=course, title='U', order=0)

    def test_lesson_key_collision_across_courses_raises(self, unit, other_course):
        upsert_lesson(unit, 'ups101-shared', 0, title='Original')

        with pytest.raises(ValueError, match='already held by a lesson in course'):
            upsert_lesson(other_course, 'ups101-shared', 0, title='Impostor')

    def test_the_source_course_keeps_its_lesson_and_its_progress(
        self, unit, other_course, student
    ):
        lesson = upsert_lesson(unit, 'ups101-shared', 0, title='Original')
        LessonProgress.objects.create(user=student, lesson=lesson, completed=True)

        with pytest.raises(ValueError):
            upsert_lesson(other_course, 'ups101-shared', 0, title='Impostor')

        lesson.refresh_from_db()
        assert lesson.unit_id == unit.pk
        assert lesson.title == 'Original'
        assert Lesson.objects.filter(unit=unit).count() == 1
        assert LessonProgress.objects.get(user=student).lesson.unit.course_id == \
            unit.course_id

    def test_quiz_key_collision_across_courses_raises(self, unit, other_course):
        upsert_quiz(unit, 'ups101-quiz-shared', 0, title='Original')

        with pytest.raises(ValueError, match='already held by a quiz in course'):
            upsert_quiz(other_course, 'ups101-quiz-shared', 0, title='Impostor')

    def test_moving_between_units_of_the_SAME_course_is_still_allowed(
        self, course, unit
    ):
        """
        The guard must not break the intended case. Keys carry no unit number
        precisely so a lesson can move between units without becoming new
        content — that is a different course boundary question entirely.
        """
        other_unit = Unit.objects.create(course=course, title='Unit 2', order=1)
        lesson = upsert_lesson(unit, 'ups101-mobile', 0, title='Mobile')

        moved = upsert_lesson(other_unit, 'ups101-mobile', 0, title='Mobile')

        assert moved.pk == lesson.pk
        assert moved.unit_id == other_unit.pk
