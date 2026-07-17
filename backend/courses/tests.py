import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from accounts.models import User
from .models import Course, Unit, Lesson, Enrollment, LessonProgress, Announcement
from assignments.models import Assignment, Submission, Grade
from notifications.models import Notification


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def student():
    return User.objects.create_user(
        email='student@test.com',
        password='testpass123',
        first_name='Test',
        last_name='Student'
    )


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
def course(instructor):
    return Course.objects.create(
        code='VGD101',
        title='Intro to Game Development',
        description='Learn the basics of game development.',
        instructor=instructor
    )


@pytest.fixture
def unit(course):
    return Unit.objects.create(
        course=course,
        title='Getting Started',
        order=1
    )


@pytest.fixture
def lesson(unit):
    return Lesson.objects.create(
        unit=unit,
        title='Welcome to the Course',
        content='# Welcome\n\nThis is your first lesson.',
        order=1
    )


@pytest.fixture
def enrollment(student, course):
    return Enrollment.objects.create(user=student, course=course)


@pytest.mark.django_db
class TestCourseModel:
    def test_create_course(self, instructor):
        course = Course.objects.create(
            code='VGD102',
            title='Advanced Game Dev',
            instructor=instructor
        )
        assert course.code == 'VGD102'
        assert course.instructor == instructor
        assert len(course.enrollment_code) == 8
        assert course.is_active is True

    def test_enrollment_code_generation(self, instructor):
        course = Course.objects.create(
            code='VGD103',
            title='Test Course',
            instructor=instructor
        )
        old_code = course.enrollment_code
        new_code = course.regenerate_enrollment_code()
        assert new_code != old_code
        assert len(new_code) == 8


