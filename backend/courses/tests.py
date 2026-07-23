from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from accounts.models import User
from .models import (
    Course, Unit, Lesson, Enrollment, LessonProgress, Announcement,
    LessonSection, LessonQuestion, LessonQuestionChoice, LessonQuizAttempt,
    LessonAttachment,
)
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
        title='Intro to Programming',
        description='Learn the basics of programming.',
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
            title='Advanced Programming',
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
def quiz(unit):
    from quizzes.models import Quiz
    return Quiz.objects.create(
        unit=unit,
        title='Test Quiz',
        points=100,
        passing_score=70
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

    def test_gradebook_returns_structure(self, api_client, instructor, course, unit, quiz, student, enrollment):
        """Gradebook returns the quizzes + completion matrix structure."""
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')
        assert response.status_code == status.HTTP_200_OK
        assert 'course' in response.data
        assert 'gradebook_items' in response.data
        assert 'students' in response.data
        assert response.data['course']['code'] == course.code
        # Items are quizzes only
        assert all(i['type'] == 'quiz' for i in response.data['gradebook_items'])
        # Each student row has completion and weighted-total columns
        student_data = response.data['students'][0]
        assert 'participation_percentage' in student_data
        assert 'quizzes_percentage' in student_data
        assert 'percentage' in student_data
        assert 'letter_grade' in student_data

    def test_gradebook_shows_students(self, api_client, instructor, course, unit, student, enrollment):
        """Gradebook shows enrolled students."""
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')
        assert len(response.data['students']) == 1
        assert response.data['students'][0]['email'] == student.email

    def test_gradebook_matrix_cells(self, api_client, instructor, course, unit, quiz, student, enrollment):
        """A quiz cell is either a score (best attempt) or empty."""
        from quizzes.models import QuizAttempt

        QuizAttempt.objects.create(quiz=quiz, student=student, score=85.00, passed=True)

        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')
        student_data = response.data['students'][0]
        cell = student_data['grades'][0]
        assert cell['item_id'] == quiz.id
        assert cell['item_type'] == 'quiz'
        assert cell['status'] == 'graded'
        assert cell['points_earned'] == 85.0
        assert student_data['quizzes_percentage'] == 85.0

    def test_gradebook_empty_cell_without_attempt(self, api_client, instructor, course, unit, quiz, student, enrollment):
        """No attempt means an empty cell, not a missing/late status."""
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')
        cell = response.data['students'][0]['grades'][0]
        assert cell['status'] == 'not_started'
        assert cell['points_earned'] is None

    def test_gradebook_completion_column(self, api_client, instructor, course, unit, quiz, lesson, student, enrollment):
        """Participation column reflects lesson completion percentage."""
        Lesson.objects.create(unit=unit, title='Second Lesson', order=2)
        LessonProgress.objects.create(user=student, lesson=lesson, completed=True)

        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')
        student_data = response.data['students'][0]
        assert student_data['participation_percentage'] == 50.0

    def test_gradebook_weighted_total(self, api_client, instructor, course, unit, quiz, lesson, student, enrollment):
        """Weighted total combines quiz % and completion % via config weights."""
        from quizzes.models import QuizAttempt
        from courses.models import CourseGradingConfig

        CourseGradingConfig.objects.create(
            course=course, quizzes_weight=60, participation_weight=40
        )
        # Quiz: 80%
        QuizAttempt.objects.create(quiz=quiz, student=student, score=80.00, passed=True)
        # Completion: 100% (only lesson completed)
        LessonProgress.objects.create(user=student, lesson=lesson, completed=True)

        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')
        student_data = response.data['students'][0]
        # (80 * 60 + 100 * 40) / 100 = 88
        assert student_data['percentage'] == 88.0
        assert student_data['letter_grade'] == 'B'
        assert response.data['grading_config'] == {
            'quizzes_weight': 60.0,
            'participation_weight': 40.0,
        }

    def test_gradebook_export_csv(self, api_client, instructor, course, unit, quiz, student, enrollment):
        """Gradebook export returns CSV with quiz + completion columns."""
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/export/')
        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'text/csv'
        assert f'{course.code}_gradebook.csv' in response['Content-Disposition']

        header = response.content.decode().splitlines()[0]
        assert 'Student Name' in header
        assert 'Email' in header
        assert 'Test Quiz (100)' in header
        assert 'Lesson Completion %' in header
        assert 'Weighted %' in header
        assert 'Letter Grade' in header
        assert 'assignment' not in header.lower()

    def test_gradebook_export_values(self, api_client, instructor, course, unit, quiz, lesson, student, enrollment):
        """CSV row carries the same numbers as the gradebook matrix."""
        from quizzes.models import QuizAttempt

        QuizAttempt.objects.create(quiz=quiz, student=student, score=80.00, passed=True)
        LessonProgress.objects.create(user=student, lesson=lesson, completed=True)

        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/export/')
        row = response.content.decode().splitlines()[1]
        # quiz score, quiz %, completion %, weighted % (default 50/50 → 90), letter
        assert '80.0' in row
        assert '100.0' in row
        assert '90.0' in row
        assert row.strip().endswith('A')

    def test_gradebook_export_student_forbidden(self, api_client, student, course, enrollment):
        """Students cannot export gradebook."""
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/export/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_gradebook_multiple_students(self, api_client, instructor, course, unit, quiz, student, second_student, enrollment):
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
        """Removing student preserves their quiz attempts (grades)."""
        from quizzes.models import Quiz, QuizAttempt

        quiz = Quiz.objects.create(unit=unit, title='Test', points=10, passing_score=70)
        attempt = QuizAttempt.objects.create(quiz=quiz, student=student, score=90.00, passed=True)

        api_client.force_authenticate(user=instructor)
        api_client.delete(f'/api/courses/courses/{course.code}/students/{enrollment.id}/')

        # Quiz attempt should still exist
        assert QuizAttempt.objects.filter(pk=attempt.pk).exists()

    def test_student_cannot_remove_others(self, api_client, student, course, enrollment):
        """Students cannot remove other students."""
        api_client.force_authenticate(user=student)
        response = api_client.delete(f'/api/courses/courses/{course.code}/students/{enrollment.id}/')
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

    def test_gradebook_total_is_quiz_points(self, api_client, instructor, student, course, unit, enrollment):
        """Total possible points is the sum of quiz points."""
        from quizzes.models import Quiz

        Quiz.objects.create(
            unit=unit,
            title='Test Quiz',
            points=20,
            passing_score=70
        )
        Quiz.objects.create(
            unit=unit,
            title='Second Quiz',
            points=30,
            passing_score=70
        )

        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/gradebook/')

        assert response.data['total_possible'] == 50  # 20 + 30


@pytest.mark.django_db
class TestGradingConfig:
    """Tests for grading configuration endpoints."""

    def test_get_grading_config_instructor(self, api_client, instructor, course):
        """Test instructor can get grading config."""
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/courses/{course.code}/grading-config/')

        assert response.status_code == 200
        assert set(response.data.keys()) == {'quizzes_weight', 'participation_weight'}
        # Default values
        assert float(response.data['quizzes_weight']) == 50
        assert float(response.data['participation_weight']) == 50

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
            'quizzes_weight': 60,
            'participation_weight': 40,
        }
        response = api_client.put(
            f'/api/courses/courses/{course.code}/grading-config/',
            data,
            format='json'
        )

        assert response.status_code == 200
        assert float(response.data['quizzes_weight']) == 60
        assert float(response.data['participation_weight']) == 40

    def test_update_grading_config_student_forbidden(self, api_client, student, course, enrollment):
        """Test student cannot update grading config."""
        api_client.force_authenticate(user=student)
        data = {'quizzes_weight': 100, 'participation_weight': 0}
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
            'quizzes_weight': 50,
            'participation_weight': 40,  # Total = 90, not 100
        }
        response = api_client.put(
            f'/api/courses/courses/{course.code}/grading-config/',
            data,
            format='json'
        )

        assert response.status_code == 400

    def test_partial_update_validates_against_existing_weight(self, api_client, instructor, course):
        """Updating one weight alone must still satisfy the sum-to-100 rule."""
        api_client.force_authenticate(user=instructor)
        response = api_client.put(
            f'/api/courses/courses/{course.code}/grading-config/',
            {'quizzes_weight': 70},  # existing participation 50 → total 120
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
        assert 'assignments' not in response.data
        assert 'quizzes' in response.data
        assert 'participation' in response.data
        assert 'overall' in response.data
        assert 'is_weighted' in response.data

    def test_get_my_grades_not_enrolled(self, api_client, student, course):
        """Test non-enrolled student cannot get grades."""
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/my-grades/')

        assert response.status_code == 403

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

    def test_my_grades_weighted_calculation(self, api_client, student, course, unit, lesson, enrollment):
        """Test weighted grade calculation from quizzes + participation."""
        from quizzes.models import Quiz, QuizAttempt
        from courses.models import CourseGradingConfig

        # Set up weights: 60% quizzes, 40% participation
        CourseGradingConfig.objects.create(
            course=course,
            quizzes_weight=60,
            participation_weight=40
        )

        # Quiz: 80%
        quiz = Quiz.objects.create(unit=unit, title='Test Quiz', points=10, passing_score=70)
        QuizAttempt.objects.create(quiz=quiz, student=student, score=80.00, passed=True)

        # Participation: 100% (single lesson completed)
        LessonProgress.objects.create(user=student, lesson=lesson, completed=True)

        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/my-grades/')

        assert response.status_code == 200
        # Weighted: (80 * 60 + 100 * 40) / 100 = 88
        assert response.data['overall']['percentage'] == 88.0
        assert response.data['overall']['letter_grade'] == 'B'
        assert response.data['is_weighted'] is True

    def test_my_grades_items_are_quizzes_only(self, api_client, student, course, unit, enrollment):
        """grade_items contains only quiz entries."""
        from quizzes.models import Quiz

        Quiz.objects.create(unit=unit, title='Test Quiz', points=10, passing_score=70)

        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/courses/{course.code}/my-grades/')

        assert response.status_code == 200
        assert len(response.data['grade_items']) == 1
        assert all(item['type'] == 'quiz' for item in response.data['grade_items'])


@pytest.mark.django_db
class TestGradingConfigWeightMigration:
    """0014_two_weight_grading_config rescales surviving weights to sum 100."""

    def _run_migration(self):
        from importlib import import_module

        from django.apps import apps as django_apps

        migration = import_module('courses.migrations.0014_two_weight_grading_config')
        migration.redistribute_weights(django_apps, None)

    def test_redistributes_proportionally(self, course):
        from courses.models import CourseGradingConfig

        # Old 50/40/10 (assignments/quizzes/participation) row arrives with
        # quizzes=40, participation=10 once assignments_weight is dropped.
        CourseGradingConfig.objects.create(
            course=course, quizzes_weight=40, participation_weight=10
        )

        self._run_migration()

        config = CourseGradingConfig.objects.get(course=course)
        assert float(config.quizzes_weight) == 80.0
        assert float(config.participation_weight) == 20.0

    def test_all_assignments_config_becomes_fifty_fifty(self, course):
        from courses.models import CourseGradingConfig

        # A config that was 100% assignments has both surviving weights at 0.
        CourseGradingConfig.objects.create(
            course=course, quizzes_weight=0, participation_weight=0
        )

        self._run_migration()

        config = CourseGradingConfig.objects.get(course=course)
        assert float(config.quizzes_weight) == 50.0
        assert float(config.participation_weight) == 50.0


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


# ---------------------------------------------------------------------------
# Phase 23: Learning-mode pagination + comprehension-quiz gating
# ---------------------------------------------------------------------------


def _add_comprehension_quiz(lesson, count=2):
    """Attach `count` comprehension questions (one correct choice each).

    Phase 54: also flips `requires_quiz` on so the questions actually gate
    completion (the default is off — questions are optional practice unless the
    lesson opts in). These helpers back tests of the *gated* flow.
    """
    questions = []
    for i in range(1, count + 1):
        question = LessonQuestion.objects.create(
            lesson=lesson, text=f'Question {i}?', order=i
        )
        LessonQuestionChoice.objects.create(
            question=question, text='Correct', is_correct=True, order=1
        )
        LessonQuestionChoice.objects.create(
            question=question, text='Wrong', is_correct=False, order=2
        )
        questions.append(question)
    if not lesson.requires_quiz:
        lesson.requires_quiz = True
        lesson.save(update_fields=['requires_quiz'])
    return questions


@pytest.mark.django_db
class TestLessonSections:
    def test_lesson_detail_returns_sections_in_order(
        self, api_client, student, lesson, enrollment
    ):
        # Create sections out of order; serializer should sort by `order`.
        LessonSection.objects.create(lesson=lesson, title='Third', order=2)
        LessonSection.objects.create(lesson=lesson, title='First', order=0)
        LessonSection.objects.create(lesson=lesson, title='Second', order=1)

        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/lessons/{lesson.id}/')

        assert response.status_code == status.HTTP_200_OK
        orders = [s['order'] for s in response.data['sections']]
        titles = [s['title'] for s in response.data['sections']]
        assert orders == [0, 1, 2]
        assert titles == ['First', 'Second', 'Third']

    def test_section_write_requires_course_owner(
        self, api_client, student, lesson, enrollment
    ):
        """A non-owner enrolled student cannot create or reorder sections."""
        section = LessonSection.objects.create(lesson=lesson, title='Only', order=0)
        api_client.force_authenticate(user=student)

        create_resp = api_client.post(
            f'/api/courses/lessons/{lesson.id}/sections/',
            {'title': 'Hacked', 'content': 'nope', 'order': 1},
        )
        assert create_resp.status_code == status.HTTP_403_FORBIDDEN

        reorder_resp = api_client.post(
            f'/api/courses/lessons/{lesson.id}/sections/reorder/',
            {'section_ids': [section.id]},
            format='json',
        )
        assert reorder_resp.status_code == status.HTTP_403_FORBIDDEN

    # ---- Bulk create (paste-to-split, Phase 29) ----

    def test_bulk_create_appends_from_empty(self, api_client, instructor, lesson):
        """Instructor bulk-creates 3 sections on a lesson with 0 existing → 201, order 0,1,2."""
        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/courses/lessons/{lesson.id}/sections/bulk/',
            {'sections': [
                {'title': 'One', 'content': 'a'},
                {'title': 'Two', 'content': 'b'},
                {'title': 'Three', 'content': 'c'},
            ]},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) == 3
        assert [s['order'] for s in response.data] == [0, 1, 2]
        assert [s['title'] for s in response.data] == ['One', 'Two', 'Three']

    def test_bulk_create_appends_after_existing(self, api_client, instructor, lesson):
        """New sections append after existing ones without unique_together collision."""
        LessonSection.objects.create(lesson=lesson, title='Existing 0', order=0)
        LessonSection.objects.create(lesson=lesson, title='Existing 1', order=1)

        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/courses/lessons/{lesson.id}/sections/bulk/',
            {'sections': [
                {'title': 'New A', 'content': 'a'},
                {'title': 'New B', 'content': 'b'},
            ]},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert [s['order'] for s in response.data] == [2, 3]
        assert lesson.sections.count() == 4

    def test_bulk_create_is_atomic_on_invalid_child(self, api_client, instructor, lesson):
        """A batch with one invalid section → 400 and zero sections created (rollback)."""
        before = lesson.sections.count()
        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/courses/lessons/{lesson.id}/sections/bulk/',
            {'sections': [
                {'title': 'Valid', 'content': 'ok'},
                {'title': 'Bad', 'content': 'x', 'video_type': 'not_a_real_choice'},
            ]},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert lesson.sections.count() == before

    def test_bulk_create_empty_list_rejected(self, api_client, instructor, lesson):
        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/courses/lessons/{lesson.id}/sections/bulk/',
            {'sections': []},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert lesson.sections.count() == 0

    def test_bulk_create_student_forbidden(self, api_client, student, lesson, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.post(
            f'/api/courses/lessons/{lesson.id}/sections/bulk/',
            {'sections': [{'title': 'Nope', 'content': 'x'}]},
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert lesson.sections.count() == 0

    def test_bulk_create_unauthenticated_rejected(self, api_client, lesson):
        response = api_client.post(
            f'/api/courses/lessons/{lesson.id}/sections/bulk/',
            {'sections': [{'title': 'Nope', 'content': 'x'}]},
            format='json',
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert lesson.sections.count() == 0

    def test_bulk_create_wrong_course_instructor_forbidden(self, api_client, lesson):
        """An instructor who does not own this course cannot bulk-create sections."""
        other = User.objects.create_user(
            email='other-instructor@test.com',
            password='testpass123',
            first_name='Other',
            last_name='Instructor',
            is_instructor=True,
        )
        api_client.force_authenticate(user=other)
        response = api_client.post(
            f'/api/courses/lessons/{lesson.id}/sections/bulk/',
            {'sections': [{'title': 'Nope', 'content': 'x'}]},
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert lesson.sections.count() == 0


@pytest.mark.django_db
class TestLessonCompletionGating:
    def test_complete_blocked_until_comprehension_quiz_passed(
        self, api_client, student, lesson, enrollment
    ):
        questions = _add_comprehension_quiz(lesson, count=2)
        api_client.force_authenticate(user=student)

        # Blocked while no passing attempt exists.
        blocked = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/progress/', {'completed': True}
        )
        assert blocked.status_code == status.HTTP_400_BAD_REQUEST

        # Record a passing attempt.
        LessonQuizAttempt.objects.create(
            user=student,
            lesson=lesson,
            attempt_number=1,
            score=len(questions),
            total_questions=len(questions),
            passed=True,
        )

        allowed = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/progress/', {'completed': True}
        )
        assert allowed.status_code == status.HTTP_200_OK
        assert allowed.data['completed'] is True

    def test_complete_allowed_when_no_quiz(
        self, api_client, student, lesson, enrollment
    ):
        """A lesson with no questions completes directly."""
        api_client.force_authenticate(user=student)
        response = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/progress/', {'completed': True}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['completed'] is True

    def test_questions_do_not_gate_when_requires_quiz_off(
        self, api_client, student, lesson, enrollment
    ):
        """Phase 54: questions are optional practice unless `requires_quiz` is on.
        With the toggle off, the lesson completes without any passing attempt."""
        _add_comprehension_quiz(lesson, count=2)
        lesson.requires_quiz = False  # opt out of gating
        lesson.save(update_fields=['requires_quiz'])

        api_client.force_authenticate(user=student)
        response = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/progress/', {'completed': True}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['completed'] is True

    def test_requires_quiz_on_with_no_questions_does_not_softlock(
        self, api_client, student, lesson, enrollment
    ):
        """`requires_quiz=True` but zero questions must not block completion —
        there is nothing to pass."""
        lesson.requires_quiz = True
        lesson.save(update_fields=['requires_quiz'])

        api_client.force_authenticate(user=student)
        response = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/progress/', {'completed': True}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['completed'] is True

    def test_toggling_requires_quiz_off_unblocks_completion(
        self, api_client, student, instructor, lesson, enrollment
    ):
        """A student blocked by the gate can complete once the instructor turns
        the requirement off."""
        _add_comprehension_quiz(lesson, count=2)  # requires_quiz on
        api_client.force_authenticate(user=student)
        blocked = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/progress/', {'completed': True}
        )
        assert blocked.status_code == status.HTTP_400_BAD_REQUEST

        lesson.requires_quiz = False
        lesson.save(update_fields=['requires_quiz'])

        allowed = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/progress/', {'completed': True}
        )
        assert allowed.status_code == status.HTTP_200_OK
        assert allowed.data['completed'] is True

    def test_status_can_complete_agrees_with_gate(
        self, api_client, student, lesson, enrollment
    ):
        """The lesson-questions-status endpoint's `can_complete_lesson` must match
        the real gate: false until a passing attempt exists when gated."""
        questions = _add_comprehension_quiz(lesson, count=2)  # requires_quiz on
        api_client.force_authenticate(user=student)

        status_resp = api_client.get(
            f'/api/courses/lessons/{lesson.id}/questions-status/'
        )
        assert status_resp.status_code == status.HTTP_200_OK
        assert status_resp.data['requires_quiz'] is True
        assert status_resp.data['can_complete_lesson'] is False

        LessonQuizAttempt.objects.create(
            user=student, lesson=lesson, attempt_number=1,
            score=len(questions), total_questions=len(questions), passed=True,
        )
        status_resp2 = api_client.get(
            f'/api/courses/lessons/{lesson.id}/questions-status/'
        )
        assert status_resp2.data['can_complete_lesson'] is True


