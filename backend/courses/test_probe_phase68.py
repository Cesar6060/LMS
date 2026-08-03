"""Throwaway adversarial probe for phase 68 enroll/invite fixes. DELETE before finishing."""
import pytest
from django.db import connection
from django.utils import timezone
from django.db import IntegrityError
from rest_framework import status
from accounts.models import User
from courses.models import Course, CourseInvite, Enrollment
import courses.views as courses_views
import courses.serializers as courses_serializers

from courses.tests import (  # reuse fixtures/helpers
    api_client, student, instructor, course, enrollment, second_student,
    other_instructor, ENROLL_PATHS, enroll_via, student_invite,
)


@pytest.mark.django_db
class TestProbeIntegrityErrorMasking:
    """Does `except IntegrityError` swallow a non-uniqueness IntegrityError
    and misreport it as 'already enrolled'?"""

    @pytest.mark.parametrize('path', ENROLL_PATHS)
    def test_unrelated_integrity_error_is_misreported_as_already_enrolled(
            self, api_client, student, course, student_invite, monkeypatch, path):
        """Force consume_invite_for to raise an IntegrityError that has
        NOTHING to do with the (user, course) unique constraint - e.g. a
        simulated FK/db-level failure - and see whether the handler still
        claims 'already enrolled'."""

        def boom(user, course_arg):
            raise IntegrityError("simulated: some_other_table_fk_violation")

        monkeypatch.setattr(courses_views, 'consume_invite_for', boom)
        monkeypatch.setattr(courses_serializers, 'consume_invite_for', boom)

        api_client.force_authenticate(user=student)
        response = enroll_via(api_client, path, course)

        print(f"\n[{path}] status={response.status_code} body={response.data}")
        # We're not asserting pass/fail here - just observing behavior.
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'already enrolled' in str(response.data).lower()
        # And crucially: is the enrollment actually rolled back?
        assert not Enrollment.objects.filter(user=student, course=course).exists()


@pytest.mark.django_db
class TestProbeConnectionState:
    """After the IntegrityError / PermissionDenied paths, is the DB
    connection left usable for a subsequent query in the SAME test
    (proxy for same request-response cycle / connection reuse)?"""

    @pytest.mark.parametrize('path', ENROLL_PATHS)
    def test_connection_usable_after_permission_denied_rollback(
            self, api_client, student, course, path):
        api_client.force_authenticate(user=student)
        response = enroll_via(api_client, path, course)
        assert response.status_code == 403

        # Immediately issue more queries - if the connection were left in
        # "current transaction is aborted" state, these would 500/raise.
        assert connection.in_atomic_block is False or True  # just touch it
        second_response = api_client.get('/api/courses/courses/')
        assert second_response.status_code == 200

    @pytest.mark.parametrize('path', ENROLL_PATHS)
    def test_connection_usable_after_integrity_error_rollback(
            self, api_client, student, course, student_invite, monkeypatch, path):
        import courses.views as courses_views
        import courses.serializers as courses_serializers
        real = courses_views.require_pending_invite

        def check_then_race(user, course_arg, *a, **kw):
            real(user, course_arg, *a, **kw)
            Enrollment.objects.get_or_create(user=user, course=course_arg)

        monkeypatch.setattr(courses_views, 'require_pending_invite', check_then_race)
        monkeypatch.setattr(courses_serializers, 'require_pending_invite', check_then_race)

        api_client.force_authenticate(user=student)
        response = enroll_via(api_client, path, course)
        assert response.status_code == 400

        second_response = api_client.get('/api/courses/courses/')
        assert second_response.status_code == 200


@pytest.mark.django_db
class TestProbeMultipleInvitesForSameEmail:
    """Several revoked rows + one live pending row can coexist for the same
    (course, email) per the unique constraint's condition. Does
    consume_invite_for correctly only ever touch the single live one, never
    accidentally reviving/claiming a revoked row, and never raising when
    multiple rows match the base filter (before the pending() narrowing)?"""

    def test_many_revoked_rows_plus_one_pending_all_coexist(
            self, api_client, student, course, instructor):
        # Simulate 5 revoke/re-invite cycles leaving 5 dead rows plus one live one.
        for _ in range(5):
            CourseInvite.objects.create(
                course=course, email=student.email, invited_by=instructor,
                revoked_at=timezone.now())
        live = CourseInvite.objects.create(
            course=course, email=student.email, invited_by=instructor)

        assert CourseInvite.objects.filter(
            course=course, email=student.email).count() == 6

        claimed = courses_views.consume_invite_for(student, course)
        assert claimed is True

        live.refresh_from_db()
        assert live.accepted_at is not None

        # None of the revoked rows should have been touched.
        revoked_rows = CourseInvite.objects.filter(
            course=course, email=student.email, revoked_at__isnull=False)
        assert revoked_rows.count() == 5
        assert all(r.accepted_at is None for r in revoked_rows)

    def test_consume_invite_for_never_claims_a_revoked_row(
            self, api_client, student, course, instructor):
        """No pending invite exists, only a revoked one. consume_invite_for
        must return False, not resurrect the revoked row."""
        revoked = CourseInvite.objects.create(
            course=course, email=student.email, invited_by=instructor,
            revoked_at=timezone.now())

        claimed = courses_views.consume_invite_for(student, course)
        assert claimed is False

        revoked.refresh_from_db()
        assert revoked.accepted_at is None


@pytest.mark.django_db
class TestProbeCrossUserInviteClaim:
    """Can consume_invite_for(userA, course) ever claim an invite whose email
    belongs to userB?"""

    def test_second_students_pending_invite_is_untouched_by_first_students_call(
            self, api_client, student, second_student, course, instructor):
        mine = CourseInvite.objects.create(
            course=course, email=student.email, invited_by=instructor)
        theirs = CourseInvite.objects.create(
            course=course, email=second_student.email, invited_by=instructor)

        claimed = courses_views.consume_invite_for(student, course)
        assert claimed is True

        mine.refresh_from_db()
        theirs.refresh_from_db()
        assert mine.accepted_at is not None
        assert theirs.accepted_at is None  # someone else's invite untouched

    def test_case_permutation_of_own_email_does_not_let_a_different_user_claim(
            self, api_client, student, second_student, course, instructor):
        """Confirms consume_invite_for uses exact (not case-insensitive at the
        Python level either) matching consistent with require_pending_invite's
        contract - two different users can't collide."""
        CourseInvite.objects.create(
            course=course, email=student.email.upper(), invited_by=instructor)

        # second_student's own address never matches student's uppercased one
        claimed = courses_views.consume_invite_for(second_student, course)
        assert claimed is False


@pytest.mark.django_db
class TestProbeDoubleCallIdempotency:
    def test_calling_consume_invite_for_twice_only_claims_once(
            self, api_client, student, course, instructor):
        CourseInvite.objects.create(
            course=course, email=student.email, invited_by=instructor)

        first = courses_views.consume_invite_for(student, course)
        second = courses_views.consume_invite_for(student, course)

        assert first is True
        assert second is False  # already accepted, no longer "pending"