@pytest.mark.django_db
class TestCourseEndpoints:
    def test_list_courses_student_only_sees_enrolled(self, api_client, student, course):
        """Students only see courses they are enrolled in."""
        api_client.force_authenticate(user=student)

        # Before enrollment - student sees no courses
        response = api_client.get('/api/courses/courses/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

        # After enrollment - student sees the course
        Enrollment.objects.create(user=student, course=course)
        response = api_client.get('/api/courses/courses/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['code'] == 'VGD101'

    def test_list_courses_unauthenticated(self, api_client):
        response = api_client.get('/api/courses/courses/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_course_as_instructor(self, api_client, instructor):
        api_client.force_authenticate(user=instructor)
        response = api_client.post('/api/courses/courses/', {
            'code': 'VGD102',
            'title': 'New Course',
            'description': 'A new course'
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['code'] == 'VGD102'

    def test_create_course_as_student_fails(self, api_client, student):
        api_client.force_authenticate(user=student)
        response = api_client.post('/api/courses/courses/', {
            'code': 'VGD102',
            'title': 'New Course'
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_course_detail(self, api_client, student, course, unit, lesson):
        """Students can only view course details if enrolled."""
        api_client.force_authenticate(user=student)

        # Before enrollment - student cannot see course details
        response = api_client.get(f'/api/courses/courses/{course.code}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # After enrollment - student can see course details
        Enrollment.objects.create(user=student, course=course)
        response = api_client.get(f'/api/courses/courses/{course.code}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['code'] == 'VGD101'
        assert len(response.data['units']) == 1
        # Enrollment code should be hidden from non-instructors
        assert 'enrollment_code' not in response.data

    def test_instructor_sees_enrollment_code(self, api_client, instructor, course):
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/')
        assert response.status_code == status.HTTP_200_OK
        assert 'enrollment_code' in response.data


@pytest.mark.django_db
class TestEnrollment:
    def test_enroll_with_valid_code(self, api_client, student, course):
        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/courses/courses/{course.code}/enroll/', {
            'enrollment_code': course.enrollment_code
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert Enrollment.objects.filter(user=student, course=course).exists()

    def test_enroll_with_invalid_code(self, api_client, student, course):
        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/courses/courses/{course.code}/enroll/', {
            'enrollment_code': 'INVALID1'
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_enroll_twice_fails(self, api_client, student, course, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/courses/courses/{course.code}/enroll/', {
            'enrollment_code': course.enrollment_code
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'already enrolled' in response.data['error'].lower()

    def test_instructor_cannot_enroll_own_course(self, api_client, instructor, course):
        api_client.force_authenticate(user=instructor)
        response = api_client.post(f'/api/courses/courses/{course.code}/enroll/', {
            'enrollment_code': course.enrollment_code
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_my_enrollments(self, api_client, student, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.get('/api/courses/enrollments/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_enroll_via_enrollment_endpoint(self, api_client, student, course):
        api_client.force_authenticate(user=student)
        response = api_client.post('/api/courses/enrollments/', {
            'enrollment_code': course.enrollment_code
        })
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestUnits:
    def test_list_units_for_course(self, api_client, student, course, unit, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/units/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_list_units_not_enrolled_forbidden(self, api_client, student, course, unit):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/units/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data

    def test_create_unit_as_instructor(self, api_client, instructor, course):
        api_client.force_authenticate(user=instructor)
        response = api_client.post(f'/api/courses/courses/{course.code}/units/', {
            'title': 'New Unit'
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'New Unit'
        assert response.data['order'] == 1

    def test_create_unit_as_student_fails(self, api_client, student, course):
        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/courses/courses/{course.code}/units/', {
            'title': 'New Unit'
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestLessons:
    def test_list_lessons_for_unit(self, api_client, student, unit, lesson, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/units/{unit.id}/lessons/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_list_lessons_not_enrolled_forbidden(self, api_client, student, unit, lesson):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/units/{unit.id}/lessons/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data

    def test_get_lesson_detail_enrolled(self, api_client, student, lesson, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/lessons/{lesson.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Welcome to the Course'
        assert '# Welcome' in response.data['content']

    def test_get_lesson_detail_not_enrolled(self, api_client, student, lesson):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/lessons/{lesson.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_lesson_as_instructor(self, api_client, instructor, unit):
        api_client.force_authenticate(user=instructor)
        response = api_client.post(f'/api/courses/units/{unit.id}/lessons/', {
            'title': 'New Lesson',
            'content': 'Lesson content here'
        })
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestLessonProgress:
    def test_get_lesson_progress(self, api_client, student, lesson, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/lessons/{lesson.id}/progress/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['completed'] is False
        assert response.data['video_position'] == 0

    def test_update_lesson_progress(self, api_client, student, lesson, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.patch(f'/api/courses/lessons/{lesson.id}/progress/', {
            'video_position': 120,
            'completed': True
        })
        assert response.status_code == status.HTTP_200_OK
        assert response.data['video_position'] == 120
        assert response.data['completed'] is True

    def test_progress_requires_enrollment(self, api_client, student, lesson):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/lessons/{lesson.id}/progress/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestInstructorCourses:
    def test_instructor_courses_list(self, api_client, instructor, course):
        api_client.force_authenticate(user=instructor)
        response = api_client.get('/api/courses/instructor/courses/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert 'enrollment_code' in response.data[0]

    def test_regenerate_enrollment_code(self, api_client, instructor, course):
        api_client.force_authenticate(user=instructor)
        old_code = course.enrollment_code
        response = api_client.post(f'/api/courses/courses/{course.code}/regenerate_code/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['enrollment_code'] != old_code


@pytest.mark.django_db
class TestCourseProgress:
    def test_get_course_progress_empty(self, api_client, student, course, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/progress/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_lessons'] == 0
        assert response.data['completed_lessons'] == 0
        assert response.data['progress_percentage'] == 0

    def test_get_course_progress_with_lessons(self, api_client, student, course, unit, lesson, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/progress/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_lessons'] == 1
        assert response.data['completed_lessons'] == 0
        assert response.data['progress_percentage'] == 0

    def test_course_progress_after_completion(self, api_client, student, course, unit, lesson, enrollment):
        api_client.force_authenticate(user=student)
        # Mark lesson as complete
        api_client.patch(f'/api/courses/lessons/{lesson.id}/progress/', {'completed': True})

        response = api_client.get(f'/api/courses/courses/{course.code}/progress/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_lessons'] == 1
        assert response.data['completed_lessons'] == 1
        assert response.data['progress_percentage'] == 100

    def test_course_progress_requires_enrollment(self, api_client, student, course):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/progress/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.fixture
def announcement(course, instructor):
    return Announcement.objects.create(
        course=course,
        author=instructor,
        title='Welcome Announcement',
        content='Welcome to the course! This is your first announcement.',
        send_email=False
    )


@pytest.mark.django_db
class TestAnnouncements:
    def test_list_announcements_enrolled(self, api_client, student, course, announcement, enrollment):
        """Enrolled students can see announcements."""
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/announcements/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['title'] == 'Welcome Announcement'

    def test_list_announcements_not_enrolled(self, api_client, student, course, announcement):
        """Non-enrolled students cannot see announcements."""
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/announcements/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_announcements_instructor(self, api_client, instructor, course, announcement):
        """Instructor can see their course announcements."""
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/announcements/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_create_announcement_as_instructor(self, api_client, instructor, course):
        """Instructor can create announcements."""
        api_client.force_authenticate(user=instructor)
        response = api_client.post(f'/api/courses/courses/{course.code}/announcements/', {
            'title': 'New Announcement',
            'content': 'This is a new announcement.',
            'is_pinned': True
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'New Announcement'
        assert response.data['is_pinned'] is True

    def test_create_announcement_as_student_fails(self, api_client, student, course, enrollment):
        """Students cannot create announcements."""
        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/courses/courses/{course.code}/announcements/', {
            'title': 'Student Announcement',
            'content': 'This should not work.'
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_announcement_creates_notifications(self, api_client, instructor, course, enrollment, student):
        """Creating an announcement notifies enrolled students."""
        api_client.force_authenticate(user=instructor)
        response = api_client.post(f'/api/courses/courses/{course.code}/announcements/', {
            'title': 'Important Update',
            'content': 'This is an important announcement for all students.'
        })
        assert response.status_code == status.HTTP_201_CREATED

        # Verify notification was created for enrolled student
        notification = Notification.objects.filter(
            recipient=student,
            type='announcement'
        ).first()
        assert notification is not None
        assert 'Important Update' in notification.title

    def test_get_announcement_detail(self, api_client, student, announcement, enrollment):
        """Enrolled students can view announcement details."""
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/announcements/{announcement.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Welcome Announcement'
        assert response.data['content'] == 'Welcome to the course! This is your first announcement.'

    def test_update_announcement_as_instructor(self, api_client, instructor, announcement):
        """Instructor can update their announcements."""
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(f'/api/courses/announcements/{announcement.id}/', {
            'title': 'Updated Title'
        })
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Updated Title'

    def test_update_announcement_as_student_fails(self, api_client, student, announcement, enrollment):
        """Students cannot update announcements."""
        api_client.force_authenticate(user=student)
        response = api_client.patch(f'/api/courses/announcements/{announcement.id}/', {
            'title': 'Hacked Title'
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_announcement_as_instructor(self, api_client, instructor, announcement):
        """Instructor can delete announcements."""
        api_client.force_authenticate(user=instructor)
        response = api_client.delete(f'/api/courses/announcements/{announcement.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Announcement.objects.filter(id=announcement.id).exists()

    def test_pin_announcement(self, api_client, instructor, announcement):
        """Instructor can pin announcements."""
        api_client.force_authenticate(user=instructor)
        response = api_client.post(f'/api/courses/announcements/{announcement.id}/pin/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_pinned'] is True

    def test_unpin_announcement(self, api_client, instructor, course):
        """Instructor can unpin announcements."""
        pinned = Announcement.objects.create(
            course=course,
            author=instructor,
            title='Pinned',
            content='Content',
            is_pinned=True
        )
        api_client.force_authenticate(user=instructor)
        response = api_client.post(f'/api/courses/announcements/{pinned.id}/unpin/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_pinned'] is False

    def test_pinned_announcements_first(self, api_client, instructor, course):
        """Pinned announcements appear before unpinned ones."""
        api_client.force_authenticate(user=instructor)
        # Create unpinned first
        Announcement.objects.create(
            course=course,
            author=instructor,
            title='Regular',
            content='Regular content'
        )
        # Create pinned second
        Announcement.objects.create(
            course=course,
            author=instructor,
            title='Pinned',
            content='Pinned content',
            is_pinned=True
        )
        response = api_client.get(f'/api/courses/courses/{course.code}/announcements/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]['title'] == 'Pinned'
        assert response.data[1]['title'] == 'Regular'


@pytest.fixture
def assignment(unit):
    return Assignment.objects.create(
        unit=unit,
        title='Test Assignment',
        description='Test description',
        max_points=100,
        order=1
    )


@pytest.fixture
def second_student():
    return User.objects.create_user(
        email='student2@test.com',
        password='testpass123',
        first_name='Second',
        last_name='Student'
    )


@pytest.mark.django_db
class TestGradebook:
    def test_gradebook_instructor_only(self, api_client, student, course, enrollment):
        """Students cannot view the gradebook."""
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_gradebook_returns_structure(self, api_client, instructor, course, unit, assignment, student, enrollment):
        """Gradebook returns correct structure."""
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')
        assert response.status_code == status.HTTP_200_OK
        assert 'course' in response.data
        assert 'gradebook_items' in response.data
        assert 'students' in response.data
        assert response.data['course']['code'] == course.code

    def test_gradebook_shows_assignments(self, api_client, instructor, course, unit, assignment):
        """Gradebook shows all assignments."""
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')
        assignment_items = [i for i in response.data['gradebook_items'] if i['type'] == 'assignment']
        assert len(assignment_items) == 1
        assert assignment_items[0]['title'] == 'Test Assignment'
        assert assignment_items[0]['max_points'] == 100

    def test_gradebook_shows_students(self, api_client, instructor, course, unit, student, enrollment):
        """Gradebook shows enrolled students."""
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')
        assert len(response.data['students']) == 1
        assert response.data['students'][0]['email'] == student.email

    def test_gradebook_shows_grades(self, api_client, instructor, course, unit, assignment, student, enrollment):
        """Gradebook shows graded submissions."""
        api_client.force_authenticate(user=instructor)

        # Create and grade a submission
        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            content='My answer',
            status='submitted'
        )
        Grade.objects.create(
            submission=submission,
            grader=instructor,
            points=85
        )
        submission.status = 'graded'
        submission.save()

        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')
        assert response.status_code == status.HTTP_200_OK
        student_data = response.data['students'][0]
        assert student_data['grades'][0]['points_earned'] == 85
        assert student_data['grades'][0]['status'] == 'graded'
        assert student_data['total_earned'] == 85
        assert student_data['percentage'] == 85.0
        assert student_data['letter_grade'] == 'B'

    def test_gradebook_shows_pending(self, api_client, instructor, course, unit, assignment, student, enrollment):
        """Gradebook shows pending (submitted but not graded) submissions."""
        api_client.force_authenticate(user=instructor)

        Submission.objects.create(
            assignment=assignment,
            student=student,
            content='My answer',
            status='submitted'
        )

        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')
        student_data = response.data['students'][0]
        assert student_data['grades'][0]['status'] == 'submitted'
        assert student_data['grades'][0]['points_earned'] is None

    def test_gradebook_calculates_letter_grades(self, api_client, instructor, course, unit, student, enrollment):
        """Gradebook calculates correct letter grades."""
        api_client.force_authenticate(user=instructor)

        # Create multiple assignments
        a1 = Assignment.objects.create(unit=unit, title='A1', max_points=100, order=1)
        a2 = Assignment.objects.create(unit=unit, title='A2', max_points=100, order=2)

        # Grade both: 90 + 80 = 170/200 = 85% = B
        s1 = Submission.objects.create(assignment=a1, student=student, status='submitted')
        Grade.objects.create(submission=s1, grader=instructor, points=90)
        s1.status = 'graded'
        s1.save()

        s2 = Submission.objects.create(assignment=a2, student=student, status='submitted')
        Grade.objects.create(submission=s2, grader=instructor, points=80)
        s2.status = 'graded'
        s2.save()

        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')
        student_data = response.data['students'][0]
        assert student_data['total_earned'] == 170
        assert student_data['total_possible'] == 200
        assert student_data['percentage'] == 85.0
        assert student_data['letter_grade'] == 'B'

    def test_gradebook_export_csv(self, api_client, instructor, course, unit, assignment, student, enrollment):
        """Gradebook export returns CSV file."""
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/export/')
        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'text/csv'
        assert f'{course.code}_gradebook.csv' in response['Content-Disposition']

    def test_gradebook_export_student_forbidden(self, api_client, student, course, enrollment):
        """Students cannot export gradebook."""
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/export/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_gradebook_multiple_students(self, api_client, instructor, course, unit, assignment, student, second_student, enrollment):
        """Gradebook shows multiple students."""
        # Enroll second student
        Enrollment.objects.create(user=second_student, course=course)

        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')
        assert len(response.data['students']) == 2


@pytest.mark.django_db
class TestStudentRoster:
    def test_roster_instructor_only(self, api_client, student, course, enrollment):
        """Students cannot view the roster."""
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/students/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_roster_returns_students(self, api_client, instructor, course, student, enrollment):
        """Roster returns enrolled students."""
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/students/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['email'] == student.email

    def test_roster_includes_activity_data(self, api_client, instructor, course, student, enrollment):
        """Roster includes activity tracking fields."""
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/students/')
        assert 'last_activity_at' in response.data[0]
        assert 'is_inactive' in response.data[0]
        assert 'progress_percentage' in response.data[0]

    def test_roster_excludes_removed_students(self, api_client, instructor, course, student, enrollment):
        """Roster excludes soft-deleted students."""
        enrollment.is_active = False
        enrollment.save()

        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/students/')
        assert len(response.data) == 0

    def test_remove_student(self, api_client, instructor, course, student, enrollment):
        """Instructor can remove a student (soft delete)."""
        api_client.force_authenticate(user=instructor)
        response = api_client.delete(f'/api/courses/courses/{course.code}/students/{enrollment.id}/')
        assert response.status_code == status.HTTP_200_OK

        enrollment.refresh_from_db()
        assert enrollment.is_active is False

    def test_remove_student_preserves_grades(self, api_client, instructor, course, unit, student, enrollment):
        """Removing student preserves their grades."""
        # Create an assignment and grade
        assignment = Assignment.objects.create(unit=unit, title='Test', max_points=100, order=1)
        submission = Submission.objects.create(assignment=assignment, student=student, status='submitted')
        Grade.objects.create(submission=submission, grader=instructor, points=90)

        api_client.force_authenticate(user=instructor)
        api_client.delete(f'/api/courses/courses/{course.code}/students/{enrollment.id}/')

        # Grade should still exist
        assert Grade.objects.filter(submission=submission).exists()

    def test_student_cannot_remove_others(self, api_client, student, course, enrollment):
        """Students cannot remove other students."""
        api_client.force_authenticate(user=student)
        response = api_client.delete(f'/api/courses/courses/{course.code}/students/{enrollment.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_send_invite_success(self, api_client, instructor, course):
        """Instructor can send course invitation email."""
        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/courses/courses/{course.code}/students/invite/',
            {'email': 'newstudent@example.com'}
        )
        assert response.status_code == status.HTTP_200_OK
        assert 'newstudent@example.com' in response.data['message']

    def test_send_invite_invalid_email(self, api_client, instructor, course):
        """Sending invite with invalid email fails."""
        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/courses/courses/{course.code}/students/invite/',
            {'email': 'not-an-email'}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Invalid email' in response.data['error']

    def test_send_invite_already_enrolled(self, api_client, instructor, course, student, enrollment):
        """Cannot send invite to already enrolled student."""
        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/courses/courses/{course.code}/students/invite/',
            {'email': student.email}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'already enrolled' in response.data['error']

    def test_send_invite_student_forbidden(self, api_client, student, course):
        """Students cannot send invitations."""
        api_client.force_authenticate(user=student)
        response = api_client.post(
            f'/api/courses/courses/{course.code}/students/invite/',
            {'email': 'someone@example.com'}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_activity(self, api_client, student, course, enrollment):
        """Student can update their activity timestamp."""
        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/courses/courses/{course.code}/activity/')
        assert response.status_code == status.HTTP_200_OK

        enrollment.refresh_from_db()
        assert enrollment.last_activity_at is not None


@pytest.mark.django_db
class TestGradebookWithQuizzes:
    """Tests for gradebook including quiz scores."""

    def test_gradebook_includes_quizzes(self, api_client, instructor, course, unit):
        """Test that gradebook includes quiz items."""
        from quizzes.models import Quiz

        # Create a quiz
        quiz = Quiz.objects.create(
            unit=unit,
            title='Test Quiz',
            points=20,
            passing_score=70
        )

        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')

        assert response.status_code == 200
        assert 'gradebook_items' in response.data
        assert response.data['has_quizzes'] is True

        # Find the quiz in gradebook_items
        quiz_items = [i for i in response.data['gradebook_items'] if i['type'] == 'quiz']
        assert len(quiz_items) == 1
        assert quiz_items[0]['title'] == 'Test Quiz'
        assert quiz_items[0]['max_points'] == 20

    def test_gradebook_shows_quiz_scores(self, api_client, instructor, student, course, unit, enrollment):
        """Test that gradebook shows student quiz scores."""
        from quizzes.models import Quiz, QuizAttempt

        quiz = Quiz.objects.create(
            unit=unit,
            title='Test Quiz',
            points=10,
            passing_score=70
        )

        # Create a quiz attempt for the student
        QuizAttempt.objects.create(
            quiz=quiz,
            student=student,
            score=85.00,
            passed=True
        )

        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')

        assert response.status_code == 200

        # Find the student
        student_data = next(s for s in response.data['students'] if s['id'] == student.id)

        # Find the quiz grade
        quiz_grade = next(g for g in student_data['grades'] if g.get('item_type') == 'quiz')
        assert quiz_grade['status'] == 'graded'
        assert quiz_grade['points_earned'] == 8.5  # 85% of 10 points
        assert quiz_grade['passed'] is True

    def test_gradebook_shows_best_quiz_score(self, api_client, instructor, student, course, unit, enrollment):
        """Test that gradebook shows the best quiz score when multiple attempts exist."""
        from quizzes.models import Quiz, QuizAttempt

        quiz = Quiz.objects.create(
            unit=unit,
            title='Test Quiz',
            points=10,
            passing_score=70
        )

        # Create multiple attempts - should show best score
        QuizAttempt.objects.create(quiz=quiz, student=student, score=60.00, passed=False)
        QuizAttempt.objects.create(quiz=quiz, student=student, score=90.00, passed=True)
        QuizAttempt.objects.create(quiz=quiz, student=student, score=75.00, passed=True)

        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')

        student_data = next(s for s in response.data['students'] if s['id'] == student.id)
        quiz_grade = next(g for g in student_data['grades'] if g.get('item_type') == 'quiz')

        # Should show best score (90%)
        assert quiz_grade['points_earned'] == 9.0  # 90% of 10 points
        assert quiz_grade['score_percentage'] == 90.0

    def test_gradebook_total_includes_quizzes(self, api_client, instructor, student, course, unit, enrollment):
        """Test that total possible points includes quiz points."""
        from quizzes.models import Quiz
        from assignments.models import Assignment

        Assignment.objects.create(
            unit=unit,
            title='Test Assignment',
            max_points=100
        )

        Quiz.objects.create(
            unit=unit,
            title='Test Quiz',
            points=20,
            passing_score=70
        )

        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')

        assert response.data['total_possible'] == 120  # 100 + 20


@pytest.mark.django_db
class TestGradingConfig:
    """Tests for grading configuration endpoints."""

    def test_get_grading_config_instructor(self, api_client, instructor, course):
        """Test instructor can get grading config."""
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/grading-config/')

        assert response.status_code == 200
        assert 'assignments_weight' in response.data
        assert 'quizzes_weight' in response.data
        assert 'participation_weight' in response.data
        # Default values
        assert float(response.data['assignments_weight']) == 50
        assert float(response.data['quizzes_weight']) == 50

    def test_get_grading_config_enrolled_student(self, api_client, student, course, enrollment):
        """Test enrolled student can get grading config."""
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/grading-config/')

        assert response.status_code == 200

    def test_get_grading_config_not_enrolled(self, api_client, student, course):
        """Test non-enrolled student cannot get grading config."""
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/grading-config/')

        assert response.status_code == 403

    def test_update_grading_config_instructor(self, api_client, instructor, course):
        """Test instructor can update grading config."""
        api_client.force_authenticate(user=instructor)
        data = {
            'assignments_weight': 60,
            'quizzes_weight': 30,
            'participation_weight': 10,
        }
        response = api_client.put(
            f'/api/courses/courses/{course.code}/grading-config/',
            data,
            format='json'
        )

        assert response.status_code == 200
        assert float(response.data['assignments_weight']) == 60
        assert float(response.data['quizzes_weight']) == 30
        assert float(response.data['participation_weight']) == 10

    def test_update_grading_config_student_forbidden(self, api_client, student, course, enrollment):
        """Test student cannot update grading config."""
        api_client.force_authenticate(user=student)
        data = {'assignments_weight': 100, 'quizzes_weight': 0, 'participation_weight': 0}
        response = api_client.put(
            f'/api/courses/courses/{course.code}/grading-config/',
            data,
            format='json'
        )

        assert response.status_code == 403

    def test_update_grading_config_invalid_weights(self, api_client, instructor, course):
        """Test that weights must sum to 100."""
        api_client.force_authenticate(user=instructor)
        data = {
            'assignments_weight': 50,
            'quizzes_weight': 30,
            'participation_weight': 10,  # Total = 90, not 100
        }
        response = api_client.put(
            f'/api/courses/courses/{course.code}/grading-config/',
            data,
            format='json'
        )

        assert response.status_code == 400


@pytest.mark.django_db
class TestStudentGradeSummary:
    """Tests for student grade summary endpoint."""

    def test_get_my_grades_enrolled_student(self, api_client, student, course, enrollment):
        """Test enrolled student can get their grade summary."""
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/my-grades/')

        assert response.status_code == 200
        assert 'assignments' in response.data
        assert 'quizzes' in response.data
        assert 'participation' in response.data
        assert 'overall' in response.data
        assert 'is_weighted' in response.data

    def test_get_my_grades_not_enrolled(self, api_client, student, course):
        """Test non-enrolled student cannot get grades."""
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/my-grades/')

        assert response.status_code == 403

    def test_my_grades_with_assignment(self, api_client, student, course, unit, enrollment):
        """Test grade summary includes assignment grades."""
        from assignments.models import Assignment, Submission, Grade

        assignment = Assignment.objects.create(
            unit=unit,
            title='Test Assignment',
            max_points=100
        )

        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            status='graded'
        )

        Grade.objects.create(
            submission=submission,
            grader=course.instructor,
            points=85
        )

        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/my-grades/')

        assert response.status_code == 200
        assert response.data['assignments']['earned'] == 85
        assert response.data['assignments']['possible'] == 100
        assert response.data['assignments']['percentage'] == 85.0

    def test_my_grades_with_quiz(self, api_client, student, course, unit, enrollment):
        """Test grade summary includes quiz grades."""
        from quizzes.models import Quiz, QuizAttempt

        quiz = Quiz.objects.create(
            unit=unit,
            title='Test Quiz',
            points=20,
            passing_score=70
        )

        QuizAttempt.objects.create(
            quiz=quiz,
            student=student,
            score=90.00,
            passed=True
        )

        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/my-grades/')

        assert response.status_code == 200
        assert response.data['quizzes']['earned'] == 18.0  # 90% of 20
        assert response.data['quizzes']['possible'] == 20
        assert response.data['quizzes']['percentage'] == 90.0

    def test_my_grades_weighted_calculation(self, api_client, student, course, unit, enrollment):
        """Test weighted grade calculation."""
        from assignments.models import Assignment, Submission, Grade
        from quizzes.models import Quiz, QuizAttempt
        from courses.models import CourseGradingConfig

        # Set up weights: 60% assignments, 40% quizzes
        CourseGradingConfig.objects.create(
            course=course,
            assignments_weight=60,
            quizzes_weight=40,
            participation_weight=0
        )

        # Assignment: 80%
        assignment = Assignment.objects.create(unit=unit, title='Test', max_points=100)
        submission = Submission.objects.create(assignment=assignment, student=student, status='graded')
        Grade.objects.create(submission=submission, grader=course.instructor, points=80)

        # Quiz: 100%
        quiz = Quiz.objects.create(unit=unit, title='Test Quiz', points=10, passing_score=70)
        QuizAttempt.objects.create(quiz=quiz, student=student, score=100.00, passed=True)

        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/my-grades/')

        assert response.status_code == 200
        # Weighted: (80 * 60 + 100 * 40) / 100 = 88
        assert response.data['overall']['percentage'] == 88.0
        assert response.data['is_weighted'] is True


@pytest.mark.django_db
class TestPermissionBoundaries:
    """Phase 14: bare ViewSet scoping and cross-course permission hardening."""

    @pytest.fixture
    def other_instructor(self):
        return User.objects.create_user(
            email='other.instructor@test.com',
            password='testpass123',
            first_name='Other',
            last_name='Instructor',
            is_instructor=True
        )

    @pytest.fixture
    def other_course(self, other_instructor):
        return Course.objects.create(
            code='VGD201',
            title='Other Course',
            description='A course the student is not enrolled in.',
            instructor=other_instructor
        )

    @pytest.fixture
    def other_unit(self, other_course):
        return Unit.objects.create(course=other_course, title='Other Unit', order=1)

    @pytest.fixture
    def other_lesson(self, other_unit):
        return Lesson.objects.create(
            unit=other_unit, title='Other Lesson', content='Secret content', order=1
        )

    # --- Bare ViewSet creates are forbidden ---

    def test_student_cannot_create_unit_via_bare_endpoint(self, api_client, student, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.post('/api/courses/units/', {'title': 'Injected Unit'})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_student_cannot_create_lesson_via_bare_endpoint(self, api_client, student, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.post('/api/courses/lessons/', {'title': 'Injected', 'content': 'x'})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # --- Bare ViewSet lists are scoped to accessible courses ---

    def test_units_list_scoped_to_accessible_courses(self, api_client, student, unit, enrollment, other_unit):
        api_client.force_authenticate(user=student)
        response = api_client.get('/api/courses/units/')
        assert response.status_code == status.HTTP_200_OK
        ids = [u['id'] for u in response.data]
        assert unit.id in ids
        assert other_unit.id not in ids

    def test_lessons_list_scoped_to_accessible_courses(self, api_client, student, lesson, enrollment, other_lesson):
        api_client.force_authenticate(user=student)
        response = api_client.get('/api/courses/lessons/')
        assert response.status_code == status.HTTP_200_OK
        ids = [l['id'] for l in response.data]
        assert lesson.id in ids
        assert other_lesson.id not in ids

    def test_retrieve_other_course_unit_forbidden(self, api_client, student, enrollment, other_unit):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/units/{other_unit.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data

    def test_retrieve_other_course_lesson_forbidden(self, api_client, student, enrollment, other_lesson):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/lessons/{other_lesson.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data

    # --- Cross-instructor writes are forbidden ---

    def test_other_instructor_cannot_update_unit(self, api_client, other_instructor, unit):
        api_client.force_authenticate(user=other_instructor)
        response = api_client.patch(f'/api/courses/units/{unit.id}/', {'title': 'Hijacked'})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        unit.refresh_from_db()
        assert unit.title != 'Hijacked'

    def test_other_instructor_cannot_delete_lesson(self, api_client, other_instructor, lesson):
        api_client.force_authenticate(user=other_instructor)
        response = api_client.delete(f'/api/courses/lessons/{lesson.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Lesson.objects.filter(id=lesson.id).exists()

    # --- Announcement list/retrieve scoping ---

    def test_announcements_list_scoped_to_accessible_courses(
        self, api_client, student, course, instructor, enrollment, other_course, other_instructor
    ):
        mine = Announcement.objects.create(
            course=course, author=instructor, title='Mine', content='Visible'
        )
        theirs = Announcement.objects.create(
            course=other_course, author=other_instructor, title='Theirs', content='Hidden'
        )
        api_client.force_authenticate(user=student)
        response = api_client.get('/api/courses/announcements/')
        assert response.status_code == status.HTTP_200_OK
        ids = [a['id'] for a in response.data]
        assert mine.id in ids
        assert theirs.id not in ids

    def test_retrieve_other_course_announcement_forbidden(
        self, api_client, student, enrollment, other_course, other_instructor
    ):
        theirs = Announcement.objects.create(
            course=other_course, author=other_instructor, title='Theirs', content='Hidden'
        )
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/announcements/{theirs.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data

    # --- Cross-instructor access to instructor-only course endpoints ---

    def test_gradebook_other_instructor_forbidden(self, api_client, other_instructor, course):
        api_client.force_authenticate(user=other_instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data

    def test_roster_other_instructor_forbidden(self, api_client, other_instructor, course):
        api_client.force_authenticate(user=other_instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/students/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data

    def test_course_units_other_instructor_forbidden(self, api_client, other_instructor, course, unit):
        api_client.force_authenticate(user=other_instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/units/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data

    # --- Activity endpoint now returns 403 (was 404) ---

    def test_update_activity_not_enrolled_forbidden(self, api_client, student, course):
        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/courses/courses/{course.code}/activity/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data


# ==================== Phase 16: Reorder (units, lessons, cross-unit) ====================

@pytest.mark.django_db
class TestUnitReorder:
    @pytest.fixture
    def units(self, course):
        return [
            Unit.objects.create(course=course, title=f'Unit {i}', order=i)
            for i in range(1, 5)
        ]

    def test_reorder_unit_down(self, api_client, instructor, course, units):
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(f'/api/courses/units/{units[0].id}/reorder/', {'order': 3})
        assert response.status_code == status.HTTP_200_OK
        titles = list(
            Unit.objects.filter(course=course).order_by('order').values_list('title', flat=True)
        )
        assert titles == ['Unit 2', 'Unit 3', 'Unit 1', 'Unit 4']
        orders = list(
            Unit.objects.filter(course=course).order_by('order').values_list('order', flat=True)
        )
        assert orders == [1, 2, 3, 4]

    def test_reorder_unit_up(self, api_client, instructor, course, units):
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(f'/api/courses/units/{units[3].id}/reorder/', {'order': 1})
        assert response.status_code == status.HTTP_200_OK
        titles = list(
            Unit.objects.filter(course=course).order_by('order').values_list('title', flat=True)
        )
        assert titles == ['Unit 4', 'Unit 1', 'Unit 2', 'Unit 3']

    def test_reorder_unit_student_forbidden(self, api_client, student, enrollment, units):
        api_client.force_authenticate(user=student)
        response = api_client.patch(f'/api/courses/units/{units[0].id}/reorder/', {'order': 2})
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestLessonReorder:
    @pytest.fixture
    def unit_b(self, course):
        return Unit.objects.create(course=course, title='Unit B', order=2)

    @pytest.fixture
    def lessons_a(self, unit):
        return [
            Lesson.objects.create(unit=unit, title=f'A{i}', order=i)
            for i in range(1, 4)
        ]

    @pytest.fixture
    def lessons_b(self, unit_b):
        return [
            Lesson.objects.create(unit=unit_b, title=f'B{i}', order=i)
            for i in range(1, 3)
        ]

    @pytest.fixture
    def other_instructor(self):
        return User.objects.create_user(
            email='other-instructor@test.com',
            password='testpass123',
            is_instructor=True,
        )

    @pytest.fixture
    def other_course_unit(self, other_instructor):
        other_course = Course.objects.create(
            code='OTHER101',
            title='Other Course',
            instructor=other_instructor,
        )
        return Unit.objects.create(course=other_course, title='Other Unit', order=1)

    def _titles(self, unit):
        return list(
            Lesson.objects.filter(unit=unit).order_by('order').values_list('title', flat=True)
        )

    def _orders(self, unit):
        return list(
            Lesson.objects.filter(unit=unit).order_by('order').values_list('order', flat=True)
        )

    def test_reorder_within_unit(self, api_client, instructor, unit, lessons_a):
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(
            f'/api/courses/lessons/{lessons_a[2].id}/reorder/', {'order': 1}
        )
        assert response.status_code == status.HTTP_200_OK
        assert self._titles(unit) == ['A3', 'A1', 'A2']
        assert self._orders(unit) == [1, 2, 3]

    def test_cross_unit_move_happy_path(
        self, api_client, instructor, unit, unit_b, lessons_a, lessons_b
    ):
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(
            f'/api/courses/lessons/{lessons_a[1].id}/reorder/',
            {'order': 2, 'unit': unit_b.id},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['unit'] == unit_b.id
        assert response.data['order'] == 2
        assert self._titles(unit_b) == ['B1', 'A2', 'B2']
        assert self._titles(unit) == ['A1', 'A3']

    def test_cross_unit_move_compacts_orders_in_both_units(
        self, api_client, instructor, unit, unit_b, lessons_a, lessons_b
    ):
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(
            f'/api/courses/lessons/{lessons_a[0].id}/reorder/',
            {'order': 1, 'unit': unit_b.id},
        )
        assert response.status_code == status.HTTP_200_OK
        assert self._orders(unit) == [1, 2]
        assert self._orders(unit_b) == [1, 2, 3]

    def test_cross_unit_move_to_other_course_rejected(
        self, api_client, instructor, lessons_a, other_course_unit
    ):
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(
            f'/api/courses/lessons/{lessons_a[0].id}/reorder/',
            {'order': 1, 'unit': other_course_unit.id},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_reorder_student_forbidden(
        self, api_client, student, enrollment, unit_b, lessons_a
    ):
        api_client.force_authenticate(user=student)
        response = api_client.patch(
            f'/api/courses/lessons/{lessons_a[0].id}/reorder/',
            {'order': 1, 'unit': unit_b.id},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_reorder_anonymous_unauthorized(self, api_client, lessons_a):
        response = api_client.patch(
            f'/api/courses/lessons/{lessons_a[0].id}/reorder/', {'order': 2}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
