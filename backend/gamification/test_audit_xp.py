"""
Tests for the ``audit_xp`` management command (Phase 65).

The command exists to measure damage that Phase 65 deliberately did not
repair, so the property that matters most is the one asserted last: it never
writes anything.
"""
import pytest
from django.core.management import call_command

from accounts.models import User
from courses.models import Course, Lesson, Unit
from gamification.models import GameProfile, XPEvent
from gamification.services import (
    award_lesson_completion, award_quiz_pass, XP_LESSON,
)
from quizzes.models import Quiz


@pytest.fixture
def instructor():
    return User.objects.create_user(
        email='audit-instructor@test.com', password='pw', is_instructor=True
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        email='audit-student@test.com', password='pw', is_instructor=False
    )


@pytest.fixture
def unit(instructor):
    course = Course.objects.create(
        code='AUD101', title='Audit Course', instructor=instructor
    )
    return Unit.objects.create(course=course, title='Unit 1', order=0)


@pytest.fixture
def lesson(unit):
    return Lesson.objects.create(
        unit=unit, title='Lesson 1', order=0, content_key='aud101-lesson-1'
    )


def run(*args, **kwargs):
    """Run the command and return its stdout."""
    from io import StringIO
    out = StringIO()
    call_command('audit_xp', *args, stdout=out, **kwargs)
    return out.getvalue()


@pytest.mark.django_db
class TestAuditXPCleanDatabase:
    def test_reports_zero_of_everything(self, student, lesson):
        award_lesson_completion(student, lesson)

        output = run()

        assert 'ORPHANED XP EVENTS' in output
        assert 'LEDGER DRIFT' in output
        assert 'AMOUNT DRIFT' in output
        assert 'CONTENT KEYS' in output
        assert output.count('None') >= 2
        assert 'every profile matches its ledger' in output

    def test_empty_database_does_not_error(self):
        output = run()
        assert 'Nothing was modified.' in output


@pytest.mark.django_db
class TestOrphanReport:
    def test_counts_an_event_whose_lesson_was_deleted(self, student, lesson):
        award_lesson_completion(student, lesson)
        lesson.delete()

        output = run()

        assert 'audit-student@test.com' in output
        assert 'TOTAL' in output

    def test_orphan_is_detected_without_relying_on_the_prefix(
        self, student, lesson
    ):
        """
        Existence is decided by looking the source up, so content deleted
        AFTER the backfill is still caught even though its key is a normal
        blueprint slug rather than ``orphan:``.
        """
        award_lesson_completion(student, lesson)
        event = XPEvent.objects.get(user=student)
        assert event.source_key == 'aud101-lesson-1'
        lesson.delete()

        output = run('--verbose')

        assert "key='aud101-lesson-1'" in output

    def test_live_content_is_not_reported_as_orphaned(self, student, lesson):
        award_lesson_completion(student, lesson)

        output = run()

        orphan_section = output.split('ORPHANED')[1].split('LEDGER DRIFT')[0]
        assert 'None.' in orphan_section

    def test_quiz_orphans_resolve_against_quizzes_not_lessons(
        self, student, unit
    ):
        quiz = Quiz.objects.create(
            unit=unit, title='Q', order=0, content_key='aud101-quiz-1'
        )
        award_quiz_pass(student, quiz)
        quiz.delete()

        output = run('--verbose')

        assert "key='aud101-quiz-1'" in output


@pytest.mark.django_db
class TestLedgerDrift:
    def test_hand_edited_total_xp_shows_as_drift(self, student, lesson):
        award_lesson_completion(student, lesson)
        GameProfile.objects.filter(user=student).update(total_xp=10_000)

        output = run()

        assert 'audit-student@test.com' in output
        assert '+9950' in output

    def test_matching_profile_is_not_reported(self, student, lesson):
        award_lesson_completion(student, lesson)

        output = run()

        assert 'every profile matches its ledger' in output


@pytest.mark.django_db
class TestAmountDrift:
    def test_stale_amount_is_reported(self, student, lesson):
        award_lesson_completion(student, lesson)
        XPEvent.objects.filter(user=student).update(amount=XP_LESSON + 5)

        output = run()

        amount_section = output.split('AMOUNT DRIFT')[1].split('CONTENT KEYS')[0]
        assert f'expected {XP_LESSON:>4} XP' in amount_section
        assert '1 row(s) differ' in amount_section
        assert f'holding {XP_LESSON + 5} XP' in amount_section

    def test_current_amount_is_not_reported(self, student, lesson):
        award_lesson_completion(student, lesson)

        output = run()

        amount_section = output.split('AMOUNT DRIFT')[1].split('CONTENT KEYS')[0]
        assert 'None.' in amount_section


@pytest.mark.django_db
class TestContentKeyReport:
    def test_reports_unadopted_auto_keys_in_a_seeded_course(self, instructor):
        course = Course.objects.create(
            code='ROB101', title='Robotics 1', instructor=instructor
        )
        unit = Unit.objects.create(course=course, title='U', order=0)
        Lesson.objects.create(unit=unit, title='Unadopted', order=0)

        output = run()

        assert 'ROB101: 1 row(s) still unadopted' in output

    def test_reports_a_key_held_by_both_a_lesson_and_a_quiz(self, unit):
        Lesson.objects.create(unit=unit, title='L', order=0, content_key='shared-key')
        Quiz.objects.create(unit=unit, title='Q', order=0, content_key='shared-key')

        output = run()

        assert "'shared-key' is held by both a lesson and a quiz" in output

    def test_fully_adopted_seeded_course_is_clean(self, instructor):
        course = Course.objects.create(
            code='JAVA101', title='Java', instructor=instructor
        )
        unit = Unit.objects.create(course=course, title='U', order=0)
        Lesson.objects.create(
            unit=unit, title='L', order=0, content_key='java101-hello'
        )

        output = run()

        assert 'JAVA101: all content carries a blueprint key.' in output


