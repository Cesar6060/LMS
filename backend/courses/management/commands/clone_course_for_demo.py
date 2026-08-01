"""
Management command to clone JAVA101 into the public demo course DEMO101.

Phase 51: real students enroll in JAVA101, so the shared demo account moves
to its own cloned course. Visitors then never share rosters, discussions,
or leaderboards with real students.

The clone deep-copies course content: units -> lessons -> sections ->
lesson questions/choices, plus unit quizzes -> questions -> choices, with
Lesson attachments
(uploaded files) are deliberately NOT copied — file storage is shared, and
deleting an attachment deletes its file, so shared references would be
destructive.

Idempotent: re-running upserts DEMO101's content from JAVA101 (Phase 65 —
it used to wipe and re-copy). The DEMO101 course row is preserved, so its
enrollment_code and existing enrollments survive, and so now is its
content: demo-user progress against a lesson that still exists in JAVA101
survives a refresh instead of dying with the old rows.

DEMO101 is a derived mirror of JAVA101, so unlike the seed commands this
one prunes unconditionally — content the source no longer has must not
linger in the demo.

Usage: python manage.py clone_course_for_demo
"""

import os

from allauth.account.models import EmailAddress
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from courses.models import Course, LessonSection

from ._content_upsert import (
    prune_stale, upsert_lesson, upsert_lesson_questions, upsert_quiz,
    upsert_quiz_questions, upsert_unit,
)

SOURCE_CODE = 'JAVA101'
DEMO_CODE = 'DEMO101'
DEMO_TITLE = 'Java Fundamentals — Demo'
DEMO_INSTRUCTOR_EMAIL = 'instructor@demo.com'


def demo_key(source_key):
    """
    The demo course's key for a piece of source content (Phase 65).

    Derived, not random, so it is stable across re-clones — a demo lesson
    keeps its XP identity through a refresh — while staying distinct from the
    source lesson it was copied from. Copying the source key verbatim (which
    the old field-for-field clone did) would blow the unique index on the very
    first run.
    """
    return f'demo:{source_key}' if source_key else None


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

        counts = {'units': 0, 'lessons': 0, 'sections': 0,
                  'lesson questions': 0, 'quizzes': 0, 'quiz questions': 0}
        seen_lesson_keys = set()
        seen_quiz_keys = set()

        for unit in source.units.order_by('order'):
            new_unit = upsert_unit(demo, unit.order, unit.title)
            counts['units'] += 1

            for quiz in unit.quizzes.order_by('order', 'pk'):
                key = demo_key(quiz.content_key)
                seen_quiz_keys.add(key)
                new_quiz = upsert_quiz(
                    new_unit, key, quiz.order,
                    title=quiz.title,
                    description=quiz.description,
                    passing_score=quiz.passing_score,
                    points=quiz.points,
                    max_attempts=quiz.max_attempts,
                )
                counts['quizzes'] += 1
                questions = [
                    {
                        'text': question.text,
                        'choices': [
                            (choice.text, choice.is_correct)
                            for choice in question.choices.order_by('order', 'pk')
                        ],
                    }
                    for question in quiz.questions.order_by('order', 'pk')
                ]
                upsert_quiz_questions(new_quiz, questions)
                counts['quiz questions'] += len(questions)

            for lesson in unit.lessons.order_by('order'):
                key = demo_key(lesson.content_key)
                seen_lesson_keys.add(key)
                new_lesson = upsert_lesson(
                    new_unit, key, lesson.order,
                    title=lesson.title,
                    content=lesson.content,
                    video_type=lesson.video_type,
                    video_id=lesson.video_id,
                    requires_quiz=lesson.requires_quiz,
                )
                counts['lessons'] += 1
                counts['sections'] += self._sync_sections(lesson, new_lesson)
                questions = [
                    {
                        'text': question.text,
                        'choices': [
                            (choice.text, choice.is_correct)
                            for choice in question.choices.order_by('order', 'pk')
                        ],
                    }
                    for question in lesson.questions.order_by('order', 'pk')
                ]
                upsert_lesson_questions(new_lesson, questions)
                counts['lesson questions'] += len(questions)

        # DEMO101 mirrors JAVA101, so anything the source dropped must go —
        # unlike the seed commands, where pruning is opt-in.
        prune_stale(demo, seen_lesson_keys, seen_quiz_keys, dry_run=False)

        summary = ', '.join(f'{v} {k}' for k, v in counts.items())
        self.stdout.write(self.style.SUCCESS(
            f'{"Created" if created else "Refreshed"} {DEMO_CODE} '
            f'("{DEMO_TITLE}") from {SOURCE_CODE}: {summary}. '
            f'Enrollment code: {demo.enrollment_code}'
        ))

    def _sync_sections(self, source_lesson, new_lesson):
        """
        Upsert the demo lesson's sections from the source, blobs included.

        Sections are matched on ``(lesson, order)`` and updated in place, so
        the rows survive a refresh. Slide images cannot be shared: the
        FileField holds a *name*, so copying it would leave both courses
        pointing at one storage object — and the section DELETE view deletes
        the blob with the row, breaking whichever section survived. Each demo
        section therefore gets its own copy, and its old blob is deleted
        whenever it is replaced or removed.

        Returns the number of sections in the demo lesson.
        """
        sections = list(source_lesson.sections.order_by('order'))

        for i, section in enumerate(sections):
            new_section, _created = LessonSection.objects.update_or_create(
                lesson=new_lesson, order=i,
                defaults={
                    'title': section.title,
                    'content': section.content,
                    'video_type': section.video_type,
                    'video_id': section.video_id,
                    'layout': section.layout,
                    'image_alt': section.image_alt,
                },
            )
            self._sync_section_image(section, new_section)

        stale = LessonSection.objects.filter(
            lesson=new_lesson, order__gte=len(sections)
        )
        for section in stale.exclude(image=''):
            section.image.delete(save=False)
        stale.delete()

        return len(sections)

    def _sync_section_image(self, section, new_section):
        """Give ``new_section`` its own copy of ``section``'s slide image."""
        source_name = section.image.name if section.image else ''

        if new_section.image:
            # Always replaced rather than diffed: the storage backend gives no
            # cheap content comparison, and a stale demo slide is worse than a
            # re-upload. Deleting first is what keeps the old blob from leaking.
            new_section.image.delete(save=True)

        if not source_name:
            return

        with section.image.open('rb') as f:
            content = f.read()
        # save() re-runs upload_to and de-duplicates the basename, so the copy
        # gets its own object under a new name.
        new_section.image.save(
            os.path.basename(source_name), ContentFile(content), save=True
        )

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
