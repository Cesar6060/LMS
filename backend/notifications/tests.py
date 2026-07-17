import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from courses.models import Course, Enrollment
from assignments.models import Assignment, Submission, Grade
from notifications.models import Notification


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def instructor():
    return User.objects.create_user(
        email='instructor@test.com',
        password='testpass123',
        first_name='Test',
        last_name='Instructor',
        is_instructor=True
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        email='student@test.com',
        password='testpass123',
        first_name='Test',
        last_name='Student',
        is_instructor=False
    )


@pytest.fixture
def course(instructor):
    return Course.objects.create(
        code='TEST101',
        title='Test Course',
        description='A test course',
        instructor=instructor
    )


@pytest.mark.django_db
class TestNotificationModel:
    def test_create_notification(self, student):
        notification = Notification.objects.create(
            recipient=student,
            type='grade',
            title='Test Notification',
            message='This is a test'
        )
        assert notification.id is not None
        assert notification.is_read is False


@pytest.mark.django_db
class TestNotificationEndpoints:
    def test_list_notifications(self, api_client, student):
        Notification.objects.create(
            recipient=student,
            type='grade',
            title='Test 1',
            message='Message 1'
        )
        Notification.objects.create(
            recipient=student,
            type='grade',
            title='Test 2',
            message='Message 2'
        )

        api_client.force_authenticate(user=student)
        response = api_client.get('/api/notifications/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_list_notifications_only_own(self, api_client, student, instructor):
        Notification.objects.create(
            recipient=student,
            type='grade',
            title='For Student',
            message='Message'
        )
        Notification.objects.create(
            recipient=instructor,
            type='enrollment',
            title='For Instructor',
            message='Message'
        )

        api_client.force_authenticate(user=student)
        response = api_client.get('/api/notifications/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['title'] == 'For Student'

    def test_mark_as_read(self, api_client, student):
        notification = Notification.objects.create(
            recipient=student,
            type='grade',
            title='Test',
            message='Message'
        )

        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/notifications/{notification.id}/read/')

        assert response.status_code == status.HTTP_200_OK
        notification.refresh_from_db()
        assert notification.is_read is True

    def test_mark_all_as_read(self, api_client, student):
        Notification.objects.create(recipient=student, type='grade', title='1', message='m')
        Notification.objects.create(recipient=student, type='grade', title='2', message='m')

        api_client.force_authenticate(user=student)
        response = api_client.post('/api/notifications/mark-all-read/')

        assert response.status_code == status.HTTP_200_OK
        assert Notification.objects.filter(recipient=student, is_read=False).count() == 0

    def test_unread_count(self, api_client, student):
        Notification.objects.create(recipient=student, type='grade', title='1', message='m')
        Notification.objects.create(recipient=student, type='grade', title='2', message='m')
        Notification.objects.create(recipient=student, type='grade', title='3', message='m', is_read=True)

        api_client.force_authenticate(user=student)
        response = api_client.get('/api/notifications/unread-count/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2


@pytest.mark.django_db
class TestNotificationSignals:
    def test_enrollment_creates_notification(self, instructor, student, course):
        # Enrolling should create a notification for the instructor
        Enrollment.objects.create(user=student, course=course)

        notifications = Notification.objects.filter(
            recipient=instructor,
            type='enrollment'
        )
        assert notifications.count() == 1
        assert student.email in notifications.first().message

    def test_submission_creates_notification(self, instructor, student, course):
        from courses.models import Unit
        from django.utils import timezone

        unit = Unit.objects.create(course=course, title='Unit 1', order=1)
        assignment = Assignment.objects.create(unit=unit, title='Assignment 1')

        # Create and submit
        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            content='My submission'
        )
        submission.status = 'submitted'
        submission.submitted_at = timezone.now()
        submission.save()

        notifications = Notification.objects.filter(
            recipient=instructor,
            type='submission'
        )
        assert notifications.count() == 1

    def test_grade_creates_notification(self, instructor, student, course):
        from courses.models import Unit

        unit = Unit.objects.create(course=course, title='Unit 1', order=1)
        assignment = Assignment.objects.create(unit=unit, title='Assignment 1', max_points=100)

        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            content='My submission',
            status='submitted'
        )

        # Grading should notify the student
        Grade.objects.create(
            submission=submission,
            grader=instructor,
            points=85,
            feedback='Good work!'
        )

        notifications = Notification.objects.filter(
            recipient=student,
            type='grade'
        )
        assert notifications.count() == 1
        assert '85' in notifications.first().message

    def test_new_lesson_notifies_enrolled_students(self, instructor, student, course):
        from courses.models import Unit, Lesson

        # Enroll student first
        Enrollment.objects.create(user=student, course=course)
        # Clear enrollment notification
        Notification.objects.all().delete()

        unit = Unit.objects.create(course=course, title='Unit 1', order=1)
        Lesson.objects.create(unit=unit, title='New Lesson', order=1)

        notifications = Notification.objects.filter(
            recipient=student,
            type='new_lesson'
        )
        assert notifications.count() == 1
        assert 'New Lesson' in notifications.first().message

    def test_new_assignment_notifies_enrolled_students(self, instructor, student, course):
        from courses.models import Unit

        # Enroll student first
        Enrollment.objects.create(user=student, course=course)
        # Clear enrollment notification
        Notification.objects.all().delete()

        unit = Unit.objects.create(course=course, title='Unit 1', order=1)
        Assignment.objects.create(unit=unit, title='New Assignment', max_points=100)

        notifications = Notification.objects.filter(
            recipient=student,
            type='new_assignment'
        )
        assert notifications.count() == 1
        assert 'New Assignment' in notifications.first().message

    def test_resubmission_allowed_notifies_student(self, api_client, instructor, student, course):
        from courses.models import Unit
        from django.utils import timezone

        # Setup
        Enrollment.objects.create(user=student, course=course)
        unit = Unit.objects.create(course=course, title='Unit 1', order=1)
        assignment = Assignment.objects.create(unit=unit, title='Assignment 1', max_points=100)

        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            content='My submission',
            status='submitted',
            submitted_at=timezone.now()
        )
        Grade.objects.create(submission=submission, grader=instructor, points=50)

        # Clear previous notifications
        Notification.objects.all().delete()

        # Allow resubmission as instructor
        api_client.force_authenticate(user=instructor)
        response = api_client.post(f'/api/assignments/submissions/{submission.id}/allow-resubmit/')

        assert response.status_code == 200

        notifications = Notification.objects.filter(
            recipient=student,
            type='resubmission'
        )
        assert notifications.count() == 1
        assert 'resubmit' in notifications.first().message.lower()