@pytest.mark.django_db
class TestScopingAndReadOnly:
    def test_user_flag_scopes_to_one_student(self, student, lesson, unit):
        other = User.objects.create_user(
            email='other@test.com', password='pw', is_instructor=False
        )
        other_lesson = Lesson.objects.create(
            unit=unit, title='L2', order=1, content_key='aud101-lesson-2'
        )
        award_lesson_completion(student, lesson)
        award_lesson_completion(other, other_lesson)
        GameProfile.objects.filter(user=other).update(total_xp=999)

        output = run('--user', 'audit-student@test.com')

        assert 'Scoped to audit-student@test.com' in output
        assert 'other@test.com' not in output

    def test_unknown_email_warns_and_still_exits_cleanly(self, student, lesson):
        award_lesson_completion(student, lesson)

        output = run('--user', 'nobody@test.com')

        assert 'No user with email nobody@test.com' in output
        assert 'Nothing was modified.' in output

    def test_command_writes_nothing(self, student, lesson, unit):
        """The property that makes this safe to point at production."""
        quiz = Quiz.objects.create(
            unit=unit, title='Q', order=0, content_key='aud101-quiz-1'
        )
        award_lesson_completion(student, lesson)
        award_quiz_pass(student, quiz)
        # Give it something to actually report on.
        orphan = Lesson.objects.create(
            unit=unit, title='Doomed', order=5, content_key='aud101-doomed'
        )
        award_lesson_completion(student, orphan)
        orphan.delete()
        GameProfile.objects.filter(user=student).update(total_xp=12_345)

        before = {
            'events': XPEvent.objects.count(),
            'lessons': Lesson.objects.count(),
            'quizzes': Quiz.objects.count(),
            'profiles': GameProfile.objects.count(),
            'total_xp': GameProfile.objects.get(user=student).total_xp,
            'keys': sorted(
                Lesson.objects.values_list('content_key', flat=True)
            ),
            'source_keys': sorted(
                XPEvent.objects.values_list('source_key', flat=True)
            ),
        }

        run()
        run('--verbose')
        run('--user', 'audit-student@test.com')

        after = {
            'events': XPEvent.objects.count(),
            'lessons': Lesson.objects.count(),
            'quizzes': Quiz.objects.count(),
            'profiles': GameProfile.objects.count(),
            'total_xp': GameProfile.objects.get(user=student).total_xp,
            'keys': sorted(
                Lesson.objects.values_list('content_key', flat=True)
            ),
            'source_keys': sorted(
                XPEvent.objects.values_list('source_key', flat=True)
            ),
        }
        assert after == before


@pytest.mark.django_db
class TestStrandedReport:
    """
    The canary for the adoption seam: a row pointing at LIVE content under a
    stale or missing key. `_award_xp` heals these on the next award, so this
    report is the way to see whether adoption has been exercised yet.
    """

    def test_stale_key_on_live_content_is_reported(self, student, lesson):
        award_lesson_completion(student, lesson)
        # Adoption re-keys the lesson; the ledger row is left behind.
        Lesson.objects.filter(pk=lesson.pk).update(content_key='aud101-adopted')

        output = run()

        stranded = output.split('STRANDED ROWS')[1].split('LEDGER DRIFT')[0]
        assert 'audit-student@test.com' in stranded
        assert 'TOTAL' in stranded

    def test_null_key_on_live_content_is_reported(self, student, lesson):
        XPEvent.objects.create(
            user=student, source_type=XPEvent.SOURCE_LESSON,
            source_id=lesson.id, source_key=None, amount=50,
        )

        output = run('--verbose')

        assert f'key=None -> live id={lesson.id}' in output

    def test_healthy_rows_are_not_reported(self, student, lesson):
        award_lesson_completion(student, lesson)

        output = run()

        stranded = output.split('STRANDED ROWS')[1].split('LEDGER DRIFT')[0]
        assert 'every row resolves by key' in stranded

    def test_an_orphan_is_not_counted_as_stranded(self, student, lesson):
        """Orphans have no live source; the two reports must not overlap."""
        award_lesson_completion(student, lesson)
        lesson.delete()

        output = run()

        stranded = output.split('STRANDED ROWS')[1].split('LEDGER DRIFT')[0]
        assert 'every row resolves by key' in stranded

    def test_the_report_falls_to_zero_once_the_award_heals_it(
        self, student, lesson
    ):
        award_lesson_completion(student, lesson)
        Lesson.objects.filter(pk=lesson.pk).update(content_key='aud101-adopted')
        assert 'TOTAL' in run().split('STRANDED ROWS')[1].split('LEDGER DRIFT')[0]

        lesson.refresh_from_db()
        award_lesson_completion(student, lesson)   # heals

        stranded = run().split('STRANDED ROWS')[1].split('LEDGER DRIFT')[0]
        assert 'every row resolves by key' in stranded
        assert GameProfile.objects.get(user=student).total_xp == 50
