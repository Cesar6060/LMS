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
def student_two():
    return User.objects.create_user(
        email='student2@test.com',
        password='testpass123',
        first_name='Second',
        last_name='Student',
        is_instructor=False
    )


@pytest.fixture
def other_instructor():
    return User.objects.create_user(
        email='instructor2@test.com',
        password='testpass123',
        first_name='Other',
        last_name='Instructor',
        is_instructor=True
    )


@pytest.fixture
def course(instructor):
    return Course.objects.create(
        code='TEST101',
        title='Test Course',
        description='A test course',
        instructor=instructor
    )


@pytest.fixture
def other_course(other_instructor):
    return Course.objects.create(
        code='OTHER101',
        title='Other Course',
        description='A second test course',
        instructor=other_instructor
    )


@pytest.fixture
def unit(course):
    from courses.models import Unit

    return Unit.objects.create(course=course, title='Unit 1', order=1)


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

        # Phase 55 (A6): the list is paginated — rows live under `results`.
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert len(response.data['results']) == 2

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
        assert response.data['count'] == 1
        assert response.data['results'][0]['title'] == 'For Student'

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
class TestEnrollmentSignal:
    """post_save on Enrollment -> notify_instructor_on_enrollment."""

    def test_enrollment_notification_fields(self, instructor, student, course):
        Enrollment.objects.create(user=student, course=course)

        notification = Notification.objects.get(recipient=instructor, type='enrollment')
        assert notification.title == f'New enrollment in {course.code}'
        assert notification.message == (
            f'{student.first_name} {student.last_name} '
            f'({student.email}) has enrolled in {course.title}.'
        )
        assert notification.related_url == f'/instructor/courses/{course.code}/manage'
        assert notification.is_read is False

    def test_enrollment_notifies_only_the_course_instructor(
        self, instructor, other_instructor, student, course, other_course
    ):
        Enrollment.objects.create(user=student, course=course)

        assert Notification.objects.count() == 1
        assert Notification.objects.filter(recipient=instructor).count() == 1
        # The enrolling student and unrelated instructors get nothing.
        assert Notification.objects.filter(recipient=student).count() == 0
        assert Notification.objects.filter(recipient=other_instructor).count() == 0

    def test_enrollment_update_does_not_notify_again(self, instructor, student, course):
        """Only `created` fires the signal; later saves must stay silent."""
        enrollment = Enrollment.objects.create(user=student, course=course)

        enrollment.update_activity()
        enrollment.is_active = False
        enrollment.save(update_fields=['is_active'])
        enrollment.save()

        assert Notification.objects.filter(recipient=instructor, type='enrollment').count() == 1

    def test_reactivated_enrollment_does_not_notify(self, instructor, student, course):
        """A soft-deleted student rejoining flips is_active, which is not a create.

        Documents current behaviour: the re-activation paths in courses.views
        (`enroll` and `_activate_enrollment`) produce no instructor notification.
        """
        enrollment = Enrollment.objects.create(user=student, course=course)
        Notification.objects.all().delete()

        enrollment.is_active = False
        enrollment.save(update_fields=['is_active'])
        enrollment.is_active = True
        enrollment.save(update_fields=['is_active'])

        assert Notification.objects.filter(type='enrollment').count() == 0

    def test_each_enrollment_creates_its_own_notification(
        self, instructor, student, student_two, course
    ):
        Enrollment.objects.create(user=student, course=course)
        Enrollment.objects.create(user=student_two, course=course)

        notifications = Notification.objects.filter(recipient=instructor, type='enrollment')
        assert notifications.count() == 2
        messages = ' '.join(notifications.values_list('message', flat=True))
        assert student.email in messages
        assert student_two.email in messages


@pytest.mark.django_db
class TestNewLessonSignal:
    """post_save on Lesson -> notify_students_on_new_lesson."""

    def test_new_lesson_notification_fields(self, student, course, unit):
        from courses.models import Lesson

        Enrollment.objects.create(user=student, course=course)
        Notification.objects.all().delete()

        lesson = Lesson.objects.create(unit=unit, title='Sprites 101', order=1)

        notification = Notification.objects.get(recipient=student, type='new_lesson')
        assert notification.title == f'New lesson in {course.code}'
        assert notification.message == (
            f'A new lesson "{lesson.title}" has been added to {course.title}.'
        )
        assert notification.related_url == f'/courses/{course.code}/learn/{lesson.id}'
        assert notification.is_read is False

    def test_new_lesson_notifies_every_active_student(
        self, student, student_two, course, unit
    ):
        from courses.models import Lesson

        Enrollment.objects.create(user=student, course=course)
        Enrollment.objects.create(user=student_two, course=course)
        Notification.objects.all().delete()

        Lesson.objects.create(unit=unit, title='Lesson 1', order=1)

        notifications = Notification.objects.filter(type='new_lesson')
        assert notifications.count() == 2
        assert set(notifications.values_list('recipient_id', flat=True)) == {
            student.id, student_two.id
        }

    def test_new_lesson_skips_inactive_enrollments(self, student, student_two, course, unit):
        """The signal filters on is_active=True — removed students stay quiet."""
        from courses.models import Lesson

        Enrollment.objects.create(user=student, course=course, is_active=False)
        Enrollment.objects.create(user=student_two, course=course)
        Notification.objects.all().delete()

        Lesson.objects.create(unit=unit, title='Lesson 1', order=1)

        assert Notification.objects.filter(recipient=student, type='new_lesson').count() == 0
        assert Notification.objects.filter(recipient=student_two, type='new_lesson').count() == 1

    def test_lesson_update_does_not_notify_again(self, student, course, unit):
        """Only `created` fires the signal; edits to an existing lesson stay silent."""
        from courses.models import Lesson

        Enrollment.objects.create(user=student, course=course)
        lesson = Lesson.objects.create(unit=unit, title='Lesson 1', order=1)
        Notification.objects.all().delete()

        lesson.title = 'Lesson 1 (revised)'
        lesson.content = 'New body copy'
        lesson.save()

        assert Notification.objects.filter(type='new_lesson').count() == 0

    def test_new_lesson_does_not_notify_the_instructor(self, instructor, student, course, unit):
        """The instructor is not enrolled, so they are not in the recipient set."""
        from courses.models import Lesson

        Enrollment.objects.create(user=student, course=course)
        Notification.objects.all().delete()

        Lesson.objects.create(unit=unit, title='Lesson 1', order=1)

        assert Notification.objects.filter(recipient=instructor).count() == 0

    def test_new_lesson_does_not_notify_students_of_other_courses(
        self, student, student_two, course, other_course, unit
    ):
        from courses.models import Lesson

        Enrollment.objects.create(user=student, course=course)
        Enrollment.objects.create(user=student_two, course=other_course)
        Notification.objects.all().delete()

        Lesson.objects.create(unit=unit, title='Lesson 1', order=1)

        assert Notification.objects.filter(recipient=student, type='new_lesson').count() == 1
        assert Notification.objects.filter(recipient=student_two).count() == 0

    def test_new_lesson_with_no_enrollments_creates_nothing(self, course, unit):
        """bulk_create on an empty list must be a no-op, not an error."""
        from courses.models import Lesson

        Lesson.objects.create(unit=unit, title='Lesson 1', order=1)

        assert Notification.objects.count() == 0


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
