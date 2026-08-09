"""
Tests for the read-only ``audit_content_ordering`` command (Phase 70).

The command is a report, not a gate, so the things worth pinning are: it finds
each class of ordering problem, it stays quiet on clean content, it never
writes, and it never raises on a finding.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import User
from courses.management.commands.audit_content_ordering import order_problems
from courses.models import Course, Lesson, Unit
from quizzes.models import Quiz


@pytest.fixture
def instructor():
    return User.objects.create_user(
        email='audit-instructor@test.com',
        password='testpass123',
        first_name='Audit',
        last_name='Instructor',
        is_instructor=True,
    )


def make_course(instructor, code, unit_orders=(0, 1), lessons_per_unit=2, base=0):
    course = Course.objects.create(
        code=code,
        title=f'{code} Course',
        instructor=instructor,
    )
    for unit_order in unit_orders:
        unit = Unit.objects.create(course=course, title=f'Unit {unit_order}', order=unit_order)
        for i in range(lessons_per_unit):
            Lesson.objects.create(
                unit=unit,
                title=f'Lesson {i}',
                order=base + i,
                content_key=f'{code.lower()}-u{unit_order}-l{i}',
            )
    return course


def run_audit(**options):
    out = StringIO()
    call_command('audit_content_ordering', stdout=out, **options)
    return out.getvalue()


def snapshot(course):
    """Every ordering-relevant row of a course, for the read-only assertion."""
    return {
        'units': sorted(Unit.objects.filter(course=course).values_list('pk', 'order', 'title')),
        'lessons': sorted(
            Lesson.objects.filter(unit__course=course).values_list('pk', 'order', 'title')
        ),
        'quizzes': sorted(
            Quiz.objects.filter(unit__course=course).values_list('pk', 'order', 'title')
        ),
    }


class TestOrderProblems:
    """The pure helper, independent of the database."""

    def test_zero_indexed_run_is_clean(self):
        assert order_problems([0, 1, 2, 3]) == ([], [])

    def test_one_indexed_run_is_clean_too(self):
        """Seeded content is 0-indexed, API-created content starts at 1. The
        base is not a finding — contiguity is measured from the minimum."""
        assert order_problems([1, 2, 3]) == ([], [])

    def test_gap_is_reported(self):
        assert order_problems([0, 1, 3, 4]) == ([], [2])

    def test_duplicate_is_reported(self):
        assert order_problems([0, 1, 1, 2]) == ([1], [])

    def test_empty_is_clean(self):
        assert order_problems([]) == ([], [])


@pytest.mark.django_db
class TestAuditContentOrdering:
    def test_clean_course_reports_no_issues(self, instructor):
        make_course(instructor, 'CLEAN1')
        output = run_audit()
        assert 'CLEAN1' in output
        assert 'ISSUE' not in output
        assert 'no issues found' in output

    def test_one_indexed_course_is_clean(self, instructor):
        """API-created content starts at 1; that base must not be a finding."""
        make_course(instructor, 'ONEIDX', unit_orders=(1, 2), base=1)
        output = run_audit()
        assert 'ISSUE' not in output

    def test_gap_in_unit_orders_is_reported(self, instructor):
        make_course(instructor, 'UNITGAP', unit_orders=(0, 1, 3))
        output = run_audit(course='UNITGAP')
        assert 'ISSUE' in output
        assert 'units run 0..3 with missing order(s) [2]' in output

    def test_gap_in_lesson_orders_is_reported(self, instructor):
        course = make_course(instructor, 'LESSGAP', unit_orders=(0,), lessons_per_unit=0)
        unit = course.units.first()
        for order in (0, 1, 4):
            Lesson.objects.create(
                unit=unit, title=f'L{order}', order=order,
                content_key=f'lessgap-{order}',
            )
        output = run_audit(course='LESSGAP')
        assert 'Unit 0 "Unit 0": 3 lessons run 0..4 with missing order(s) [2, 3]' in output

    def test_duplicate_quiz_order_within_a_unit_is_an_issue(self, instructor):
        """Quiz has no unique_together on (unit, order), so unlike units and
        lessons this duplicate is reachable — and the tie-break is by
        created_at, i.e. non-deterministic across a reseed."""
        course = make_course(instructor, 'QUIZDUP', unit_orders=(0,))
        unit = course.units.first()
        Quiz.objects.create(unit=unit, title='Quiz A', order=0, content_key='quizdup-a')
        Quiz.objects.create(unit=unit, title='Quiz B', order=0, content_key='quizdup-b')

        output = run_audit(course='QUIZDUP')
        assert 'ISSUE' in output
        assert '2 quizzes share order 0' in output
        assert '"Quiz A"' in output and '"Quiz B"' in output
        assert 'non-deterministic' in output
        assert 'created_at' in output

    def test_two_quizzes_in_a_unit_is_informational_not_an_issue(self, instructor):
        course = make_course(instructor, 'TWOQUIZ', unit_orders=(0,))
        unit = course.units.first()
        Quiz.objects.create(unit=unit, title='Quiz A', order=0, content_key='twoquiz-a')
        Quiz.objects.create(unit=unit, title='Quiz B', order=1, content_key='twoquiz-b')

        output = run_audit(course='TWOQUIZ')
        assert 'ISSUE' not in output
        assert 'no issues found' in output
        assert 'holds 2 quizzes (orders 0, 1)' in output

    def test_single_quiz_per_unit_is_silent(self, instructor):
        course = make_course(instructor, 'ONEQUIZ', unit_orders=(0,))
        Quiz.objects.create(
            unit=course.units.first(), title='Quiz A', order=0, content_key='onequiz-a',
        )
        output = run_audit(course='ONEQUIZ')
        assert 'ISSUE' not in output
        assert 'holds' not in output

    def test_course_filter_limits_the_report(self, instructor):
        make_course(instructor, 'KEEPME')
        make_course(instructor, 'SKIPME', unit_orders=(0, 2))
        output = run_audit(course='KEEPME')
        assert 'KEEPME' in output
        assert 'SKIPME' not in output
        assert 'Auditing 1 course(s)' in output

    def test_course_filter_is_case_insensitive(self, instructor):
        make_course(instructor, 'CASEOK')
        assert 'CASEOK' in run_audit(course='caseok')

    def test_unknown_course_is_a_clean_error(self, instructor):
        make_course(instructor, 'REAL01')
        with pytest.raises(CommandError) as exc:
            run_audit(course='NOPE99')
        assert 'No course with code "NOPE99"' in str(exc.value)
        assert 'REAL01' in str(exc.value)

    def test_findings_do_not_raise_or_exit(self, instructor):
        """Exit 0 always: a finding is a report, never a build failure."""
        make_course(instructor, 'BADORD', unit_orders=(0, 5))
        output = run_audit()  # would raise SystemExit if the command gated
        assert 'ISSUE' in output

    def test_audit_writes_nothing(self, instructor):
        course = make_course(instructor, 'NOWRITE', unit_orders=(0, 3))
        unit = course.units.first()
        Quiz.objects.create(unit=unit, title='Quiz A', order=0, content_key='nowrite-a')
        Quiz.objects.create(unit=unit, title='Quiz B', order=0, content_key='nowrite-b')

        before = snapshot(course)
        run_audit()
        assert snapshot(course) == before

    def test_course_with_no_units(self, instructor):
        Course.objects.create(code='EMPTY1', title='Empty', instructor=instructor)
        output = run_audit(course='EMPTY1')
        assert 'Course has no units.' in output
        assert 'ISSUE' not in output

    def test_no_courses_at_all(self):
        output = run_audit()
        assert 'Auditing 0 course(s)' in output
        assert 'no issues found' in output