@pytest.mark.django_db
class TestNotificationRelatedUrls:
    """Notification related_url values must point at real frontend routes."""

    def _setup_assignment(self, student, course):
        from courses.models import Unit

        Enrollment.objects.create(user=student, course=course)
        Notification.objects.all().delete()
        unit = Unit.objects.create(course=course, title='Unit 1', order=1)
        return Assignment.objects.create(unit=unit, title='Assignment 1', max_points=100)

    def test_new_assignment_url_is_course_nested(self, instructor, student, course):
        assignment = self._setup_assignment(student, course)

        notification = Notification.objects.get(recipient=student, type='new_assignment')
        assert notification.related_url == f'/courses/{course.code}/assignments/{assignment.id}'

    def test_grade_url_is_course_nested(self, instructor, student, course):
        assignment = self._setup_assignment(student, course)
        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            content='My submission',
            status='submitted'
        )
        Grade.objects.create(submission=submission, grader=instructor, points=85)

        notification = Notification.objects.get(recipient=student, type='grade')
        assert notification.related_url == f'/courses/{course.code}/assignments/{assignment.id}'

    def test_resubmission_url_is_course_nested(self, instructor, student, course):
        from notifications.signals import notify_student_resubmission_allowed

        assignment = self._setup_assignment(student, course)
        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            content='My submission',
            status='submitted'
        )

        notify_student_resubmission_allowed(submission)

        notification = Notification.objects.get(recipient=student, type='resubmission')
        assert notification.related_url == f'/courses/{course.code}/assignments/{assignment.id}'

    def test_new_lesson_url_uses_learn_path(self, instructor, student, course):
        from courses.models import Unit, Lesson

        Enrollment.objects.create(user=student, course=course)
        Notification.objects.all().delete()
        unit = Unit.objects.create(course=course, title='Unit 1', order=1)
        lesson = Lesson.objects.create(unit=unit, title='Lesson 1', order=1)

        notification = Notification.objects.get(recipient=student, type='new_lesson')
        assert notification.related_url == f'/courses/{course.code}/learn/{lesson.id}'


@pytest.mark.django_db
class TestAssignmentUrlDataMigration:
    """0003_rewrite_assignment_urls rewrites legacy /assignments/<id> URLs."""

    def _run_migration(self):
        from importlib import import_module

        from django.apps import apps as django_apps

        migration = import_module('notifications.migrations.0003_rewrite_assignment_urls')
        migration.rewrite_assignment_urls(django_apps, None)

    def test_rewrites_url_for_existing_assignment(self, instructor, student, course):
        from courses.models import Unit

        unit = Unit.objects.create(course=course, title='Unit 1', order=1)
        assignment = Assignment.objects.create(unit=unit, title='Assignment 1')
        Notification.objects.all().delete()
        notification = Notification.objects.create(
            recipient=student,
            type='new_assignment',
            title='Legacy',
            message='m',
            related_url=f'/assignments/{assignment.id}'
        )

        self._run_migration()

        notification.refresh_from_db()
        assert notification.related_url == f'/courses/{course.code}/assignments/{assignment.id}'

    def test_clears_url_for_missing_assignment(self, student):
        notification = Notification.objects.create(
            recipient=student,
            type='new_assignment',
            title='Orphaned',
            message='m',
            related_url='/assignments/999999'
        )

        self._run_migration()

        notification.refresh_from_db()
        assert notification.related_url == ''

    def test_leaves_other_urls_untouched(self, student):
        untouched = [
            '/instructor/assignments/5/grade',
            '/courses/CS101/assignments/5',
            '/courses/CS101/lessons/3',
            '',
        ]
        notifications = [
            Notification.objects.create(
                recipient=student, type='grade', title='t', message='m', related_url=url
            )
            for url in untouched
        ]

        self._run_migration()

        for notification, url in zip(notifications, untouched):
            notification.refresh_from_db()
            assert notification.related_url == url
