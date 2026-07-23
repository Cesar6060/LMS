"""
Management command to clone JAVA101 into the public demo course DEMO101.

Phase 51: real students enroll in JAVA101, so the shared demo account moves
to its own cloned course. Visitors then never share rosters, discussions,
or leaderboards with real students.

The clone deep-copies course content: units -> lessons -> sections ->
lesson questions/choices, plus unit quizzes -> questions -> choices, with
lesson.required_quiz remapped to the cloned quiz. Lesson attachments
(uploaded files) are deliberately NOT copied — file storage is shared, and
deleting an attachment deletes its file, so shared references would be
destructive.

Idempotent: re-running wipes DEMO101's content and re-copies it from
JAVA101. The DEMO101 course row itself is preserved, so its
enrollment_code and existing enrollments survive. Demo-user progress rows
die with the old lessons — run `seed_demo_account --reset` afterwards to
restore the baseline.

Usage: python manage.py clone_course_for_demo
"""

from allauth.account.models import EmailAddress
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from courses.models import Course, Unit

SOURCE_CODE = 'JAVA101'
DEMO_CODE = 'DEMO101'
DEMO_TITLE = 'Java Fundamentals — Demo'
DEMO_INSTRUCTOR_EMAIL = 'instructor@demo.com'


def _clone(obj, **overrides):
    """Duplicate a model instance (all concrete fields) with overrides."""
    obj.pk = None
    obj._state.adding = True
    for field, value in overrides.items():
        setattr(obj, field, value)
    obj.save()
    return obj


class Command(BaseCommand):
    help = (
        f'Clones {SOURCE_CODE} into the public demo course {DEMO_CODE} '
        f'(owner {DEMO_INSTRUCTOR_EMAIL}). Idempotent: re-running refreshes '
        f'content and preserves the {DEMO_CODE} enrollment code.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            source = Course.objects.get(code=SOURCE_CODE)
        except Course.DoesNotExist:
            raise CommandError(
                f'Course {SOURCE_CODE} does not exist. Refusing to clone — '
                f'run populate_java_course first.'
            )

        owner = self._assert_demo_instructor()

        demo, created = Course.objects.get_or_create(
            code=DEMO_CODE,
            defaults={
                'title': DEMO_TITLE,
                'description': source.description,
                'instructor': owner,
            },
        )
        if not created:
            demo.title = DEMO_TITLE
            demo.description = source.description
            demo.instructor = owner
            demo.is_active = True
            demo.save()
            # Refresh: drop old content, keep the course row (and with it
            # the enrollment_code and any enrollments).
            demo.units.all().delete()

        counts = {'units': 0, 'lessons': 0, 'sections': 0,
                  'lesson questions': 0, 'quizzes': 0, 'quiz questions': 0}
        quiz_map = {}
        unit_pairs = []

        # Pass 1: units and their quizzes (so required_quiz can remap even
        # if a lesson references a quiz from another unit).
        for unit in source.units.order_by('order'):
            # _clone mutates the instance's pk in place — capture first.
            source_unit_pk = unit.pk
            quizzes = list(unit.quizzes.all())
            new_unit = _clone(unit, course=demo)
            counts['units'] += 1
            unit_pairs.append((source_unit_pk, new_unit))

            for quiz in quizzes:
                old_quiz_pk = quiz.pk
                questions = list(quiz.questions.all())
                new_quiz = _clone(quiz, unit=new_unit)
                quiz_map[old_quiz_pk] = new_quiz
                counts['quizzes'] += 1
                for question in questions:
                    choices = list(question.choices.all())
                    new_question = _clone(question, quiz=new_quiz)
                    counts['quiz questions'] += 1
                    for choice in choices:
                        _clone(choice, question=new_question)

        # Pass 2: lessons with sections and comprehension questions.
        for source_unit_pk, new_unit in unit_pairs:
            source_unit = Unit.objects.get(pk=source_unit_pk)
            for lesson in source_unit.lessons.order_by('order'):
                sections = list(lesson.sections.order_by('order'))
                questions = list(lesson.questions.order_by('order'))
                required_quiz = (
                    quiz_map.get(lesson.required_quiz_id)
                    if lesson.required_quiz_id else None
                )
                if lesson.required_quiz_id and required_quiz is None:
                    self.stderr.write(self.style.WARNING(
                        f'  Lesson "{lesson.title}": required quiz is not '
                        f'part of {SOURCE_CODE}; cleared on the clone.'
                    ))
                new_lesson = _clone(
                    lesson, unit=new_unit, required_quiz=required_quiz)
                counts['lessons'] += 1
                for section in sections:
                    _clone(section, lesson=new_lesson)
                    counts['sections'] += 1
                for question in questions:
                    choices = list(question.choices.all())
                    new_question = _clone(question, lesson=new_lesson)
                    counts['lesson questions'] += 1
                    for choice in choices:
                        _clone(choice, question=new_question)

        summary = ', '.join(f'{v} {k}' for k, v in counts.items())
        self.stdout.write(self.style.SUCCESS(
            f'{"Created" if created else "Refreshed"} {DEMO_CODE} '
            f'("{DEMO_TITLE}") from {SOURCE_CODE}: {summary}. '
            f'Enrollment code: {demo.enrollment_code}'
        ))

    def _assert_demo_instructor(self):
        """Create (or re-assert) the demo course's instructor account.

        The account owns DEMO101 only; nobody logs in as it, so it gets an
        unusable password.
        """
        user, created = User.objects.get_or_create(
            email=DEMO_INSTRUCTOR_EMAIL,
            defaults={
                'first_name': 'Demo',
                'last_name': 'Instructor',
                'is_instructor': True,
            },
        )
        if created:
            user.set_unusable_password()
            user.save()
        elif not user.is_instructor:
            user.is_instructor = True
            user.save(update_fields=['is_instructor'])

        EmailAddress.objects.get_or_create(
            user=user,
            email=DEMO_INSTRUCTOR_EMAIL,
            defaults={'verified': True, 'primary': True},
        )
        self.stdout.write(
            f'  {"Created" if created else "Found"} demo instructor '
            f'{DEMO_INSTRUCTOR_EMAIL}'
        )
        return user
