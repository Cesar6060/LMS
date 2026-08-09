"""
Sequencing sweep over every seeded course (Phase 70).

The player's Next/Previous walk is a chain derived from ``unit.order`` then
``lesson.order`` then ``quiz.order`` — the same flattening ``course_map`` does
(``courses/views.py``, "Flatten: for each unit (by order), lessons (by order)
then quizzes (by order)"). A gap or a duplicate in any of those ``order``
columns makes the chain skip content or visit it twice, and nothing else in the
suite would notice. This module pins the invariants for the real blueprints.

MAINTENANCE — READ BEFORE ADDING A COURSE
-----------------------------------------
``COURSES`` below is the list that actually buys coverage. Adding a new course
to ``COMMANDS`` in ``test_populate_courses.py`` does **not** cover it here, and
the reverse is also true: several classes in that module hardcode
``populate_robotics_course`` rather than reading ``COMMANDS`` (the phase-69
gotcha — ROB201 sat in ``COMMANDS`` while ``TestAdoption`` / ``TestPruneFlag`` /
``TestInstructorGuard`` never ran against it). A fifth course therefore needs
**both** lists updated: ``COURSES`` here and ``COMMANDS`` there.

Note on the ordering BASE: seeded content is 0-indexed while content created
through the API starts at 1 (``CourseUnitsView.perform_create`` vs
``_content_upsert``). These tests assert contiguity — no gaps, no duplicates —
never a particular starting value.

Runtime: each test re-runs the real blueprints in a fresh transaction, so a
course is seeded once per test rather than once per module (pytest-django's
``db`` fixture is function-scoped and rolling a module-scoped seed outside it
would leak rows into the rest of the session). Each seed is ~1s; the whole
module is a handful of seconds.
"""
from typing import NamedTuple

import pytest
from django.core.management import call_command

from accounts.models import User
from courses.models import Course, Lesson, Unit
from quizzes.models import Quiz

# (course code, management commands to run in order).
# DEMO101 is a clone of JAVA101, so it needs the source seeded first.
COURSES = [
    pytest.param('DEMO101', ['populate_java_course', 'clone_course_for_demo'],
                 id='DEMO101'),
    pytest.param('JAVA101', ['populate_java_course'], id='JAVA101'),
    pytest.param('ROB101', ['populate_robotics_course'], id='ROB101'),
    pytest.param('ROB201', ['populate_robotics_2_course'], id='ROB201'),
]


class ChainNode(NamedTuple):
    """One step of the player's Next/Previous walk.

    Lesson and quiz ids come from different tables and collide freely, so a
    node is identified by ``(kind, id)`` — never by ``id`` alone. This is the
    same reason ``course_map`` emits a composite ``current_node_id``.
    """
    kind: str          # 'lesson' | 'quiz'
    id: int
    title: str
    unit_order: int
    order: int


@pytest.fixture
def seed_instructor():
    """The instructor the populate commands look for by name."""
    return User.objects.create_user(
        email='cesar@test.com', password='pw', is_instructor=True,
        first_name='Cesar', last_name='Villarreal',
    )


@pytest.fixture
def seeded_course(seed_instructor, code, commands):
    """Build one course from its real blueprint and hand back the Course row.

    ``code`` and ``commands`` come from the class-level parametrize; pytest
    exposes parametrized argnames as fixtures, so a single fixture covers every
    entry in ``COURSES``.
    """
    for command in commands:
        call_command(command)
    return Course.objects.prefetch_related(
        'units__lessons', 'units__quizzes'
    ).get(code=code)


def build_chain(course, viewer_is_instructor=False):
    """The derived units -> lessons -> quizzes chain.

    Mirrors ``course_map``'s node order (``courses/views.py``): units in
    ``unit.order``, each unit's lessons in ``lesson.order``, then that unit's
    quizzes in ``quiz.order`` as boss nodes. Model ``Meta.ordering`` supplies
    every sort, exactly as it does for the view's prefetches. Locked units are
    skipped for non-instructors — the player's chain must not walk into
    content the instructor locked.
    """
    chain = []
    for unit in course.units.all():
        if unit.is_locked and not viewer_is_instructor:
            continue
        for lesson in unit.lessons.all():
            chain.append(ChainNode(
                'lesson', lesson.id, lesson.title, unit.order, lesson.order
            ))
        for quiz in unit.quizzes.all():
            chain.append(ChainNode(
                'quiz', quiz.id, quiz.title, unit.order, quiz.order
            ))
    return chain