@pytest.mark.django_db
class TestRequiresQuizMigration:
    """Phase 54: `0020` seeds `requires_quiz` from existing questions and clears
    the retired `required_quiz` FK."""

    def test_seed_and_clear(self, instructor, course, unit):
        import importlib
        from django.apps import apps as global_apps
        migration = importlib.import_module(
            'courses.migrations.0020_lesson_requires_quiz'
        )
        seed_requires_quiz_and_clear_required_quiz = (
            migration.seed_requires_quiz_and_clear_required_quiz
        )
        from quizzes.models import Quiz

        quiz = Quiz.objects.create(unit=unit, title='Legacy Gate')

        # Lesson with questions → should become requires_quiz=True.
        with_q = Lesson.objects.create(unit=unit, title='Has Q', order=0)
        LessonQuestion.objects.create(lesson=with_q, text='Q?', order=1)

        # Lesson with no questions → stays False.
        no_q = Lesson.objects.create(unit=unit, title='No Q', order=1)

        # Lesson carrying a retired required_quiz FK → cleared.
        with_fk = Lesson.objects.create(
            unit=unit, title='Has FK', order=2, required_quiz=quiz
        )

        seed_requires_quiz_and_clear_required_quiz(global_apps, None)

        with_q.refresh_from_db()
        no_q.refresh_from_db()
        with_fk.refresh_from_db()
        assert with_q.requires_quiz is True
        assert no_q.requires_quiz is False
        assert with_fk.required_quiz_id is None


