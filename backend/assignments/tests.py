import pytest
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient
from accounts.models import User
from courses.models import Course, Unit, Enrollment
from .models import Assignment, Submission, Grade


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
def student2():
    return User.objects.create_user(
        email='student2@test.com',
        password='testpass123',
        first_name='Another',
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
        description='Learn game dev basics.',
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
def assignment(unit):
    return Assignment.objects.create(
        unit=unit,
        title='First Assignment',
        description='Complete this assignment.',
        max_points=100,
        due_date=timezone.now() + timedelta(days=7),
        order=1
    )


@pytest.fixture
def enrollment(student, course):
    return Enrollment.objects.create(user=student, course=course)


@pytest.mark.django_db
class TestAssignmentModel:
    def test_create_assignment(self, unit):
        assignment = Assignment.objects.create(
            unit=unit,
            title='Test Assignment',
            max_points=50
        )
        assert assignment.title == 'Test Assignment'
        assert assignment.max_points == 50
        assert assignment.course == unit.course

    def test_submission_is_late(self, assignment, student):
        # On time
        assignment.due_date = timezone.now() + timedelta(hours=1)
        assignment.save()

        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            content='My work',
            status='submitted',
            submitted_at=timezone.now()
        )
        assert submission.is_late is False

        # Late
        assignment.due_date = timezone.now() - timedelta(hours=1)
        assignment.save()
        submission.submitted_at = timezone.now()
        submission.save()
        assert submission.is_late is True


