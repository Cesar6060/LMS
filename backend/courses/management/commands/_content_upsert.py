"""
Shared upsert helpers for the content seed commands (Phase 65).

The leading underscore keeps Django from registering this module as a
management command.

WHY THIS EXISTS
---------------
``populate_robotics_course`` and ``populate_java_course`` used to begin every
run with ``course.units.all().delete()``. That cascade destroyed the Lessons
and Quizzes *and* every student's ``LessonProgress``, ``QuizAttempt``,
``LessonQuizAttempt``, ``AttemptAnswer``, ``LessonQuestionAnswer`` and
``LessonAttemptAnswer`` rows. The seeds now upsert instead, so a rebuild
touches content only and student work survives it.

The upsert goes all the way down (decision 7). Sections, lesson questions,
quiz questions and choices are matched on ``(parent, order)`` and updated in
place, so the question primary keys survive — and with them the three
student-owned tables that CASCADE off a question. Upserting a choice in place
also avoids the ``SET_NULL`` path on ``AttemptAnswer.selected_choice`` and
``LessonQuestionAnswer.selected_choice``; the latter matters because
``LessonQuestionAnswer.save()`` recomputes ``is_correct`` from the choice, so a
NULLed choice would silently rewrite a student's answer to *incorrect*.

Accepted tradeoff: children are keyed POSITIONALLY, so reordering questions in
a blueprint re-associates historical answers. Acceptable — they carry no XP,
the reorder is rare and deliberate, and giving every choice a slug is not worth
it. Lessons and quizzes, which DO carry XP, are keyed by author-chosen slug
instead and never positionally once keyed.

Every helper is pure DB work with no stdout, returns the object, and is safe to
call repeatedly. Anomalies go to the module logger, not the command's output.
"""
import logging
from collections import namedtuple

from django.db.models import Max

from courses.models import (
    Lesson, LessonQuestion, LessonQuestionChoice, LessonSection, Unit,
)
from quizzes.models import Choice, Question, Quiz

logger = logging.getLogger(__name__)

# Lessons are unique on ``(unit, order)``, so moving one into an occupied slot
# needs the occupant out of the way first. Displaced rows are parked above this
# offset and settled back into real orders by ``prune_stale``, which always
# runs. A parked row is either blueprint-absent content (reported, or deleted
# under --prune) or a lesson the blueprint reordered past.
PARK_OFFSET = 900_000

PruneReport = namedtuple('PruneReport', 'lessons quizzes units deleted')


def is_adoptable(content_key):
    """
    Whether a row at a blueprint position may be adopted and stamped with the
    blueprint's key (decision 5).

    True for content nobody authored a key for: unkeyed rows (only possible
    mid-deploy) and ``auto:``-prefixed rows, which is what existing prod
    content and instructor-created content carry. A row already holding a
    different authored key is NEVER re-keyed — that would move a student's XP
    onto different content, which is exactly what positional keys were
    rejected for (decision 2).
    """
    return not content_key or content_key.startswith('auto:')


def _park_conflicts(model, unit, order, keep_pk=None):
    """Move anything else sitting at ``(unit, order)`` out of the way."""
    conflicting = model.objects.filter(unit=unit, order=order)
    if keep_pk is not None:
        conflicting = conflicting.exclude(pk=keep_pk)
    for row in conflicting:
        row.order = PARK_OFFSET + row.pk
        row.save(update_fields=['order'])


def _delete_lesson_blobs(lessons):
    """
    Drop the storage objects behind a lesson's slide images before its rows go.

    The cascade takes the ``LessonSection`` rows but not the blobs they point
    at, so without this every prune orphans a deck's worth of R2 objects. Same
    rule as ``clone_course_for_demo``.
    """
    lesson_ids = [lesson.pk for lesson in lessons]
    if not lesson_ids:
        return
    for section in LessonSection.objects.filter(
        lesson_id__in=lesson_ids
    ).exclude(image=''):
        section.image.delete(save=False)


def _lowest_pk_dedup(queryset, label):
    """
    Return the lowest-pk row of ``queryset``, deleting any duplicates.

    ``Quiz``, ``quizzes.Question``, ``quizzes.Choice`` and ``LessonQuestion``
    carry no ``(parent, order)`` uniqueness, so prod may already hold duplicate
    rows from an earlier destructive reseed. Adding the constraints could fail
    the migration against unknown data (out of scope this phase), so the
    helpers are defensive instead: keep the oldest, drop the rest, say so.
    """
    rows = list(queryset.order_by('pk'))
    if not rows:
        return None
    if len(rows) > 1:
        logger.warning(
            'Duplicate %s rows found (%d); keeping pk=%s and deleting %s',
            label, len(rows), rows[0].pk, [r.pk for r in rows[1:]],
        )
        for extra in rows[1:]:
            extra.delete()
    return rows[0]


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------

