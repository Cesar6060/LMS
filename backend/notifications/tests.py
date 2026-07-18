import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from courses.models import Course, Enrollment
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
            type='announcement',
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
            type='announcement',
            title='Test 1',
            message='Message 1'
        )
        Notification.objects.create(
            recipient=student,
            type='announcement',
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
            type='announcement',
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
            type='announcement',
            title='Test',
            message='Message'
        )

        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/notifications/{notification.id}/read/')

        assert response.status_code == status.HTTP_200_OK
        notification.refresh_from_db()
        assert notification.is_read is True

    def test_mark_all_as_read(self, api_client, student):
        Notification.objects.create(recipient=student, type='announcement', title='1', message='m')
        Notification.objects.create(recipient=student, type='announcement', title='2', message='m')

        api_client.force_authenticate(user=student)
        response = api_client.post('/api/notifications/mark-all-read/')

        assert response.status_code == status.HTTP_200_OK
        assert Notification.objects.filter(recipient=student, is_read=False).count() == 0

    def test_unread_count(self, api_client, student):
        Notification.objects.create(recipient=student, type='announcement', title='1', message='m')
        Notification.objects.create(recipient=student, type='announcement', title='2', message='m')
        Notification.objects.create(recipient=student, type='announcement', title='3', message='m', is_read=True)

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


@pytest.mark.django_db
class TestNotificationRelatedUrls:
    """Notification related_url values must point at real frontend routes."""

    def test_new_lesson_url_uses_learn_path(self, instructor, student, course):
        from courses.models import Unit, Lesson

        Enrollment.objects.create(user=student, course=course)
        Notification.objects.all().delete()
        unit = Unit.objects.create(course=course, title='Unit 1', order=1)
        lesson = Lesson.objects.create(unit=unit, title='Lesson 1', order=1)

        notification = Notification.objects.get(recipient=student, type='new_lesson')
        assert notification.related_url == f'/courses/{course.code}/learn/{lesson.id}'


@pytest.mark.django_db
class TestRemovedTypePurgeMigration:
    """0004_remove_assignment_types deletes rows of removed notification types."""

    def _run_migration(self):
        from importlib import import_module

        from django.apps import apps as django_apps

        migration = import_module('notifications.migrations.0004_remove_assignment_types')
        migration.delete_assignment_notifications(django_apps, None)

    def test_purges_removed_types(self, student):
        for removed_type in ['submission', 'grade', 'new_assignment', 'resubmission']:
            Notification.objects.create(
                recipient=student, type=removed_type, title='t', message='m'
            )
        kept = Notification.objects.create(
            recipient=student, type='announcement', title='keep', message='m'
        )

        self._run_migration()

        assert Notification.objects.count() == 1
        assert Notification.objects.first().pk == kept.pk