# ---------------------------------------------------------------------------
# Phase 31: Instructor analytics dashboard
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInstructorAnalytics:
    ENDPOINTS = ['overview', 'quizzes', 'students', 'activity']

    @pytest.fixture
    def other_instructor(self):
        return User.objects.create_user(
            email='other_instructor@test.com',
            password='testpass123',
            first_name='Other',
            last_name='Instructor',
            is_instructor=True
        )

    def _url(self, course, endpoint):
        return f'/api/courses/courses/{course.code}/analytics/{endpoint}/'

    # ---- Permission boundaries (each endpoint) ----

    @pytest.mark.parametrize('endpoint', ENDPOINTS)
    def test_course_instructor_allowed(self, api_client, instructor, course, endpoint):
        api_client.force_authenticate(user=instructor)
        response = api_client.get(self._url(course, endpoint))
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.parametrize('endpoint', ENDPOINTS)
    def test_other_instructor_forbidden(self, api_client, other_instructor, course, endpoint):
        api_client.force_authenticate(user=other_instructor)
        response = api_client.get(self._url(course, endpoint))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize('endpoint', ENDPOINTS)
    def test_enrolled_student_forbidden(self, api_client, student, course, enrollment, endpoint):
        api_client.force_authenticate(user=student)
        response = api_client.get(self._url(course, endpoint))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize('endpoint', ENDPOINTS)
    def test_anonymous_unauthorized(self, api_client, course, endpoint):
        response = api_client.get(self._url(course, endpoint))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ---- Overview ----

    def test_overview_metrics(self, api_client, instructor, course, unit, quiz,
                              lesson, student, second_student, enrollment):
        """Known averages from seeded data; stale student not counted active."""
        from datetime import timedelta
        from django.utils import timezone
        from quizzes.models import QuizAttempt

        Lesson.objects.create(unit=unit, title='Second Lesson', order=2)
        stale = Enrollment.objects.create(user=second_student, course=course)
        Enrollment.objects.filter(id=stale.id).update(
            last_activity_at=timezone.now() - timedelta(days=10)
        )

        # student: 1/2 lessons (50%), best quiz 80% -> weighted (50/50) = 65.0
        # second_student: 0% progress, no quiz -> weighted = 0.0
        LessonProgress.objects.create(
            user=student, lesson=lesson, completed=True,
            completed_at=timezone.now()
        )
        QuizAttempt.objects.create(quiz=quiz, student=student, score=60.00, passed=False)
        QuizAttempt.objects.create(quiz=quiz, student=student, score=80.00, passed=True)

        api_client.force_authenticate(user=instructor)
        response = api_client.get(self._url(course, 'overview'))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['student_count'] == 2
        assert response.data['avg_progress_percentage'] == 25.0
        assert response.data['avg_grade_percentage'] == 32.5
        # student has no last_activity_at -> falls back to enrolled_at (fresh)
        assert response.data['active_last_7_days'] == 1

    def test_overview_zero_students(self, api_client, instructor, course):
        """Zero enrollments: zeroed counts, null averages, still 200."""
        api_client.force_authenticate(user=instructor)
        response = api_client.get(self._url(course, 'overview'))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['student_count'] == 0
        assert response.data['avg_progress_percentage'] is None
        assert response.data['avg_grade_percentage'] is None
        assert response.data['active_last_7_days'] == 0

    # ---- Unit quizzes ----

    def test_unit_quiz_metrics(self, api_client, instructor, course, unit, quiz,
                               student, second_student, enrollment):
        """Best-attempt avg, pass/completion denominators, worst-first order."""
        from quizzes.models import Quiz, QuizAttempt

        Enrollment.objects.create(user=second_student, course=course)
        # quiz: student best 80 (passed after a 60 fail), second_student 40 fail
        QuizAttempt.objects.create(quiz=quiz, student=student, score=60.00, passed=False)
        QuizAttempt.objects.create(quiz=quiz, student=student, score=80.00, passed=True)
        QuizAttempt.objects.create(quiz=quiz, student=second_student, score=40.00, passed=False)
        # better_quiz: one 90 -> higher avg, sorts after quiz
        better_quiz = Quiz.objects.create(unit=unit, title='Better Quiz', points=50, passing_score=70)
        QuizAttempt.objects.create(quiz=better_quiz, student=student, score=90.00, passed=True)
        # untouched quiz: no attempts -> null metrics, sorts last
        untouched = Quiz.objects.create(unit=unit, title='Untouched Quiz', points=10, passing_score=70)

        api_client.force_authenticate(user=instructor)
        response = api_client.get(self._url(course, 'quizzes'))
        rows = response.data['unit_quizzes']
        assert [r['title'] for r in rows] == ['Test Quiz', 'Better Quiz', 'Untouched Quiz']

        worst = rows[0]
        assert worst['avg_score'] == 60.0          # (80 + 40) / 2
        assert worst['pass_rate'] == 50.0          # 1 of 2 attempters passed
        assert worst['completion_rate'] == 100.0   # 2 of 2 enrolled attempted
        assert worst['passing_score'] == 70

        untouched_row = rows[2]
        assert untouched_row['avg_score'] is None
        assert untouched_row['pass_rate'] is None
        assert untouched_row['completion_rate'] == 0.0

    def test_quizzes_zero_quizzes(self, api_client, instructor, course, student, enrollment):
        """Course with no quizzes and no lesson checks: empty lists, 200."""
        api_client.force_authenticate(user=instructor)
        response = api_client.get(self._url(course, 'quizzes'))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['unit_quizzes'] == []
        assert response.data['lesson_checks'] == []

    # ---- Lesson checks ----

    def test_lesson_check_metrics(self, api_client, instructor, course, unit,
                                  lesson, student, second_student, enrollment):
        """Stuck student counted; avg uses first passing attempt; no-question lesson excluded."""
        from django.utils import timezone

        _add_comprehension_quiz(lesson, count=2)
        Lesson.objects.create(unit=unit, title='No Questions Lesson', order=2)
        Enrollment.objects.create(user=second_student, course=course)

        now = timezone.now()
        # student: fails once, passes on attempt 2 (then retakes -- ignored)
        LessonQuizAttempt.objects.create(
            user=student, lesson=lesson, attempt_number=1,
            score=1, total_questions=2, passed=False, completed_at=now)
        LessonQuizAttempt.objects.create(
            user=student, lesson=lesson, attempt_number=2,
            score=2, total_questions=2, passed=True, completed_at=now)
        LessonQuizAttempt.objects.create(
            user=student, lesson=lesson, attempt_number=3,
            score=2, total_questions=2, passed=True, completed_at=now)
        # second_student: attempted, never passed -> stuck
        LessonQuizAttempt.objects.create(
            user=second_student, lesson=lesson, attempt_number=1,
            score=0, total_questions=2, passed=False, completed_at=now)

        api_client.force_authenticate(user=instructor)
        response = api_client.get(self._url(course, 'quizzes'))
        checks = response.data['lesson_checks']
        assert len(checks) == 1  # lesson without questions excluded
        row = checks[0]
        assert row['title'] == lesson.title
        assert row['attempted_count'] == 2
        assert row['passed_count'] == 1
        assert row['stuck_count'] == 1
        assert row['avg_attempts_to_pass'] == 2.0

    # ---- Students ----

    def test_students_at_risk_low_progress(self, api_client, instructor, course,
                                           lesson, student, enrollment):
        """Progress < 50% flags at-risk even with fresh activity."""
        enrollment.update_activity()
        api_client.force_authenticate(user=instructor)
        response = api_client.get(self._url(course, 'students'))
        row = response.data['students'][0]
        assert row['progress_percentage'] == 0
        assert row['at_risk'] is True

    def test_students_at_risk_inactive(self, api_client, instructor, course,
                                       lesson, student, enrollment):
        """100% progress but 8+ days inactive still flags at-risk."""
        from datetime import timedelta
        from django.utils import timezone

        LessonProgress.objects.create(
            user=student, lesson=lesson, completed=True,
            completed_at=timezone.now()
        )
        Enrollment.objects.filter(id=enrollment.id).update(
            last_activity_at=timezone.now() - timedelta(days=8)
        )
        api_client.force_authenticate(user=instructor)
        response = api_client.get(self._url(course, 'students'))
        row = response.data['students'][0]
        assert row['progress_percentage'] == 100.0
        assert row['at_risk'] is True

    def test_students_not_at_risk(self, api_client, instructor, course,
                                  lesson, student, enrollment):
        """High progress + recent activity: not at risk."""
        from django.utils import timezone

        LessonProgress.objects.create(
            user=student, lesson=lesson, completed=True,
            completed_at=timezone.now()
        )
        enrollment.update_activity()
        api_client.force_authenticate(user=instructor)
        response = api_client.get(self._url(course, 'students'))
        assert response.data['students'][0]['at_risk'] is False

    def test_students_streak_values(self, api_client, instructor, course,
                                    student, second_student, enrollment):
        """Streak read from GameProfile; 0 (not created) when none exists."""
        from gamification.models import GameProfile

        Enrollment.objects.create(user=second_student, course=course)
        GameProfile.objects.create(user=student, current_streak=5)

        api_client.force_authenticate(user=instructor)
        response = api_client.get(self._url(course, 'students'))
        by_email = {r['student']['email']: r for r in response.data['students']}
        assert by_email[student.email]['current_streak'] == 5
        assert by_email[second_student.email]['current_streak'] == 0
        # reading analytics must not create profiles
        assert not GameProfile.objects.filter(user=second_student).exists()

    def test_students_zero_students(self, api_client, instructor, course):
        api_client.force_authenticate(user=instructor)
        response = api_client.get(self._url(course, 'students'))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['students'] == []

    # ---- Activity ----

    def test_activity_series_and_zero_fill(self, api_client, instructor, course,
                                           unit, quiz, lesson, student, enrollment):
        """30 zero-filled days; all three series counted on the right day."""
        from datetime import timedelta
        from django.utils import timezone
        from quizzes.models import QuizAttempt

        now = timezone.now()
        LessonProgress.objects.create(
            user=student, lesson=lesson, completed=True, completed_at=now)
        QuizAttempt.objects.create(
            quiz=quiz, student=student, score=80.00, passed=True, completed_at=now)
        LessonQuizAttempt.objects.create(
            user=student, lesson=lesson, attempt_number=1,
            score=1, total_questions=1, passed=True, completed_at=now)

        api_client.force_authenticate(user=instructor)
        response = api_client.get(self._url(course, 'activity'))
        days = response.data['days']
        assert len(days) == 30
        assert days[-1]['date'] == timezone.localdate().isoformat()

        today_row = days[-1]
        assert today_row['lessons_completed'] == 1
        assert today_row['quiz_attempts'] == 1
        assert today_row['lesson_check_attempts'] == 1

        # a day with no events is present and zeroed
        empty_row = days[0]
        assert empty_row['lessons_completed'] == 0
        assert empty_row['quiz_attempts'] == 0
        assert empty_row['lesson_check_attempts'] == 0

    def test_activity_excludes_old_and_other_course_events(
            self, api_client, instructor, course, unit, lesson, student, enrollment,
            other_instructor):
        """Events outside the 30-day window or in another course don't count."""
        from datetime import timedelta
        from django.utils import timezone

        # outside the window (40 days ago)
        old = LessonProgress.objects.create(
            user=student, lesson=lesson, completed=True,
            completed_at=timezone.now() - timedelta(days=40))
        # other course event today
        other_course = Course.objects.create(
            code='OTHER101', title='Other Course', instructor=other_instructor)
        other_unit = Unit.objects.create(course=other_course, title='U', order=1)
        other_lesson = Lesson.objects.create(unit=other_unit, title='L', order=1)
        LessonProgress.objects.create(
            user=student, lesson=other_lesson, completed=True,
            completed_at=timezone.now())

        api_client.force_authenticate(user=instructor)
        response = api_client.get(self._url(course, 'activity'))
        assert all(d['lessons_completed'] == 0 for d in response.data['days'])


