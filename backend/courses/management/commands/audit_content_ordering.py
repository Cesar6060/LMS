"""
Read-only audit of unit / lesson / quiz ``order`` values (Phase 70).

The lesson chain the player walks (units -> lessons -> unit quiz -> next unit)
is derived entirely from ``order``. Nothing enforces that those values are
sensible, so this command reports the ways they can go wrong:

* units whose orders are not contiguous, and lessons the same way within each
  unit. Seeded content is 0-indexed and API-created content starts at 1
  (``CourseUnitsView.perform_create`` saves ``max_order + 1``, while
  ``_content_upsert`` numbers from the blueprint's own 0-based index), so the
  BASE is not a finding — only gaps and duplicates are.
* quizzes sharing an ``order`` inside a unit. ``Quiz`` has no
  ``unique_together`` on ``(unit, order)`` — unlike ``Unit`` and ``Lesson``,
  which the database keeps unique — so this is the one place a genuine
  duplicate can exist.
* units holding more than one quiz. Informational, not an error.

This is a REPORT, not a gate: it never writes, has no ``--fix``, and exits 0
however many findings it prints. (An unknown ``--course`` is a usage error and
still exits non-zero, as any Django command does.)

Usage:
    python manage.py audit_content_ordering
    python manage.py audit_content_ordering --course ROB101
"""

from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from courses.models import Course

# Findings are one of these two levels. Only ISSUE counts toward "problems";
# INFO is context the reader may still want (see the multi-quiz note below).
ISSUE = 'ISSUE'
INFO = 'INFO'


# A run of N items can hide at most N-1 interesting holes; past that the reader
# learns nothing from more. The cap also stops the audit materialising a
# billion-element list: `Unit.order` is a PositiveIntegerField and
# `UnitViewSet.partial_update` writes it through unclamped, so a single unit at
# order 1_500_000_000 is a reachable value, not a hypothetical.
MAX_REPORTED_GAPS = 20


def order_problems(orders):
    """
    Return ``(duplicates, gaps, gap_count)`` for a sequence of ``order`` values.

    Contiguity is measured from the sequence's own minimum, so a 0-indexed
    seeded course and a 1-indexed API-created one are both clean. Only the
    holes between the lowest and highest value are reported, and only the first
    ``MAX_REPORTED_GAPS`` of them — ``gap_count`` is the true total.
    """
    counts = Counter(orders)
    if not counts:
        return [], [], 0

    duplicates = sorted(value for value, n in counts.items() if n > 1)
    low, high = min(counts), max(counts)
    # span counts the slots between low and high; distinct values fill some.
    gap_count = (high - low + 1) - len(counts)
    if gap_count <= 0:
        return duplicates, [], 0

    gaps = []
    for value in range(low, high):
        if value not in counts:
            gaps.append(value)
            if len(gaps) == MAX_REPORTED_GAPS:
                break
    return duplicates, gaps, gap_count


def describe(items):
    """Render objects as ``"Title" (id=N)`` for a finding message."""
    return ', '.join(f'"{item.title}" (id={item.pk})' for item in items)