@pytest.mark.django_db
class TestAssignmentEndpoints:
    def test_list_course_assignments(self, api_client, student, course, unit, assignment, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/assignments/courses/{course.code}/assignments/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['title'] == 'First Assignment'

    def test_list_assignments_unauthenticated(self, api_client, course):
        response = api_client.get(f'/api/assignments/courses/{course.code}/assignments/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_assignments_not_enrolled(self, api_client, student, course, unit, assignment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/assignments/courses/{course.code}/assignments/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data

    def test_create_assignment_as_instructor(self, api_client, instructor, unit):
        api_client.force_authenticate(user=instructor)
        response = api_client.post(f'/api/assignments/units/{unit.id}/assignments/', {
            'title': 'New Assignment',
            'description': 'Instructions here',
            'max_points': 50
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'New Assignment'

    def test_create_assignment_as_student_fails(self, api_client, student, unit, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/assignments/units/{unit.id}/assignments/', {
            'title': 'New Assignment'
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_assignment_detail(self, api_client, student, assignment, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/assignments/assignments/{assignment.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'First Assignment'
        assert response.data['max_points'] == 100

    def test_update_assignment_as_instructor(self, api_client, instructor, assignment):
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(f'/api/assignments/assignments/{assignment.id}/', {
            'max_points': 150
        })
        assert response.status_code == status.HTTP_200_OK
        assert response.data['max_points'] == 150

    def test_delete_assignment_as_instructor(self, api_client, instructor, assignment):
        api_client.force_authenticate(user=instructor)
        response = api_client.delete(f'/api/assignments/assignments/{assignment.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Assignment.objects.filter(id=assignment.id).exists()


@pytest.mark.django_db
class TestSubmissions:
    def test_get_my_submission_creates_draft(self, api_client, student, assignment, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/assignments/assignments/{assignment.id}/my-submission/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'draft'
        assert Submission.objects.filter(student=student, assignment=assignment).exists()

    def test_update_submission(self, api_client, student, assignment, enrollment):
        api_client.force_authenticate(user=student)
        # First get to create draft
        api_client.get(f'/api/assignments/assignments/{assignment.id}/my-submission/')

        # Update content
        response = api_client.patch(f'/api/assignments/assignments/{assignment.id}/my-submission/', {
            'content': 'My work here'
        })
        assert response.status_code == status.HTTP_200_OK
        assert response.data['content'] == 'My work here'

    def test_submit_assignment(self, api_client, student, assignment, enrollment):
        api_client.force_authenticate(user=student)
        # Create and update submission
        api_client.get(f'/api/assignments/assignments/{assignment.id}/my-submission/')
        api_client.patch(f'/api/assignments/assignments/{assignment.id}/my-submission/', {
            'content': 'Completed work'
        })

        # Submit
        response = api_client.post(f'/api/assignments/assignments/{assignment.id}/submit/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'submitted'
        assert response.data['submitted_at'] is not None

    def test_submit_empty_fails(self, api_client, student, assignment, enrollment):
        api_client.force_authenticate(user=student)
        # Create draft without content
        api_client.get(f'/api/assignments/assignments/{assignment.id}/my-submission/')

        response = api_client.post(f'/api/assignments/assignments/{assignment.id}/submit/')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_modify_submitted(self, api_client, student, assignment, enrollment):
        api_client.force_authenticate(user=student)
        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            content='Work',
            status='submitted',
            submitted_at=timezone.now()
        )

        response = api_client.patch(f'/api/assignments/assignments/{assignment.id}/my-submission/', {
            'content': 'Changed'
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_submission_not_enrolled_fails(self, api_client, student, assignment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/assignments/assignments/{assignment.id}/my-submission/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestGrading:
    def test_instructor_list_submissions(self, api_client, instructor, student, assignment, enrollment):
        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            content='My work',
            status='submitted',
            submitted_at=timezone.now()
        )

        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/assignments/assignments/{assignment.id}/submissions/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['student_email'] == 'student@test.com'

    def test_student_cannot_list_submissions(self, api_client, student, assignment, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/assignments/assignments/{assignment.id}/submissions/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data

    def test_grade_submission(self, api_client, instructor, student, assignment, enrollment):
        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            content='My work',
            status='submitted',
            submitted_at=timezone.now()
        )

        api_client.force_authenticate(user=instructor)
        response = api_client.post(f'/api/assignments/submissions/{submission.id}/grade/', {
            'points': 85,
            'feedback': 'Good work!'
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['status'] == 'graded'
        assert response.data['grade']['points'] == 85
        assert response.data['grade']['feedback'] == 'Good work!'

    def test_update_grade(self, api_client, instructor, student, assignment, enrollment):
        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            content='My work',
            status='submitted',
            submitted_at=timezone.now()
        )
        Grade.objects.create(
            submission=submission,
            grader=instructor,
            points=70,
            feedback='Initial'
        )
        submission.status = 'graded'
        submission.save()

        api_client.force_authenticate(user=instructor)
        response = api_client.put(f'/api/assignments/submissions/{submission.id}/grade/', {
            'points': 80,
            'feedback': 'Updated feedback'
        })
        assert response.status_code == status.HTTP_200_OK
        assert response.data['grade']['points'] == 80

    def test_grade_exceeds_max_fails(self, api_client, instructor, student, assignment, enrollment):
        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            content='My work',
            status='submitted',
            submitted_at=timezone.now()
        )

        api_client.force_authenticate(user=instructor)
        response = api_client.post(f'/api/assignments/submissions/{submission.id}/grade/', {
            'points': 150,  # Max is 100
            'feedback': 'Too high'
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_student_cannot_grade(self, api_client, student, student2, assignment, enrollment):
        Enrollment.objects.create(user=student2, course=assignment.course)
        submission = Submission.objects.create(
            assignment=assignment,
            student=student2,
            content='Work',
            status='submitted',
            submitted_at=timezone.now()
        )

        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/assignments/submissions/{submission.id}/grade/', {
            'points': 50
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_grade_draft(self, api_client, instructor, student, assignment, enrollment):
        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            content='Draft work',
            status='draft'
        )

        api_client.force_authenticate(user=instructor)
        response = api_client.post(f'/api/assignments/submissions/{submission.id}/grade/', {
            'points': 50
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLateSubmissions:
    def test_submit_after_due_date_allowed(self, api_client, student, assignment, enrollment):
        assignment.due_date = timezone.now() - timedelta(hours=1)
        assignment.allow_late = True
        assignment.save()

        api_client.force_authenticate(user=student)
        api_client.get(f'/api/assignments/assignments/{assignment.id}/my-submission/')
        api_client.patch(f'/api/assignments/assignments/{assignment.id}/my-submission/', {
            'content': 'Late work'
        })

        response = api_client.post(f'/api/assignments/assignments/{assignment.id}/submit/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_late'] is True

    def test_submit_after_due_date_blocked(self, api_client, student, assignment, enrollment):
        assignment.due_date = timezone.now() - timedelta(hours=1)
        assignment.allow_late = False
        assignment.save()

        api_client.force_authenticate(user=student)
        api_client.get(f'/api/assignments/assignments/{assignment.id}/my-submission/')
        api_client.patch(f'/api/assignments/assignments/{assignment.id}/my-submission/', {
            'content': 'Late work'
        })

        response = api_client.post(f'/api/assignments/assignments/{assignment.id}/submit/')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestQuickGrade:
    """Tests for quick grade endpoint."""

    def test_quick_grade_creates_submission_and_grade(self, api_client, instructor, student, unit, enrollment):
        """Test quick grade creates submission if none exists."""
        from .models import Assignment, Submission, Grade

        assignment = Assignment.objects.create(
            unit=unit,
            title='Test Assignment',
            max_points=100
        )

        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/assignments/assignments/{assignment.id}/quick-grade/{student.id}/',
            {'points': 85},
            format='json'
        )

        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['points'] == 85

        # Verify submission was created
        submission = Submission.objects.get(assignment=assignment, student=student)
        assert submission.status == 'graded'
        assert submission.grade.points == 85

    def test_quick_grade_updates_existing_grade(self, api_client, instructor, student, unit, enrollment):
        """Test quick grade updates existing submission."""
        from .models import Assignment, Submission, Grade

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
            grader=instructor,
            points=70
        )

        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/assignments/assignments/{assignment.id}/quick-grade/{student.id}/',
            {'points': 90},
            format='json'
        )

        assert response.status_code == 200

        # Verify grade was updated
        submission.refresh_from_db()
        assert submission.grade.points == 90

    def test_quick_grade_student_forbidden(self, api_client, student, instructor, unit, enrollment):
        """Test students cannot use quick grade."""
        from .models import Assignment

        assignment = Assignment.objects.create(
            unit=unit,
            title='Test Assignment',
            max_points=100
        )

        api_client.force_authenticate(user=student)
        response = api_client.post(
            f'/api/assignments/assignments/{assignment.id}/quick-grade/{student.id}/',
            {'points': 100},
            format='json'
        )

        assert response.status_code == 403

    def test_quick_grade_invalid_points(self, api_client, instructor, student, unit, enrollment):
        """Test quick grade rejects invalid points."""
        from .models import Assignment

        assignment = Assignment.objects.create(
            unit=unit,
            title='Test Assignment',
            max_points=100
        )

        api_client.force_authenticate(user=instructor)

        # Points too high
        response = api_client.post(
            f'/api/assignments/assignments/{assignment.id}/quick-grade/{student.id}/',
            {'points': 150},
            format='json'
        )
        assert response.status_code == 400

        # Negative points
        response = api_client.post(
            f'/api/assignments/assignments/{assignment.id}/quick-grade/{student.id}/',
            {'points': -10},
            format='json'
        )
        assert response.status_code == 400

    def test_quick_grade_not_enrolled_student(self, api_client, instructor, unit):
        """Test quick grade fails for non-enrolled student."""
        from .models import Assignment
        from accounts.models import User

        assignment = Assignment.objects.create(
            unit=unit,
            title='Test Assignment',
            max_points=100
        )

        # Create a user who is not enrolled
        other_student = User.objects.create_user(
            email='other@test.com',
            password='testpass123'
        )

        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/assignments/assignments/{assignment.id}/quick-grade/{other_student.id}/',
            {'points': 80},
            format='json'
        )

        assert response.status_code == 404

    def test_quick_grade_converts_draft_to_graded(self, api_client, instructor, student, unit, enrollment):
        """Test quick grade converts draft submission to graded."""
        from .models import Assignment, Submission

        assignment = Assignment.objects.create(
            unit=unit,
            title='Test Assignment',
            max_points=100
        )

        # Create draft submission
        Submission.objects.create(
            assignment=assignment,
            student=student,
            status='draft',
            content='Draft content'
        )

        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/assignments/assignments/{assignment.id}/quick-grade/{student.id}/',
            {'points': 75},
            format='json'
        )

        assert response.status_code == 200

        submission = Submission.objects.get(assignment=assignment, student=student)
        assert submission.status == 'graded'
        assert submission.submitted_at is not None