# ---------------------------------------------------------------------------
# Phase 32: Lesson-check mastery sessions
# ---------------------------------------------------------------------------


def _lesson_session_answer(client, lesson, question, correct):
    choice = question.choices.get(is_correct=correct)
    return client.post(
        f'/api/courses/lessons/{lesson.id}/quiz-session/answer/',
        {'question_id': question.id, 'choice_id': choice.id},
        format='json',
    )


@pytest.mark.django_db
class TestLessonQuizSessionPermissions:
    """Boundary trio (unauth 401 / instructor 403 / unenrolled 403) per route."""

    ROUTES = [
        ('post', 'quiz-session/start/'),
        ('get', 'quiz-session/'),
        ('post', 'quiz-session/answer/'),
    ]

    @pytest.mark.parametrize('method,suffix', ROUTES)
    def test_unauthenticated_401(self, api_client, lesson, method, suffix):
        _add_comprehension_quiz(lesson)
        response = getattr(api_client, method)(f'/api/courses/lessons/{lesson.id}/{suffix}')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize('method,suffix', ROUTES)
    def test_instructor_403(self, api_client, instructor, lesson, method, suffix):
        _add_comprehension_quiz(lesson)
        api_client.force_authenticate(user=instructor)
        response = getattr(api_client, method)(f'/api/courses/lessons/{lesson.id}/{suffix}')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data

    @pytest.mark.parametrize('method,suffix', ROUTES)
    def test_unenrolled_student_403(self, api_client, student, lesson, method, suffix):
        _add_comprehension_quiz(lesson)
        api_client.force_authenticate(user=student)
        response = getattr(api_client, method)(f'/api/courses/lessons/{lesson.id}/{suffix}')
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestLessonQuizSession:
    def test_start_no_questions_400(self, api_client, student, lesson, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/courses/lessons/{lesson.id}/quiz-session/start/')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_start_and_resume(self, api_client, student, lesson, enrollment):
        _add_comprehension_quiz(lesson)
        api_client.force_authenticate(user=student)
        first = api_client.post(f'/api/courses/lessons/{lesson.id}/quiz-session/start/')
        assert first.status_code == status.HTTP_201_CREATED
        assert first.data['status'] == 'in_progress'
        assert first.data['total_questions'] == 2

        again = api_client.post(f'/api/courses/lessons/{lesson.id}/quiz-session/start/')
        assert again.status_code == status.HTTP_200_OK
        assert again.data['attempt_id'] == first.data['attempt_id']

        get_resp = api_client.get(f'/api/courses/lessons/{lesson.id}/quiz-session/')
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.data['attempt_id'] == first.data['attempt_id']

    def test_get_session_404_when_none(self, api_client, student, lesson, enrollment):
        _add_comprehension_quiz(lesson)
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/lessons/{lesson.id}/quiz-session/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_mastery_loop_finalizes_passed_with_first_try_score(
        self, api_client, student, lesson, enrollment
    ):
        q1, q2 = _add_comprehension_quiz(lesson)
        api_client.force_authenticate(user=student)
        api_client.post(f'/api/courses/lessons/{lesson.id}/quiz-session/start/')

        miss = _lesson_session_answer(api_client, lesson, q1, correct=False)
        assert miss.data['is_correct'] is False
        assert miss.data['correct_choice_id'] == q1.choices.get(is_correct=True).id
        assert miss.data['session_complete'] is False

        _lesson_session_answer(api_client, lesson, q2, correct=True)
        final = _lesson_session_answer(api_client, lesson, q1, correct=True)
        assert final.data['session_complete'] is True

        result = final.data['result']
        assert result['passed'] is True
        assert result['score'] == 1  # first-try correct count
        assert result['total_questions'] == 2
        assert result['can_complete_lesson'] is True
        assert result['gamification']['xp_awarded'] == 20

        attempt = LessonQuizAttempt.objects.get(user=student, lesson=lesson)
        assert attempt.status == LessonQuizAttempt.STATUS_COMPLETED
        assert attempt.passed is True
        assert attempt.score == 1
        first_try = attempt.session_answers.get(question=q1)
        assert first_try.is_correct is False
        assert first_try.mastered_at is not None

    def test_mastery_updates_legacy_answers_and_unblocks_completion(
        self, api_client, student, lesson, enrollment
    ):
        q1, q2 = _add_comprehension_quiz(lesson)
        api_client.force_authenticate(user=student)
        api_client.post(f'/api/courses/lessons/{lesson.id}/quiz-session/start/')
        _lesson_session_answer(api_client, lesson, q1, correct=False)
        _lesson_session_answer(api_client, lesson, q2, correct=True)
        _lesson_session_answer(api_client, lesson, q1, correct=True)

        # Legacy latest-answer rows now all correct -> status contract holds.
        status_resp = api_client.get(f'/api/courses/lessons/{lesson.id}/questions-status/')
        assert status_resp.data['all_correct'] is True
        assert status_resp.data['can_complete_lesson'] is True
        assert status_resp.data['has_passed'] is True

        # Lesson completion is unblocked.
        progress = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/progress/', {'completed': True}
        )
        assert progress.status_code == status.HTTP_200_OK
        assert progress.data['completed'] is True

    def test_attempt_cap_ignored(self, api_client, student, lesson, enrollment):
        """max_quiz_attempts is retired: prior completed attempts never block."""
        _add_comprehension_quiz(lesson)
        lesson.max_quiz_attempts = 1
        lesson.save()
        LessonQuizAttempt.objects.create(
            user=student, lesson=lesson, attempt_number=1,
            score=0, total_questions=2, passed=False,
        )

        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/courses/lessons/{lesson.id}/quiz-session/start/')
        assert response.status_code == status.HTTP_201_CREATED

        status_resp = api_client.get(f'/api/courses/lessons/{lesson.id}/questions-status/')
        assert status_resp.data['can_attempt'] is True
        assert status_resp.data['attempts_remaining'] is None
        assert status_resp.data['max_attempts'] is None

    def test_xp_awarded_once_across_sessions(self, api_client, student, lesson, enrollment):
        q1, q2 = _add_comprehension_quiz(lesson)
        api_client.force_authenticate(user=student)

        for expected_xp in (20, 0):
            api_client.post(f'/api/courses/lessons/{lesson.id}/quiz-session/start/')
            _lesson_session_answer(api_client, lesson, q1, correct=True)
            final = _lesson_session_answer(api_client, lesson, q2, correct=True)
            assert final.data['result']['gamification']['xp_awarded'] == expected_xp

    def test_answer_rejects_foreign_and_mastered(self, api_client, student, lesson, unit, enrollment):
        q1, _q2 = _add_comprehension_quiz(lesson)
        other_lesson = Lesson.objects.create(unit=unit, title='Other', order=9)
        foreign_q = LessonQuestion.objects.create(lesson=other_lesson, text='F?', order=1)
        foreign_c = LessonQuestionChoice.objects.create(
            question=foreign_q, text='X', is_correct=True, order=1
        )

        api_client.force_authenticate(user=student)
        api_client.post(f'/api/courses/lessons/{lesson.id}/quiz-session/start/')

        foreign = api_client.post(
            f'/api/courses/lessons/{lesson.id}/quiz-session/answer/',
            {'question_id': foreign_q.id, 'choice_id': foreign_c.id}, format='json'
        )
        assert foreign.status_code == status.HTTP_400_BAD_REQUEST

        _lesson_session_answer(api_client, lesson, q1, correct=True)
        again = _lesson_session_answer(api_client, lesson, q1, correct=True)
        assert again.status_code == status.HTTP_400_BAD_REQUEST

    def test_answer_without_session_400(self, api_client, student, lesson, enrollment):
        q1, _q2 = _add_comprehension_quiz(lesson)
        api_client.force_authenticate(user=student)
        response = _lesson_session_answer(api_client, lesson, q1, correct=True)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_in_progress_ignored_by_questions_status(self, api_client, student, lesson, enrollment):
        _add_comprehension_quiz(lesson)
        api_client.force_authenticate(user=student)
        api_client.post(f'/api/courses/lessons/{lesson.id}/quiz-session/start/')

        status_resp = api_client.get(f'/api/courses/lessons/{lesson.id}/questions-status/')
        assert status_resp.data['attempt_count'] == 0
        assert status_resp.data['has_passed'] is False