class Command(BaseCommand):
    help = (
        'Report gaps and duplicates in unit/lesson/quiz order values. '
        'Read-only: it never writes and always exits 0, so any finding is '
        'something to schedule, not a build failure.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--course',
            metavar='CODE',
            default=None,
            help='Audit only this course code (e.g. ROB101). Default: every course.',
        )

    def handle(self, *args, **options):
        courses = self._select_courses(options['course'])

        self.stdout.write(f'Auditing {len(courses)} course(s) for content-ordering problems...')

        issues = 0
        notes = 0
        for course in courses:
            findings = self.audit_course(course)
            issues += sum(1 for level, _ in findings if level == ISSUE)
            notes += sum(1 for level, _ in findings if level == INFO)
            self._write_course_report(course, findings)

        self.stdout.write('')
        self._write_summary(len(courses), issues, notes)

    # ------------------------------------------------------------------ audit

    def audit_course(self, course):
        """Return a list of ``(level, message)`` findings for one course."""
        findings = []
        units = list(
            course.units.all()
            .order_by('order', 'pk')
            .prefetch_related('lessons', 'quizzes')
        )

        if not units:
            findings.append((INFO, 'Course has no units.'))
            return findings

        findings.extend(self._audit_orders(
            label='units',
            items=units,
            noun='unit',
        ))

        for unit in units:
            prefix = f'Unit {unit.order} "{unit.title}"'
            lessons = list(unit.lessons.all())
            if lessons:
                findings.extend(self._audit_orders(
                    label='lessons',
                    items=lessons,
                    noun='lesson',
                    prefix=prefix,
                ))
            findings.extend(self._audit_unit_quizzes(unit, prefix))

        return findings

    def _audit_orders(self, label, items, noun, prefix=None):
        """Gap/duplicate findings for a sibling set of units or lessons."""
        head = f'{prefix}: ' if prefix else ''
        orders = [item.order for item in items]
        duplicates, gaps, gap_count = order_problems(orders)
        findings = []

        for value in duplicates:
            shared = [item for item in items if item.order == value]
            findings.append((ISSUE, (
                f'{head}{len(shared)} {label} share order {value}: {describe(shared)}.'
            )))

        if gaps:
            shown = f'{gaps}'
            if gap_count > len(gaps):
                shown = f'{gaps} and {gap_count - len(gaps)} more'
            findings.append((ISSUE, (
                f'{head}{len(items)} {label} run {min(orders)}..{max(orders)} '
                f'with {gap_count} missing order(s): {shown}. The chain reads '
                f'siblings in `order`, so a gap is only cosmetic today — but it '
                f'means the {noun} numbering no longer matches position.'
            )))

        return findings

    def _audit_unit_quizzes(self, unit, prefix):
        """Duplicate-order and multi-quiz findings for one unit's quizzes."""
        quizzes = sorted(unit.quizzes.all(), key=lambda q: (q.order, q.pk))
        if not quizzes:
            return []

        findings = []
        duplicates, _, _ = order_problems([quiz.order for quiz in quizzes])
        for value in duplicates:
            shared = [quiz for quiz in quizzes if quiz.order == value]
            findings.append((ISSUE, (
                f'{prefix}: {len(shared)} quizzes share order {value}: '
                f'{describe(shared)}. Quiz has no unique_together on '
                f'(unit, order), so this duplicate is real, and '
                f"Quiz.Meta.ordering = ['order', 'created_at'] resolves the tie "
                f'by creation time — which quiz comes first is therefore '
                f'non-deterministic across a reseed.'
            )))

        if len(quizzes) > 1:
            orders = ', '.join(str(quiz.order) for quiz in quizzes)
            findings.append((INFO, (
                f'{prefix}: holds {len(quizzes)} quizzes (orders {orders}). Not '
                f'an error — they chain in `order` — but the lesson chain\'s '
                f'"Next -> unit quiz" step assumes at most one quiz per unit.'
            )))

        return findings

    # ----------------------------------------------------------------- output

    def _write_course_report(self, course, findings):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(f'{course.code} — {course.title}'))

        if not findings:
            self.stdout.write(self.style.SUCCESS(f'  OK   {self._counts(course)}'))
            return

        for level, message in findings:
            if level == ISSUE:
                self.stdout.write(self.style.WARNING(f'  ISSUE  {message}'))
            else:
                self.stdout.write(f'  INFO   {message}')

    def _counts(self, course):
        units = course.units.all()
        lessons = sum(unit.lessons.count() for unit in units)
        quizzes = sum(unit.quizzes.count() for unit in units)
        return f'{len(units)} unit(s), {lessons} lesson(s), {quizzes} quiz(zes)'

    def _write_summary(self, course_count, issues, notes):
        if issues:
            self.stdout.write(self.style.WARNING(
                f'Summary: {issues} issue(s) and {notes} informational note(s) '
                f'across {course_count} course(s). Report only — nothing was changed.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Summary: no issues found across {course_count} course(s) '
                f'({notes} informational note(s)).'
            ))

    # ------------------------------------------------------------- selection

    def _select_courses(self, code):
        if code:
            course = Course.objects.filter(code__iexact=code).first()
            if course is None:
                known = ', '.join(
                    Course.objects.order_by('code').values_list('code', flat=True)
                ) or '(none)'
                raise CommandError(
                    f'No course with code "{code}". Known codes: {known}'
                )
            return [course]
        return list(Course.objects.order_by('code'))