def upsert_unit(course, order, title):
    """Get-or-update the unit at ``(course, order)`` — already unique_together."""
    unit, _created = Unit.objects.update_or_create(
        course=course, order=order, defaults={'title': title},
    )
    return unit


# ---------------------------------------------------------------------------
# Lessons and quizzes — the XP-carrying rows, keyed by author-chosen slug
# ---------------------------------------------------------------------------

def upsert_lesson(unit, key, order, **fields):
    """
    Get-or-create the lesson identified by ``key``, at ``(unit, order)``.

    Match order:
    1. by ``content_key`` — the identity match, and the only one that runs on a
       course that has been seeded before;
    2. failing that, adopt the row at ``(unit, order)`` IF its key is adoptable
       (see ``is_adoptable``), stamping the blueprint key onto it. This is how
       existing prod content joins the scheme with no manual step and no course
       content hardcoded into a migration;
    3. failing that, create.

    The lesson keeps its primary key through every rebuild, which is what keeps
    ``LessonProgress`` and the comprehension-quiz tables alive.
    """
    lesson = Lesson.objects.filter(content_key=key).first()

    if lesson is None:
        candidate = Lesson.objects.filter(unit=unit, order=order).first()
        if candidate is not None and is_adoptable(candidate.content_key):
            candidate.content_key = key
            lesson = candidate

    if lesson is None:
        _park_conflicts(Lesson, unit, order)
        return Lesson.objects.create(
            unit=unit, content_key=key, order=order, **fields
        )

    _park_conflicts(Lesson, unit, order, keep_pk=lesson.pk)
    lesson.unit = unit
    lesson.order = order
    for field, value in fields.items():
        setattr(lesson, field, value)
    lesson.save()
    return lesson


def upsert_quiz(unit, key, order, **fields):
    """
    Get-or-create the quiz identified by ``key``, at ``(unit, order)``.

    Same adoption rule as ``upsert_lesson``. ``Quiz`` has no ``(unit, order)``
    uniqueness, so the positional lookup takes the lowest-pk match and logs a
    warning when there is more than one — and no parking is needed, because
    nothing stops two quizzes sharing an order.
    """
    quiz = Quiz.objects.filter(content_key=key).first()

    if quiz is None:
        matches = list(Quiz.objects.filter(unit=unit, order=order).order_by('pk'))
        if len(matches) > 1:
            logger.warning(
                'Unit %s holds %d quizzes at order %s; adopting the lowest pk (%s)',
                unit.pk, len(matches), order, matches[0].pk,
            )
        if matches and is_adoptable(matches[0].content_key):
            quiz = matches[0]
            quiz.content_key = key

    if quiz is None:
        return Quiz.objects.create(unit=unit, content_key=key, order=order, **fields)

    quiz.unit = unit
    quiz.order = order
    for field, value in fields.items():
        setattr(quiz, field, value)
    quiz.save()
    return quiz


# ---------------------------------------------------------------------------
# Children — keyed positionally on (parent, order)
# ---------------------------------------------------------------------------

def upsert_sections(lesson, sections_data):
    """
    Upsert a lesson's sections on ``(lesson, order)``, deleting only the
    trailing extras beyond the end of ``sections_data``.

    Blobs behind removed sections are deleted explicitly — the row DELETE would
    otherwise leave the storage object orphaned on every reseed.
    """
    for i, section in enumerate(sections_data):
        LessonSection.objects.update_or_create(
            lesson=lesson, order=i,
            defaults={
                'title': section.get('title', ''),
                'content': section.get('content', ''),
                'video_type': section.get('video_type', 'none'),
                'video_id': section.get('video_id', ''),
            },
        )

    stale = LessonSection.objects.filter(lesson=lesson, order__gte=len(sections_data))
    for section in stale.exclude(image=''):
        section.image.delete(save=False)
    stale.delete()


def _upsert_choices(question, choice_model, fk_name, choices):
    """Upsert one question's choices on ``(question, order)``; drop the extras."""
    for j, (choice_text, is_correct) in enumerate(choices):
        existing = _lowest_pk_dedup(
            choice_model.objects.filter(**{fk_name: question}, order=j),
            f'{choice_model.__name__}(question={question.pk}, order={j})',
        )
        if existing is None:
            choice_model.objects.create(
                **{fk_name: question}, text=choice_text,
                is_correct=is_correct, order=j,
            )
            continue
        # Updated in place so the pk survives: a delete-and-recreate here would
        # SET_NULL every student selection pointing at it.
        existing.text = choice_text
        existing.is_correct = is_correct
        existing.save(update_fields=['text', 'is_correct'])

    choice_model.objects.filter(
        **{fk_name: question}, order__gte=len(choices)
    ).delete()