def contiguity_failure(orders):
    """Return a message describing the gap/duplicate, or None if contiguous.

    Contiguous == the sorted values are a run of consecutive integers. The base
    is deliberately not asserted (0 for seeded content, 1 via the API).
    """
    if not orders:
        return None
    ordered = sorted(orders)
    expected = list(range(ordered[0], ordered[0] + len(ordered)))
    if ordered == expected:
        return None
    duplicates = sorted({o for o in ordered if ordered.count(o) > 1})
    gaps = sorted(set(expected) - set(ordered))
    return f'orders={ordered} duplicates={duplicates} gaps={gaps}'


@pytest.mark.django_db
@pytest.mark.parametrize('code, commands', COURSES)
class TestSeededCourseSequencing:

    def test_units_are_contiguously_ordered(self, seeded_course, code, commands):
        orders = list(
            Unit.objects.filter(course=seeded_course)
            .values_list('order', flat=True)
        )
        assert orders, f'{code} seeded no units'
        failure = contiguity_failure(orders)
        assert failure is None, f'{code} unit ordering is not contiguous: {failure}'

    def test_lessons_are_contiguously_ordered_within_each_unit(
        self, seeded_course, code, commands
    ):
        units = list(seeded_course.units.all())
        assert units, f'{code} seeded no units'
        problems = []
        for unit in units:
            orders = list(
                Lesson.objects.filter(unit=unit).values_list('order', flat=True)
            )
            failure = contiguity_failure(orders)
            if failure is not None:
                problems.append(
                    f'unit {unit.order} "{unit.title}": {failure}'
                )
        assert not problems, (
            f'{code} lesson ordering is not contiguous:\n  '
            + '\n  '.join(problems)
        )
        assert Lesson.objects.filter(unit__course=seeded_course).exists(), (
            f'{code} seeded no lessons'
        )

    def test_no_two_quizzes_share_an_order_within_a_unit(
        self, seeded_course, code, commands
    ):
        """``Quiz`` has no ``unique_together`` on ``(unit, order)``.

        ``Quiz.Meta.ordering = ['order', 'created_at']`` means a duplicate
        resolves by creation time, i.e. non-deterministically across a reseed —
        the chain would reorder itself under the student. This is the one
        ordering column the database does not already protect.
        """
        problems = []
        for unit in seeded_course.units.all():
            orders = list(
                Quiz.objects.filter(unit=unit).values_list('order', flat=True)
            )
            duplicates = sorted({o for o in orders if orders.count(o) > 1})
            if duplicates:
                problems.append(
                    f'unit {unit.order} "{unit.title}": orders={sorted(orders)} '
                    f'duplicated={duplicates}'
                )
        assert not problems, (
            f'{code} has quizzes sharing an order inside a unit:\n  '
            + '\n  '.join(problems)
        )

    def test_chain_contains_every_lesson_exactly_once(
        self, seeded_course, code, commands
    ):
        chain = build_chain(seeded_course)
        assert chain, f'{code} produced an empty navigation chain'

        # (kind, id) is the node identity: lesson 7 and quiz 7 are two nodes.
        keys = [(node.kind, node.id) for node in chain]
        assert len(keys) == len(set(keys)), (
            f'{code} chain visits a node twice: '
            f'{sorted(k for k in keys if keys.count(k) > 1)}'
        )

        expected_lesson_ids = list(
            Lesson.objects.filter(
                unit__course=seeded_course, unit__is_locked=False
            )
            .order_by('unit__order', 'order')
            .values_list('id', flat=True)
        )
        chain_lesson_ids = [node.id for node in chain if node.kind == 'lesson']

        assert chain_lesson_ids == expected_lesson_ids, (
            f'{code} chain does not visit every non-locked lesson exactly once '
            f'in (unit.order, lesson.order) order.\n'
            f'  missing: {sorted(set(expected_lesson_ids) - set(chain_lesson_ids))}\n'
            f'  extra:   {sorted(set(chain_lesson_ids) - set(expected_lesson_ids))}'
        )

        # The chain is monotonic in (unit.order, kind-rank, order): a unit's
        # lessons, then that unit's quizzes, then the next unit.
        positions = [
            (node.unit_order, 0 if node.kind == 'lesson' else 1, node.order)
            for node in chain
        ]
        assert positions == sorted(positions), (
            f'{code} chain is out of (unit.order, lesson.order) sequence: '
            f'{positions}'
        )

        # ...and the unit quizzes really are in the chain, otherwise "Next from
        # the last lesson of a unit goes to its quiz" is untested by this sweep.
        assert any(node.kind == 'quiz' for node in chain), (
            f'{code} chain holds no quiz nodes'
        )
