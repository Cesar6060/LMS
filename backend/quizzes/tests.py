import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from accounts.models import User
from courses.models import Course, Unit, Enrollment
from .models import Quiz, Question, Choice, QuizAttempt


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def instructor():
    return User.objects.create_user(
        email='instructor@test.com',
        password='testpass123',
        is_instructor=True
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        email='student@test.com',
        password='testpass123',
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


@pytest.fixture
def unit(course):
    return Unit.objects.create(
        course=course,
        title='Test Unit',
        order=1
    )


@pytest.fixture
def enrollment(student, course):
    return Enrollment.objects.create(user=student, course=course)


@pytest.fixture
def quiz(unit):
    return Quiz.objects.create(
        unit=unit,
        title='Test Quiz',
        description='A test quiz',
        passing_score=70,
        points=10,
        order=1
    )


@pytest.fixture
def question_with_choices(quiz):
    question = Question.objects.create(
        quiz=quiz,
        text='What is 2 + 2?',
        order=1
    )
    Choice.objects.create(question=question, text='3', is_correct=False, order=1)
    Choice.objects.create(question=question, text='4', is_correct=True, order=2)
    Choice.objects.create(question=question, text='5', is_correct=False, order=3)
    return question


@pytest.mark.django_db
class TestQuizCRUD:
    def test_list_quizzes_instructor(self, api_client, instructor, unit, quiz):
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/units/{unit.id}/quizzes/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['title'] == 'Test Quiz'

    def test_list_quizzes_enrolled_student(self, api_client, student, unit, quiz, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/units/{unit.id}/quizzes/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_list_quizzes_not_enrolled(self, api_client, student, unit, quiz):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/units/{unit.id}/quizzes/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_quiz_instructor(self, api_client, instructor, unit):
        api_client.force_authenticate(user=instructor)
        data = {
            'title': 'New Quiz',
            'description': 'A new quiz',
            'passing_score': 80,
            'points': 20
        }
        response = api_client.post(f'/api/units/{unit.id}/quizzes/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'New Quiz'
        assert response.data['passing_score'] == 80

    def test_create_quiz_student_forbidden(self, api_client, student, unit, enrollment):
        api_client.force_authenticate(user=student)
        data = {'title': 'New Quiz', 'passing_score': 70, 'points': 10}
        response = api_client.post(f'/api/units/{unit.id}/quizzes/', data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_quiz_detail_instructor(self, api_client, instructor, quiz, question_with_choices):
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/quizzes/{quiz.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Test Quiz'
        # Instructor should see correct answers
        assert 'questions' in response.data
        assert len(response.data['questions']) == 1
        assert any(c['is_correct'] for c in response.data['questions'][0]['choices'])

    def test_get_quiz_detail_student_hides_answers(self, api_client, student, quiz, question_with_choices, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/quizzes/{quiz.id}/')
        assert response.status_code == status.HTTP_200_OK
        # Student should NOT see is_correct field
        for question in response.data['questions']:
            for choice in question['choices']:
                assert 'is_correct' not in choice

    def test_update_quiz(self, api_client, instructor, quiz):
        api_client.force_authenticate(user=instructor)
        data = {'title': 'Updated Quiz', 'passing_score': 75}
        response = api_client.put(f'/api/quizzes/{quiz.id}/', data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Updated Quiz'
        assert response.data['passing_score'] == 75

    def test_delete_quiz(self, api_client, instructor, quiz):
        api_client.force_authenticate(user=instructor)
        response = api_client.delete(f'/api/quizzes/{quiz.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Quiz.objects.filter(id=quiz.id).exists()


@pytest.mark.django_db
class TestQuestionCRUD:
    def test_add_question(self, api_client, instructor, quiz):
        api_client.force_authenticate(user=instructor)
        data = {
            'text': 'What is the capital of France?',
            'choices': [
                {'text': 'London', 'is_correct': False},
                {'text': 'Paris', 'is_correct': True},
                {'text': 'Berlin', 'is_correct': False}
            ]
        }
        response = api_client.post(f'/api/quizzes/{quiz.id}/questions/', data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['text'] == 'What is the capital of France?'
        assert len(response.data['choices']) == 3

    def test_update_question(self, api_client, instructor, question_with_choices):
        api_client.force_authenticate(user=instructor)
        data = {
            'text': 'Updated question?',
            'choices': [
                {'text': 'A', 'is_correct': True},
                {'text': 'B', 'is_correct': False}
            ]
        }
        response = api_client.put(f'/api/questions/{question_with_choices.id}/', data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['text'] == 'Updated question?'
        assert len(response.data['choices']) == 2

    def test_delete_question(self, api_client, instructor, question_with_choices):
        api_client.force_authenticate(user=instructor)
        response = api_client.delete(f'/api/questions/{question_with_choices.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestQuizSubmission:
    def test_submit_quiz_correct_answer(self, api_client, student, quiz, question_with_choices, enrollment):
        api_client.force_authenticate(user=student)
        correct_choice = question_with_choices.choices.get(is_correct=True)
        data = {
            'answers': {
                str(question_with_choices.id): correct_choice.id
            }
        }
        response = api_client.post(f'/api/quizzes/{quiz.id}/submit/', data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['score'] == '100.00'
        assert response.data['passed'] is True
        assert len(response.data['answers']) == 1
        assert response.data['answers'][0]['is_correct'] is True

    def test_submit_quiz_wrong_answer(self, api_client, student, quiz, question_with_choices, enrollment):
        api_client.force_authenticate(user=student)
        wrong_choice = question_with_choices.choices.filter(is_correct=False).first()
        data = {
            'answers': {
                str(question_with_choices.id): wrong_choice.id
            }
        }
        response = api_client.post(f'/api/quizzes/{quiz.id}/submit/', data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['score'] == '0.00'
        assert response.data['passed'] is False

    def test_submit_quiz_not_enrolled(self, api_client, student, quiz, question_with_choices):
        api_client.force_authenticate(user=student)
        data = {'answers': {}}
        response = api_client.post(f'/api/quizzes/{quiz.id}/submit/', data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_submit_quiz_no_questions(self, api_client, student, quiz, enrollment):
        api_client.force_authenticate(user=student)
        data = {'answers': {}}
        response = api_client.post(f'/api/quizzes/{quiz.id}/submit/', data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_multiple_attempts_allowed(self, api_client, student, quiz, question_with_choices, enrollment):
        api_client.force_authenticate(user=student)
        correct_choice = question_with_choices.choices.get(is_correct=True)
        data = {'answers': {str(question_with_choices.id): correct_choice.id}}

        # First attempt
        response1 = api_client.post(f'/api/quizzes/{quiz.id}/submit/', data, format='json')
        assert response1.status_code == status.HTTP_201_CREATED

        # Second attempt
        response2 = api_client.post(f'/api/quizzes/{quiz.id}/submit/', data, format='json')
        assert response2.status_code == status.HTTP_201_CREATED

        # Should have 2 attempts
        attempts = QuizAttempt.objects.filter(quiz=quiz, student=student)
        assert attempts.count() == 2

    def test_max_attempts_enforced(self, api_client, student, quiz, question_with_choices, enrollment):
        # Set max attempts to 2
        quiz.max_attempts = 2
        quiz.save()

        api_client.force_authenticate(user=student)
        correct_choice = question_with_choices.choices.get(is_correct=True)
        data = {'answers': {str(question_with_choices.id): correct_choice.id}}

        # First attempt
        response1 = api_client.post(f'/api/quizzes/{quiz.id}/submit/', data, format='json')
        assert response1.status_code == status.HTTP_201_CREATED

        # Second attempt
        response2 = api_client.post(f'/api/quizzes/{quiz.id}/submit/', data, format='json')
        assert response2.status_code == status.HTTP_201_CREATED

        # Third attempt should be blocked
        response3 = api_client.post(f'/api/quizzes/{quiz.id}/submit/', data, format='json')
        assert response3.status_code == status.HTTP_400_BAD_REQUEST
        assert 'maximum number of attempts' in response3.data['detail']

    def test_unlimited_attempts_when_zero(self, api_client, student, quiz, question_with_choices, enrollment):
        # Ensure max_attempts is 0 (unlimited)
        quiz.max_attempts = 0
        quiz.save()

        api_client.force_authenticate(user=student)
        correct_choice = question_with_choices.choices.get(is_correct=True)
        data = {'answers': {str(question_with_choices.id): correct_choice.id}}

        # Multiple attempts should all work
        for _ in range(5):
            response = api_client.post(f'/api/quizzes/{quiz.id}/submit/', data, format='json')
            assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestQuizAttempts:
    def test_list_my_attempts(self, api_client, student, quiz, question_with_choices, enrollment):
        api_client.force_authenticate(user=student)
        # Create an attempt
        correct_choice = question_with_choices.choices.get(is_correct=True)
        api_client.post(
            f'/api/quizzes/{quiz.id}/submit/',
            {'answers': {str(question_with_choices.id): correct_choice.id}},
            format='json'
        )

        response = api_client.get(f'/api/quizzes/{quiz.id}/attempts/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_instructor_sees_all_attempts(self, api_client, instructor, student, quiz, question_with_choices, enrollment):
        # Student makes an attempt
        api_client.force_authenticate(user=student)
        correct_choice = question_with_choices.choices.get(is_correct=True)
        api_client.post(
            f'/api/quizzes/{quiz.id}/submit/',
            {'answers': {str(question_with_choices.id): correct_choice.id}},
            format='json'
        )

        # Instructor views attempts
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/quizzes/{quiz.id}/attempts/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1


@pytest.mark.django_db
class TestCourseQuizzes:
    def test_list_course_quizzes(self, api_client, instructor, course, unit, quiz):
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/{course.code}/quizzes/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['title'] == 'Test Quiz'


@pytest.mark.django_db
class TestQuizPermissionBoundaries:
    """Phase 14: previously untested quiz permission gaps."""

    @pytest.fixture
    def other_instructor(self):
        return User.objects.create_user(
            email='other.instructor@test.com',
            password='testpass123',
            is_instructor=True
        )

    def test_question_detail_student_forbidden(self, api_client, student, enrollment, question_with_choices):
        api_client.force_authenticate(user=student)
        response = api_client.put(
            f'/api/questions/{question_with_choices.id}/',
            {'text': 'Hijacked?'}, format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data

    def test_question_delete_student_forbidden(self, api_client, student, enrollment, question_with_choices):
        api_client.force_authenticate(user=student)
        response = api_client.delete(f'/api/questions/{question_with_choices.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_quick_grade_student_forbidden(self, api_client, student, enrollment, quiz):
        api_client.force_authenticate(user=student)
        response = api_client.post(
            f'/api/quizzes/{quiz.id}/quick-grade/{student.id}/', {'points': 10}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data

    def test_quick_grade_other_instructor_forbidden(self, api_client, other_instructor, student, enrollment, quiz):
        api_client.force_authenticate(user=other_instructor)
        response = api_client.post(
            f'/api/quizzes/{quiz.id}/quick-grade/{student.id}/', {'points': 10}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data