# ==================== Course Map (Phase 35) ====================

@pytest.fixture
def map_course(instructor):
    """Two units: (A1, A2, Boss A) then (B1, Boss B) — 5 map nodes."""
    from quizzes.models import Quiz

    course = Course.objects.create(
        code='MAP101', title='Map Course', instructor=instructor
    )
    unit1 = Unit.objects.create(course=course, title='Unit One', order=1)
    unit2 = Unit.objects.create(course=course, title='Unit Two', order=2)
    return {
        'course': course,
        'unit1': unit1,
        'unit2': unit2,
        'lesson_a1': Lesson.objects.create(unit=unit1, title='A1', order=1),
        'lesson_a2': Lesson.objects.create(unit=unit1, title='A2', order=2),
        'boss_a': Quiz.objects.create(unit=unit1, title='Boss A', order=1, passing_score=70),
        'lesson_b1': Lesson.objects.create(unit=unit2, title='B1', order=1),
        'boss_b': Quiz.objects.create(unit=unit2, title='Boss B', order=1, passing_score=70),
    }


@pytest.mark.django_db
class TestCourseMap:
    URL = '/api/courses/courses/MAP101/map/'

    @staticmethod
    def flat_nodes(data):
        return [node for unit in data['units'] for node in unit['nodes']]

    def test_enrolled_student_gets_full_tree_in_order(self, api_client, student, map_course):
        """Units by order; each unit's lessons before its quizzes."""
        Enrollment.objects.create(user=student, course=map_course['course'])
        api_client.force_authenticate(user=student)

        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.data

        assert data['course_code'] == 'MAP101'
        assert data['course_title'] == 'Map Course'
        assert data['total_nodes'] == 5
        assert data['completed_nodes'] == 0
        assert [u['title'] for u in data['units']] == ['Unit One', 'Unit Two']

        sequence = [(n['node_type'], n['id']) for n in self.flat_nodes(data)]
        assert sequence == [
            ('lesson', map_course['lesson_a1'].id),
            ('lesson', map_course['lesson_a2'].id),
            ('quiz', map_course['boss_a'].id),
            ('lesson', map_course['lesson_b1'].id),
            ('quiz', map_course['boss_b'].id),
        ]
        # Quiz nodes carry scores; lesson nodes don't.
        boss_node = data['units'][0]['nodes'][2]
        assert boss_node['passing_score'] == 70
        assert boss_node['best_score'] is None
        assert 'passing_score' not in data['units'][0]['nodes'][0]

    def test_state_progression(self, api_client, student, map_course):
        """Nothing done: node 1 current, rest locked. Complete lesson 1:
        it flips to completed and node 2 becomes current."""
        Enrollment.objects.create(user=student, course=map_course['course'])
        api_client.force_authenticate(user=student)

        data = api_client.get(self.URL).data
        states = [n['state'] for n in self.flat_nodes(data)]
        assert states == ['current', 'locked', 'locked', 'locked', 'locked']
        assert data['current_node_id'] == f"lesson-{map_course['lesson_a1'].id}"

        LessonProgress.objects.create(
            user=student, lesson=map_course['lesson_a1'], completed=True
        )
        data = api_client.get(self.URL).data
        states = [n['state'] for n in self.flat_nodes(data)]
        assert states == ['completed', 'current', 'locked', 'locked', 'locked']
        assert data['completed_nodes'] == 1
        assert data['current_node_id'] == f"lesson-{map_course['lesson_a2'].id}"

    def test_quiz_boss_node_scores(self, api_client, student, map_course):
        """Failed attempt: not completed but best_score reported; passing
        attempt completes the boss and advances current into unit 2."""
        from quizzes.models import QuizAttempt

        Enrollment.objects.create(user=student, course=map_course['course'])
        for lesson in (map_course['lesson_a1'], map_course['lesson_a2']):
            LessonProgress.objects.create(user=student, lesson=lesson, completed=True)
        api_client.force_authenticate(user=student)

        QuizAttempt.objects.create(
            quiz=map_course['boss_a'], student=student, score=40.00, passed=False
        )
        data = api_client.get(self.URL).data
        boss_node = data['units'][0]['nodes'][2]
        assert boss_node['state'] == 'current'
        assert boss_node['best_score'] == 40.0

        QuizAttempt.objects.create(
            quiz=map_course['boss_a'], student=student, score=85.00, passed=True
        )
        data = api_client.get(self.URL).data
        boss_node = data['units'][0]['nodes'][2]
        assert boss_node['state'] == 'completed'
        assert boss_node['best_score'] == 85.0
        assert data['current_node_id'] == f"lesson-{map_course['lesson_b1'].id}"
        assert data['completed_nodes'] == 3

    def test_required_quiz_unlocks_with_its_lesson(self, api_client, student, map_course):
        """Deadlock exception: a lesson's required_quiz is unlocked while the
        lesson is still incomplete (not locked behind its completion)."""
        map_course['lesson_a2'].required_quiz = map_course['boss_a']
        map_course['lesson_a2'].save()
        Enrollment.objects.create(user=student, course=map_course['course'])
        LessonProgress.objects.create(
            user=student, lesson=map_course['lesson_a1'], completed=True
        )
        api_client.force_authenticate(user=student)

        data = api_client.get(self.URL).data
        nodes = self.flat_nodes(data)
        assert nodes[1]['state'] == 'current'   # A2 (the gated lesson)
        assert nodes[2]['state'] == 'unlocked'  # Boss A: unlocked, not current
        assert nodes[3]['state'] == 'locked'    # B1 untouched by the exception

    def test_permission_boundaries(self, api_client, student, instructor, map_course):
        """Unenrolled student 403; course instructor 200; anonymous 401."""
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        api_client.force_authenticate(user=student)
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

        api_client.force_authenticate(user=instructor)
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK


def make_attachment_file(name='notes.txt', content=b'hello world'):
    return SimpleUploadedFile(name, content, content_type='text/plain')