def upsert_lesson_questions(lesson, questions_data):
    """
    Upsert a lesson's comprehension questions on ``(lesson, order)``.

    ``questions_data`` items are ``{'text': ..., 'choices': [(text, correct)]}``
    with the choices already in their final stored order.

    Phase-55 invariant, preserved: a seeded lesson has the ``requires_quiz``
    gate on if and only if it has questions. An empty ``questions_data`` is an
    early return rather than a wipe — the blueprints never move a lesson from
    having questions to having none, and deleting a student's answer history on
    the strength of that guess is not a trade this helper should make.
    """
    if not questions_data:
        return

    for i, q in enumerate(questions_data):
        question = _lowest_pk_dedup(
            LessonQuestion.objects.filter(lesson=lesson, order=i),
            f'LessonQuestion(lesson={lesson.pk}, order={i})',
        )
        if question is None:
            question = LessonQuestion.objects.create(
                lesson=lesson, text=q['text'], order=i,
            )
        elif question.text != q['text']:
            question.text = q['text']
            question.save(update_fields=['text', 'updated_at'])
        _upsert_choices(question, LessonQuestionChoice, 'question', q['choices'])

    LessonQuestion.objects.filter(
        lesson=lesson, order__gte=len(questions_data)
    ).delete()

    if not lesson.requires_quiz:
        lesson.requires_quiz = True
        lesson.save(update_fields=['requires_quiz'])


def upsert_quiz_questions(quiz, questions_data):
    """Upsert a unit quiz's questions on ``(quiz, order)``. See above."""
    for i, q in enumerate(questions_data):
        question = _lowest_pk_dedup(
            Question.objects.filter(quiz=quiz, order=i),
            f'Question(quiz={quiz.pk}, order={i})',
        )
        if question is None:
            question = Question.objects.create(quiz=quiz, text=q['text'], order=i)
        elif question.text != q['text']:
            question.text = q['text']
            question.save(update_fields=['text'])
        _upsert_choices(question, Choice, 'question', q['choices'])

    Question.objects.filter(quiz=quiz, order__gte=len(questions_data)).delete()


# ---------------------------------------------------------------------------
# Pruning
# ---------------------------------------------------------------------------

def _delete_keeping_pk(obj):
    """
    Delete ``obj``, leaving its primary key readable on the instance.

    Django nulls ``pk`` after a delete, which would make the returned
    ``PruneReport`` useless for the one thing a caller wants it for — telling
    the operator exactly which rows just went.
    """
    pk = obj.pk
    obj.delete()
    obj.pk = pk


def _settle_parked_orders(course):
    """
    Give any lesson parked by ``_park_conflicts`` a real order again, appended
    after the blueprint's own lessons in its unit.

    Runs on every seed, pruning or not, so a default run never leaves a course
    holding lessons at order 900000+.
    """
    for unit in course.units.all():
        parked = list(unit.lessons.filter(order__gte=PARK_OFFSET).order_by('order'))
        if not parked:
            continue
        highest = unit.lessons.exclude(order__gte=PARK_OFFSET).aggregate(
            Max('order')
        )['order__max']
        next_order = 0 if highest is None else highest + 1
        for lesson in parked:
            lesson.order = next_order
            lesson.save(update_fields=['order'])
            next_order += 1


def prune_stale(course, seen_lesson_keys, seen_quiz_keys, *, dry_run=True):
    """
    The content in ``course`` this run did not touch.

    ``dry_run`` (the default) only reports — a plain seed run creates, updates,
    warns, and deletes nothing (decision 6). ``--prune`` opts into the deletion,
    which still cascades student progress for the removed lesson; that is the
    point of making it explicit rather than the default it used to be.

    A unit counts as stale when none of its lessons or quizzes were seen.
    Returns a ``PruneReport``; parked orders are settled either way.
    """
    stale_lessons = list(
        Lesson.objects.filter(unit__course=course).exclude(
            content_key__in=seen_lesson_keys
        ).select_related('unit')
    )
    stale_quizzes = list(
        Quiz.objects.filter(unit__course=course).exclude(
            content_key__in=seen_quiz_keys
        ).select_related('unit')
    )

    live_unit_ids = set(
        Lesson.objects.filter(
            unit__course=course, content_key__in=seen_lesson_keys
        ).values_list('unit_id', flat=True)
    ) | set(
        Quiz.objects.filter(
            unit__course=course, content_key__in=seen_quiz_keys
        ).values_list('unit_id', flat=True)
    )
    stale_units = [u for u in course.units.all() if u.pk not in live_unit_ids]

    if not dry_run:
        _delete_lesson_blobs(stale_lessons)
        for lesson in stale_lessons:
            _delete_keeping_pk(lesson)
        for quiz in stale_quizzes:
            _delete_keeping_pk(quiz)
        for unit in stale_units:
            # Any surviving lesson under a stale unit would go with it; there
            # are none by construction, but clear the blobs regardless.
            _delete_lesson_blobs(list(unit.lessons.all()))
            _delete_keeping_pk(unit)

    _settle_parked_orders(course)

    return PruneReport(
        lessons=stale_lessons,
        quizzes=stale_quizzes,
        units=stale_units,
        deleted=not dry_run,
    )