@pytest.mark.django_db
class TestLessonAttachments:
    """Upload/delete coverage added in Phase 39, when media moved to R2 and
    these endpoints became load-bearing. Tests run against FileSystemStorage
    in a temp MEDIA_ROOT — the R2 swap itself is covered by the settings
    tests in config/tests/test_storage_settings.py."""

    @pytest.fixture(autouse=True)
    def media_tmp(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path

    def url(self, lesson):
        return f'/api/courses/lessons/{lesson.id}/attachments/'

    def test_instructor_upload_201_with_absolute_url(
            self, api_client, instructor, lesson):
        api_client.force_authenticate(user=instructor)

        response = api_client.post(
            self.url(lesson),
            {'files': [make_attachment_file()]},
            format='multipart',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) == 1
        assert response.data[0]['filename'] == 'notes.txt'
        # Serializer must return an absolute URL (prod: the r2.dev host).
        assert response.data[0]['url'].startswith('http://testserver/')
        assert 'lesson_attachments/' in response.data[0]['url']

    def test_enrolled_student_upload_403(
            self, api_client, student, lesson, enrollment):
        api_client.force_authenticate(user=student)

        response = api_client.post(
            self.url(lesson),
            {'files': [make_attachment_file()]},
            format='multipart',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_anonymous_upload_401(self, api_client, lesson):
        response = api_client.post(
            self.url(lesson),
            {'files': [make_attachment_file()]},
            format='multipart',
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_removes_stored_file(self, api_client, instructor, lesson):
        api_client.force_authenticate(user=instructor)
        created = api_client.post(
            self.url(lesson),
            {'files': [make_attachment_file()]},
            format='multipart',
        ).data
        attachment = LessonAttachment.objects.get(pk=created[0]['id'])
        stored = Path(attachment.file.path)
        assert stored.exists()

        response = api_client.delete(
            f"{self.url(lesson)}{attachment.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not stored.exists()
        assert lesson.attachments.count() == 0

    def test_limit_of_10_per_lesson(self, api_client, instructor, lesson):
        api_client.force_authenticate(user=instructor)
        for i in range(10):
            LessonAttachment.objects.create(
                lesson=lesson,
                file=make_attachment_file(f'file{i}.txt'),
                filename=f'file{i}.txt',
                file_type='txt',
                file_size=11,
            )

        response = api_client.post(
            self.url(lesson),
            {'files': [make_attachment_file('one-too-many.txt')]},
            format='multipart',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Maximum 10 attachments' in response.data['error']
        assert lesson.attachments.count() == 10

    def test_oversized_attachment_rejected(
            self, api_client, instructor, lesson, settings):
        """A file over ATTACHMENT_MAX_UPLOAD_BYTES is refused before storage,
        mirroring the avatar cap."""
        settings.ATTACHMENT_MAX_UPLOAD_BYTES = 1024  # 1 KB cap for the test
        api_client.force_authenticate(user=instructor)

        response = api_client.post(
            self.url(lesson),
            {'files': [make_attachment_file('big.txt', b'0' * 4096)]},
            format='multipart',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'exceeds' in response.data['error']
        assert lesson.attachments.count() == 0


@pytest.mark.django_db
class TestOutboundEmail:
    """Phase 47: mail.outbox coverage for the invite/announcement senders and
    the demo outbound-email guard in core.email.send_templated_email."""

    def test_invite_sends_email_with_token_link(
            self, api_client, instructor, course, monkeypatch):
        from django.core import mail
        import courses.views as courses_views

        # Invite emails go through send_emails_async's daemon thread, which
        # races the outbox assertions — run the queued tasks inline.
        monkeypatch.setattr(
            courses_views, 'send_emails_async',
            lambda tasks: [f(*a, **k) for f, a, k in tasks])

        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/courses/courses/{course.code}/invites/',
            {'emails': ['newstudent@example.com']},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == ['newstudent@example.com']
        assert course.title in message.subject
        from courses.models import CourseInvite
        invite = CourseInvite.objects.get(email='newstudent@example.com')
        assert f'/invite/{invite.token}' in message.body

    def test_announcement_emails_only_opted_in_students(
            self, api_client, instructor, course, student, enrollment,
            monkeypatch):
        import core.email as core_email
        from django.core import mail
        from accounts.models import UserPreferences

        # Opted-in student (signal auto-creates prefs; default is opted in).
        UserPreferences.objects.filter(user=student).update(
            email_announcements=True)

        # Second enrolled student who opted out.
        opted_out = User.objects.create_user(
            email='optout@test.com', password='testpass123')
        UserPreferences.objects.filter(user=opted_out).update(
            email_announcements=False)
        Enrollment.objects.create(user=opted_out, course=course)

        # send_emails_async fires a daemon thread, which races the test's
        # outbox assertions — run the queued tasks inline instead. The
        # task-building, per-student preference filtering, and the real
        # send_announcement_email path are all still exercised.
        monkeypatch.setattr(
            core_email, 'send_emails_async',
            lambda tasks: [f(*a, **k) for f, a, k in tasks])

        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/courses/courses/{course.code}/announcements/', {
                'title': 'Emailed Update',
                'content': 'This announcement goes out by email.',
                'send_email': True,
            })

        assert response.status_code == status.HTTP_201_CREATED
        assert [m.to for m in mail.outbox] == [[student.email]]
        assert 'Emailed Update' in mail.outbox[0].subject

    def test_demo_user_cannot_trigger_email(self, settings):
        from django.core import mail
        from core.email import send_templated_email

        settings.DEMO_ACCOUNT_EMAIL = 'demo@test.com'
        demo = User.objects.create_user(
            email='demo@test.com', password='testpass123')

        sent = send_templated_email(
            subject='Should never send',
            template_name='emails/course_invite_link.html',
            context={
                'course_title': 'X', 'instructor_name': 'Y',
                'invite_url': 'http://example.com/invite/Z',
            },
            recipient_list=['victim@example.com'],
            triggered_by=demo,
        )

        assert sent is False
        assert len(mail.outbox) == 0

    def test_non_demo_user_can_trigger_email(self, instructor):
        from django.core import mail
        from core.email import send_templated_email

        sent = send_templated_email(
            subject='Legit email',
            template_name='emails/course_invite_link.html',
            context={
                'course_title': 'X', 'instructor_name': 'Y',
                'invite_url': 'http://example.com/invite/Z',
            },
            recipient_list=['student@example.com'],
            triggered_by=instructor,
        )

        assert sent is True
        assert len(mail.outbox) == 1


# ==================== Course Invites (Phase 51) ====================

from datetime import timedelta

from django.utils import timezone

from .models import CourseInvite


@pytest.fixture
def other_instructor():
    return User.objects.create_user(
        email='other-instructor@test.com',
        password='testpass123',
        first_name='Other',
        last_name='Instructor',
        is_instructor=True,
    )


def invites_url(course):
    return f'/api/courses/courses/{course.code}/invites/'


def accept_url(token):
    return f'/api/courses/invites/{token}/accept/'


def detail_url(token):
    return f'/api/courses/invites/{token}/'


VALID_ACCEPT_BODY = {
    'first_name': 'New',
    'last_name': 'Student',
    'password': 'correct-horse-battery',
    'agree_terms': True,
}


@pytest.mark.django_db
class TestCourseInviteCreate:

    def test_bulk_create_mixed_outcomes(
            self, api_client, instructor, course, student, enrollment,
            settings, monkeypatch):
        """One POST, per-email outcomes: invited / resent / already_enrolled
        / invalid (bad address, demo account, instructor's own email);
        duplicates within the paste are silently deduped."""
        from django.core import mail
        import courses.views as courses_views

        monkeypatch.setattr(
            courses_views, 'send_emails_async',
            lambda tasks: [f(*a, **k) for f, a, k in tasks])

        pending = CourseInvite.objects.create(
            course=course, email='pending@example.com', invited_by=instructor)

        api_client.force_authenticate(user=instructor)
        response = api_client.post(invites_url(course), {'emails': [
            'new@example.com',
            'Pending@Example.com',      # normalizes to the pending invite
            student.email,              # actively enrolled
            'not-an-email',
            settings.DEMO_ACCOUNT_EMAIL,
            instructor.email,           # course owner
            'NEW@example.com',          # duplicate of the first, deduped
        ]}, format='json')

        assert response.status_code == status.HTTP_200_OK
        outcomes = {r['email']: r['status'] for r in response.data['results']}
        assert outcomes == {
            'new@example.com': 'invited',
            'pending@example.com': 'resent',
            student.email: 'already_enrolled',
            'not-an-email': 'invalid',
            settings.DEMO_ACCOUNT_EMAIL: 'invalid',
            instructor.email: 'invalid',
        }
        # Emails went out only for invited + resent.
        assert sorted(m.to[0] for m in mail.outbox) == [
            'new@example.com', 'pending@example.com']
        # The resent invite was refreshed in place, not duplicated.
        assert CourseInvite.objects.filter(
            course=course, email='pending@example.com').count() == 1
        refreshed = CourseInvite.objects.get(pk=pending.pk)
        assert refreshed.token != pending.token

    def test_reinvite_refreshes_instead_of_duplicating(
            self, api_client, instructor, course):
        api_client.force_authenticate(user=instructor)
        api_client.post(invites_url(course),
                        {'emails': ['kid@example.com']}, format='json')
        first = CourseInvite.objects.get(email='kid@example.com')

        response = api_client.post(invites_url(course),
                                   {'emails': ['kid@example.com']}, format='json')

        assert response.data['results'][0]['status'] == 'resent'
        assert CourseInvite.objects.filter(email='kid@example.com').count() == 1
        second = CourseInvite.objects.get(email='kid@example.com')
        assert second.pk == first.pk
        assert second.token != first.token
        assert second.expires_at >= first.expires_at

    def test_reinvite_after_expiry_counts_as_invited(
            self, api_client, instructor, course):
        CourseInvite.objects.create(
            course=course, email='late@example.com', invited_by=instructor,
            expires_at=timezone.now() - timedelta(days=1))

        api_client.force_authenticate(user=instructor)
        response = api_client.post(invites_url(course),
                                   {'emails': ['late@example.com']}, format='json')

        assert response.data['results'][0]['status'] == 'invited'
        invite = CourseInvite.objects.get(email='late@example.com')
        assert invite.is_pending

    def test_requires_email_list(self, api_client, instructor, course):
        api_client.force_authenticate(user=instructor)
        for bad_body in ({}, {'emails': []}, {'emails': 'a@x.com'}):
            response = api_client.post(invites_url(course), bad_body, format='json')
            assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_student_forbidden(self, api_client, student, course):
        api_client.force_authenticate(user=student)
        assert api_client.post(
            invites_url(course), {'emails': ['a@x.com']}, format='json'
        ).status_code == status.HTTP_403_FORBIDDEN
        assert api_client.get(
            invites_url(course)).status_code == status.HTTP_403_FORBIDDEN

    def test_non_owner_instructor_forbidden(
            self, api_client, other_instructor, course):
        api_client.force_authenticate(user=other_instructor)
        assert api_client.post(
            invites_url(course), {'emails': ['a@x.com']}, format='json'
        ).status_code == status.HTTP_403_FORBIDDEN

    def test_anonymous_unauthorized(self, api_client, course):
        response = api_client.post(
            invites_url(course), {'emails': ['a@x.com']}, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_invites_with_statuses(self, api_client, instructor, course):
        CourseInvite.objects.create(
            course=course, email='pending@example.com', invited_by=instructor)
        CourseInvite.objects.create(
            course=course, email='expired@example.com', invited_by=instructor,
            expires_at=timezone.now() - timedelta(minutes=1))
        CourseInvite.objects.create(
            course=course, email='revoked@example.com', invited_by=instructor,
            revoked_at=timezone.now())
        CourseInvite.objects.create(
            course=course, email='accepted@example.com', invited_by=instructor,
            accepted_at=timezone.now())

        api_client.force_authenticate(user=instructor)
        response = api_client.get(invites_url(course))

        assert response.status_code == status.HTTP_200_OK
        statuses = {row['email']: row['status'] for row in response.data}
        assert statuses == {
            'pending@example.com': 'pending',
            'expired@example.com': 'expired',
            'revoked@example.com': 'revoked',
            'accepted@example.com': 'accepted',
        }


@pytest.mark.django_db
class TestCourseInviteRevoke:

    def test_revoke_pending_invite(self, api_client, instructor, course):
        invite = CourseInvite.objects.create(
            course=course, email='kid@example.com', invited_by=instructor)

        api_client.force_authenticate(user=instructor)
        response = api_client.delete(f'{invites_url(course)}{invite.id}/')

        assert response.status_code == status.HTTP_200_OK
        invite.refresh_from_db()
        assert invite.status == 'revoked'

    def test_accepted_invite_cannot_be_revoked(
            self, api_client, instructor, course):
        invite = CourseInvite.objects.create(
            course=course, email='kid@example.com', invited_by=instructor,
            accepted_at=timezone.now())

        api_client.force_authenticate(user=instructor)
        response = api_client.delete(f'{invites_url(course)}{invite.id}/')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        invite.refresh_from_db()
        assert invite.revoked_at is None

    def test_student_cannot_revoke(self, api_client, student, instructor, course):
        invite = CourseInvite.objects.create(
            course=course, email='kid@example.com', invited_by=instructor)
        api_client.force_authenticate(user=student)
        assert api_client.delete(
            f'{invites_url(course)}{invite.id}/'
        ).status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestInviteDetail:

    def test_pending_invite_no_account(self, api_client, instructor, course):
        invite = CourseInvite.objects.create(
            course=course, email='newkid@example.com', invited_by=instructor)

        response = api_client.get(detail_url(invite.token))

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            'course_title': course.title,
            'course_code': course.code,
            'email_masked': 'n***d@example.com',
            'status': 'pending',
            'account_exists': False,
        }

    def test_pending_invite_with_account(
            self, api_client, instructor, course, student):
        invite = CourseInvite.objects.create(
            course=course, email=student.email, invited_by=instructor)
        response = api_client.get(detail_url(invite.token))
        assert response.data['account_exists'] is True

    def test_dead_invites_report_status(self, api_client, instructor, course):
        expired = CourseInvite.objects.create(
            course=course, email='a@example.com', invited_by=instructor,
            expires_at=timezone.now() - timedelta(minutes=1))
        revoked = CourseInvite.objects.create(
            course=course, email='b@example.com', invited_by=instructor,
            revoked_at=timezone.now())
        accepted = CourseInvite.objects.create(
            course=course, email='c@example.com', invited_by=instructor,
            accepted_at=timezone.now())

        for invite, expected in ((expired, 'expired'), (revoked, 'revoked'),
                                 (accepted, 'accepted')):
            response = api_client.get(detail_url(invite.token))
            assert response.status_code == status.HTTP_200_OK
            assert response.data['status'] == expected

    def test_unknown_token_is_invalid_not_500(self, api_client):
        response = api_client.get(detail_url('no-such-token'))
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['status'] == 'invalid'


@pytest.mark.django_db
class TestInviteAccept:

    def test_accept_creates_verified_user_enrollment_and_jwt(
            self, api_client, instructor, course):
        from allauth.account.models import EmailAddress

        invite = CourseInvite.objects.create(
            course=course, email='newkid@example.com', invited_by=instructor)

        response = api_client.post(
            accept_url(invite.token), VALID_ACCEPT_BODY, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['access'] and response.data['refresh']
        assert response.data['user']['email'] == 'newkid@example.com'

        user = User.objects.get(email='newkid@example.com')
        assert user.first_name == 'New'
        assert user.is_instructor is False
        email_address = EmailAddress.objects.get(user=user)
        assert email_address.verified is True and email_address.primary is True
        assert Enrollment.objects.filter(
            user=user, course=course, is_active=True).exists()
        invite.refresh_from_db()
        assert invite.status == 'accepted'

    def test_token_dead_after_accept(self, api_client, instructor, course):
        invite = CourseInvite.objects.create(
            course=course, email='newkid@example.com', invited_by=instructor)
        api_client.post(accept_url(invite.token), VALID_ACCEPT_BODY, format='json')

        response = api_client.post(
            accept_url(invite.token), VALID_ACCEPT_BODY, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['status'] == 'accepted'

    def test_expired_and_revoked_and_unknown_tokens_rejected(
            self, api_client, instructor, course):
        expired = CourseInvite.objects.create(
            course=course, email='a@example.com', invited_by=instructor,
            expires_at=timezone.now() - timedelta(minutes=1))
        revoked = CourseInvite.objects.create(
            course=course, email='b@example.com', invited_by=instructor,
            revoked_at=timezone.now())

        for token, expected in ((expired.token, 'expired'),
                                (revoked.token, 'revoked'),
                                ('no-such-token', 'invalid')):
            response = api_client.post(
                accept_url(token), VALID_ACCEPT_BODY, format='json')
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert response.data['status'] == expected
        assert not User.objects.filter(email='a@example.com').exists()

    def test_accept_validates_body(self, api_client, instructor, course):
        invite = CourseInvite.objects.create(
            course=course, email='newkid@example.com', invited_by=instructor)

        response = api_client.post(accept_url(invite.token), {
            'first_name': '', 'last_name': '',
            'password': '123', 'agree_terms': False,
        }, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        for field in ('first_name', 'last_name', 'password', 'agree_terms'):
            assert field in response.data
        assert not User.objects.filter(email='newkid@example.com').exists()
        invite.refresh_from_db()
        assert invite.status == 'pending'

    def test_accept_existing_account_authed_enrolls(
            self, api_client, instructor, course, student):
        invite = CourseInvite.objects.create(
            course=course, email=student.email, invited_by=instructor)

        api_client.force_authenticate(user=student)
        response = api_client.post(accept_url(invite.token), {}, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert Enrollment.objects.filter(
            user=student, course=course, is_active=True).exists()
        invite.refresh_from_db()
        assert invite.status == 'accepted'

    def test_accept_existing_account_reactivates_soft_deleted_enrollment(
            self, api_client, instructor, course, student, enrollment):
        enrollment.is_active = False
        enrollment.save(update_fields=['is_active'])
        invite = CourseInvite.objects.create(
            course=course, email=student.email, invited_by=instructor)

        api_client.force_authenticate(user=student)
        response = api_client.post(accept_url(invite.token), {}, format='json')

        assert response.status_code == status.HTTP_200_OK
        enrollment.refresh_from_db()
        assert enrollment.is_active is True
        assert Enrollment.objects.filter(user=student, course=course).count() == 1

    def test_accept_existing_account_anon_gets_403_account_exists(
            self, api_client, instructor, course, student):
        invite = CourseInvite.objects.create(
            course=course, email=student.email, invited_by=instructor)

        response = api_client.post(
            accept_url(invite.token), VALID_ACCEPT_BODY, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data['account_exists'] is True
        invite.refresh_from_db()
        assert invite.status == 'pending'

    def test_accept_existing_account_wrong_user_gets_403(
            self, api_client, instructor, course, student, other_instructor):
        invite = CourseInvite.objects.create(
            course=course, email=student.email, invited_by=instructor)

        api_client.force_authenticate(user=other_instructor)
        response = api_client.post(accept_url(invite.token), {}, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data['account_exists'] is True

    def test_accept_is_atomic_no_user_left_behind(
            self, instructor, course, monkeypatch):
        """If enrollment creation blows up, the freshly created user (and
        the invite's accepted_at) must roll back with it."""
        import courses.views as courses_views

        invite = CourseInvite.objects.create(
            course=course, email='newkid@example.com', invited_by=instructor)

        def explode(user, course):
            raise RuntimeError('enrollment failed')

        monkeypatch.setattr(courses_views, '_activate_enrollment', explode)
        client = APIClient(raise_request_exception=False)
        response = client.post(
            accept_url(invite.token), VALID_ACCEPT_BODY, format='json')

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert not User.objects.filter(email='newkid@example.com').exists()
        invite.refresh_from_db()
        assert invite.status == 'pending'


@pytest.mark.django_db
class TestPhase51Throttles:
    """Env-gated rates: unset (the default) means unlimited; when a rate is
    set, the scoped/user buckets enforce it. DRF snapshots rates onto the
    throttle classes at import, so tests patch the class attribute."""

    def test_invite_send_scoped_throttle_skips_reads(
            self, api_client, instructor, course, monkeypatch):
        from django.core.cache import cache
        from rest_framework.throttling import ScopedRateThrottle

        monkeypatch.setattr(
            ScopedRateThrottle, 'THROTTLE_RATES', {'invite_send': '2/hour'})
        cache.clear()
        try:
            api_client.force_authenticate(user=instructor)
            for _ in range(2):
                ok = api_client.post(
                    invites_url(course), {'emails': ['a@x.com']}, format='json')
                assert ok.status_code == status.HTTP_200_OK

            throttled = api_client.post(
                invites_url(course), {'emails': ['a@x.com']}, format='json')
            assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS

            # GET shares the URL but must not consume or hit the send bucket.
            listed = api_client.get(invites_url(course))
            assert listed.status_code == status.HTTP_200_OK
        finally:
            cache.clear()

    def test_invite_accept_scoped_throttle(self, api_client, monkeypatch):
        from django.core.cache import cache
        from rest_framework.throttling import ScopedRateThrottle

        monkeypatch.setattr(
            ScopedRateThrottle, 'THROTTLE_RATES', {'invite_accept': '2/hour'})
        cache.clear()
        try:
            for _ in range(2):
                response = api_client.post(
                    accept_url('bogus'), VALID_ACCEPT_BODY, format='json')
                assert response.status_code == status.HTTP_400_BAD_REQUEST

            throttled = api_client.post(
                accept_url('bogus'), VALID_ACCEPT_BODY, format='json')
            assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        finally:
            cache.clear()

    def test_user_throttle_off_by_default(self, api_client, student, enrollment):
        """THROTTLE_USER unset => rate None => authenticated traffic is
        unlimited (the class is installed but inert)."""
        from rest_framework.settings import api_settings

        assert api_settings.DEFAULT_THROTTLE_RATES['user'] is None
        api_client.force_authenticate(user=student)
        for _ in range(30):
            response = api_client.get('/api/courses/courses/')
            assert response.status_code == status.HTTP_200_OK

    def test_user_throttle_enforced_when_rate_set(
            self, api_client, student, enrollment, monkeypatch):
        from django.core.cache import cache
        from rest_framework.throttling import UserRateThrottle

        monkeypatch.setattr(
            UserRateThrottle, 'THROTTLE_RATES', {'user': '3/min'})
        cache.clear()
        try:
            api_client.force_authenticate(user=student)
            for _ in range(3):
                ok = api_client.get('/api/courses/courses/')
                assert ok.status_code == status.HTTP_200_OK

            throttled = api_client.get('/api/courses/courses/')
            assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        finally:
            cache.clear()


# ---------------------------------------------------------------------------
# Phase 52: YouTube video-ID extraction, validation, and repair migration
# ---------------------------------------------------------------------------

from importlib import import_module

from courses.video import extract_youtube_video_id


class TestYouTubeVideoIdExtraction:
    """Pure unit tests for the extractor contract (no DB)."""

    @pytest.mark.parametrize('value', [
        'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'https://youtube.com/watch?v=dQw4w9WgXcQ',
        'https://m.youtube.com/watch?v=dQw4w9WgXcQ',
        'https://www.youtube.com/watch?feature=share&v=dQw4w9WgXcQ',
        'https://youtu.be/dQw4w9WgXcQ',
        'https://youtu.be/dQw4w9WgXcQ?si=AbCdEf123&t=42',
        'https://www.youtube.com/shorts/dQw4w9WgXcQ',
        'https://www.youtube.com/shorts/dQw4w9WgXcQ?feature=share',
        'https://www.youtube.com/live/dQw4w9WgXcQ',
        'https://www.youtube.com/live/dQw4w9WgXcQ?si=xyz',
        'https://www.youtube.com/embed/dQw4w9WgXcQ',
        'dQw4w9WgXcQ',
        '  https://youtu.be/dQw4w9WgXcQ  ',
    ])
    def test_accepts_all_contract_forms(self, value):
        assert extract_youtube_video_id(value) == 'dQw4w9WgXcQ'

    @pytest.mark.parametrize('value', [
        'https://google.com/foo',
        'https://www.youtube.com/watch?v=short',
        '',
        'dQw4w9WgXcQx2',  # 12+ chars of garbage
        'https://vimeo.com/123456789',
        'https://www.youtube.com/watch',
        'not a url at all',
        None,
    ])
    def test_rejects_non_extractable_values(self, value):
        assert extract_youtube_video_id(value) is None


@pytest.mark.django_db
class TestLessonVideoValidation:
    def test_lesson_update_with_shorts_url_stores_bare_id(
            self, api_client, instructor, lesson):
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/',
            {'video_type': 'youtube',
             'video_id': 'https://www.youtube.com/shorts/dQw4w9WgXcQ'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        lesson.refresh_from_db()
        assert lesson.video_id == 'dQw4w9WgXcQ'
        assert lesson.video_type == 'youtube'

    def test_lesson_update_with_long_share_url_stores_bare_id(
            self, api_client, instructor, lesson):
        # Regression: a valid share URL longer than the 50-char column must be
        # extracted, not rejected for length. DRF runs the model-derived
        # max_length validator before validate(), so without an input-length
        # override this 63-char URL 400s on max_length instead of normalizing.
        url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ&si=aB3dEfGhIjKlMnOp'
        assert len(url) > 50
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/',
            {'video_type': 'youtube', 'video_id': url},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        lesson.refresh_from_db()
        assert lesson.video_id == 'dQw4w9WgXcQ'

    def test_lesson_update_oversized_video_id_rejected(
            self, api_client, instructor, lesson):
        # The input-length override is bounded (255) so oversized junk is still
        # rejected before extraction runs.
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/',
            {'video_type': 'youtube', 'video_id': 'x' * 5000},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'video_id' in response.data

    def test_lesson_update_unparseable_returns_field_error(
            self, api_client, instructor, lesson):
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/',
            {'video_type': 'youtube', 'video_id': 'https://example.com'},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'video_id' in response.data
        lesson.refresh_from_db()
        assert lesson.video_id == ''

    def test_lesson_vimeo_choice_rejected(self, api_client, instructor, lesson):
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/',
            {'video_type': 'vimeo', 'video_id': '123456789'},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'video_type' in response.data

    def test_lesson_video_type_none_forces_empty_video_id(
            self, api_client, instructor, lesson):
        lesson.video_type = 'youtube'
        lesson.video_id = 'dQw4w9WgXcQ'
        lesson.save()
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/',
            {'video_type': 'none', 'video_id': 'dQw4w9WgXcQ'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        lesson.refresh_from_db()
        assert lesson.video_type == 'none'
        assert lesson.video_id == ''


@pytest.mark.django_db
class TestSectionVideoValidation:
    def test_section_create_with_youtu_be_si_url_stores_bare_id(
            self, api_client, instructor, lesson):
        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/courses/lessons/{lesson.id}/sections/',
            {'title': 'Video section', 'content': '',
             'video_type': 'youtube',
             'video_id': 'https://youtu.be/dQw4w9WgXcQ?si=TrAcKiNg42'},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['video_id'] == 'dQw4w9WgXcQ'

    def test_section_bulk_create_normalizes_video_ids(
            self, api_client, instructor, lesson):
        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/courses/lessons/{lesson.id}/sections/bulk/',
            {'sections': [
                {'title': 'Plain', 'content': 'a'},
                {'title': 'With video', 'content': 'b',
                 'video_type': 'youtube',
                 'video_id': 'https://youtu.be/dQw4w9WgXcQ?si=TrAcKiNg42'},
            ]},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data[1]['video_id'] == 'dQw4w9WgXcQ'

    def test_section_unparseable_video_id_rejected(
            self, api_client, instructor, lesson):
        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/courses/lessons/{lesson.id}/sections/',
            {'title': 'Bad video', 'content': '',
             'video_type': 'youtube', 'video_id': 'https://example.com'},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'video_id' in response.data
        assert lesson.sections.count() == 0

    def test_section_vimeo_choice_rejected(self, api_client, instructor, lesson):
        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/courses/lessons/{lesson.id}/sections/',
            {'title': 'Vimeo section', 'content': '',
             'video_type': 'vimeo', 'video_id': '123456789'},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'video_type' in response.data


@pytest.mark.django_db
class TestRepairVideoIdsMigration:
    """Exercises the 0018 data-migration function against current models.

    Choices are not DB-enforced, so corrupt rows can be created directly the
    same way they existed before the migration ran.
    """

    def _run_repair(self):
        from django.apps import apps as global_apps
        migration = import_module('courses.migrations.0018_repair_video_ids')
        migration.repair_video_ids(global_apps, None)

    def test_url_shaped_video_id_gets_normalized(self, lesson):
        Lesson.objects.filter(pk=lesson.pk).update(
            video_type='youtube',
            video_id='https://www.youtube.com/watch?v=dQw4w9WgXcQ')
        self._run_repair()
        lesson.refresh_from_db()
        assert lesson.video_type == 'youtube'
        assert lesson.video_id == 'dQw4w9WgXcQ'

    def test_garbage_video_id_gets_nulled(self, lesson):
        Lesson.objects.filter(pk=lesson.pk).update(
            video_type='youtube', video_id='https://example.com/nope')
        section = LessonSection.objects.create(
            lesson=lesson, title='Bad', order=0)
        LessonSection.objects.filter(pk=section.pk).update(
            video_type='youtube', video_id='total garbage')
        self._run_repair()
        lesson.refresh_from_db()
        section.refresh_from_db()
        assert (lesson.video_type, lesson.video_id) == ('none', '')
        assert (section.video_type, section.video_id) == ('none', '')

    def test_vimeo_rows_cleared(self, lesson):
        Lesson.objects.filter(pk=lesson.pk).update(
            video_type='vimeo', video_id='123456789')
        self._run_repair()
        lesson.refresh_from_db()
        assert (lesson.video_type, lesson.video_id) == ('none', '')

    def test_valid_rows_untouched(self, lesson):
        Lesson.objects.filter(pk=lesson.pk).update(
            video_type='youtube', video_id='dQw4w9WgXcQ')
        self._run_repair()
        lesson.refresh_from_db()
        assert (lesson.video_type, lesson.video_id) == ('youtube', 'dQw4w9WgXcQ')


@pytest.mark.django_db
class TestConsolidateContentIntoSectionsMigration:
    """Exercises the 0019 data-migration function against current models.

    Phase 53: lesson-level content/video is consolidated into sections. The
    migration copies content into a first section only when the lesson has no
    sections, then blanks the (now dormant) lesson-level fields on every lesson.
    """

    def _run_consolidate(self):
        from django.apps import apps as global_apps
        migration = import_module(
            'courses.migrations.0019_consolidate_lesson_content_into_sections')
        migration.consolidate_content_into_sections(global_apps, None)

    def test_no_section_lesson_with_content_and_video_becomes_a_section(self, unit):
        lesson = Lesson.objects.create(
            unit=unit, title='L', order=1,
            content='# Hello\n\nBody text.',
            video_type='youtube', video_id='dQw4w9WgXcQ')

        self._run_consolidate()

        lesson.refresh_from_db()
        sections = list(lesson.sections.all())
        assert len(sections) == 1
        s = sections[0]
        assert s.order == 0
        assert s.title == ''
        assert s.content == '# Hello\n\nBody text.'
        assert (s.video_type, s.video_id) == ('youtube', 'dQw4w9WgXcQ')
        # Lesson-level fields are now blanked/dormant.
        assert (lesson.content, lesson.video_type, lesson.video_id) == ('', 'none', '')

    def test_no_section_lesson_with_only_video_carries_video(self, unit):
        lesson = Lesson.objects.create(
            unit=unit, title='L', order=1, content='',
            video_type='youtube', video_id='dQw4w9WgXcQ')

        self._run_consolidate()

        lesson.refresh_from_db()
        sections = list(lesson.sections.all())
        assert len(sections) == 1
        assert sections[0].content == ''
        assert (sections[0].video_type, sections[0].video_id) == ('youtube', 'dQw4w9WgXcQ')
        assert (lesson.content, lesson.video_type, lesson.video_id) == ('', 'none', '')

    def test_lesson_with_existing_sections_keeps_sections_and_discards_hidden_content(self, unit):
        lesson = Lesson.objects.create(
            unit=unit, title='L', order=1,
            content='hidden leftover blob',
            video_type='youtube', video_id='dQw4w9WgXcQ')
        LessonSection.objects.create(
            lesson=lesson, title='Real 0', content='real body', order=0)
        LessonSection.objects.create(
            lesson=lesson, title='Real 1', content='more', order=1)

        self._run_consolidate()

        lesson.refresh_from_db()
        sections = list(lesson.sections.order_by('order'))
        # No new section created; existing ones untouched.
        assert [s.title for s in sections] == ['Real 0', 'Real 1']
        assert [s.content for s in sections] == ['real body', 'more']
        # The hidden lesson-level content is discarded.
        assert (lesson.content, lesson.video_type, lesson.video_id) == ('', 'none', '')

    def test_empty_lesson_is_untouched(self, unit):
        lesson = Lesson.objects.create(
            unit=unit, title='Empty', order=1,
            content='', video_type='none', video_id='')

        self._run_consolidate()

        lesson.refresh_from_db()
        assert lesson.sections.count() == 0
        assert (lesson.content, lesson.video_type, lesson.video_id) == ('', 'none', '')


@pytest.mark.django_db
class TestRequiredQuizRetired:
    """Phase 54: the cross-course `required_quiz` gate (System A) is retired.

    The FK is no longer a writable serializer field, so any attempt to set it via
    the API is silently ignored (the column stays dormant). This supersedes the
    Phase-53 IDOR-scoping tests — with no writable field there is no IDOR surface.
    """

    def test_setting_required_quiz_via_api_is_ignored(
        self, api_client, instructor, unit, lesson
    ):
        from quizzes.models import Quiz
        quiz = Quiz.objects.create(unit=unit, title='Some Quiz')

        api_client.force_authenticate(user=instructor)
        resp = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/',
            {'required_quiz': quiz.id}, format='json')

        # Accepted (unknown write field ignored), but the FK is not set.
        assert resp.status_code == status.HTTP_200_OK
        lesson.refresh_from_db()
        assert lesson.required_quiz_id is None

    def test_requires_quiz_is_writable(self, api_client, instructor, lesson):
        api_client.force_authenticate(user=instructor)
        resp = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/',
            {'requires_quiz': True}, format='json')

        assert resp.status_code == status.HTTP_200_OK
        lesson.refresh_from_db()
        assert lesson.requires_quiz is True
