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


# ---------------------------------------------------------------------------
# Phase 32: Mastery session flow (Duolingo-style)
# ---------------------------------------------------------------------------


@pytest.fixture
def two_question_quiz(quiz):
    """Quiz with two questions, one correct choice each. passing_score=70."""
    for i in (1, 2):
        question = Question.objects.create(quiz=quiz, text=f'Session Q{i}', order=i)
        Choice.objects.create(question=question, text='Right', is_correct=True, order=1)
        Choice.objects.create(question=question, text='Wrong', is_correct=False, order=2)
    return quiz


def _session_answer(client, quiz, question, correct):
    choice = question.choices.get(is_correct=correct)
    return client.post(
        f'/api/quizzes/{quiz.id}/session/answer/',
        {'question_id': question.id, 'choice_id': choice.id},
        format='json',
    )


@pytest.mark.django_db
class TestQuizSessionPermissions:
    """Boundary trio (unauth 401 / instructor 403 / unenrolled 403) per route."""

    ROUTES = [
        ('post', 'session/start/'),
        ('get', 'session/'),
        ('post', 'session/answer/'),
    ]

    @pytest.mark.parametrize('method,suffix', ROUTES)
    def test_unauthenticated_401(self, api_client, two_question_quiz, method, suffix):
        response = getattr(api_client, method)(f'/api/quizzes/{two_question_quiz.id}/{suffix}')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize('method,suffix', ROUTES)
    def test_instructor_403(self, api_client, instructor, two_question_quiz, method, suffix):
        api_client.force_authenticate(user=instructor)
        response = getattr(api_client, method)(f'/api/quizzes/{two_question_quiz.id}/{suffix}')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data

    @pytest.mark.parametrize('method,suffix', ROUTES)
    def test_unenrolled_student_403(self, api_client, student, two_question_quiz, method, suffix):
        api_client.force_authenticate(user=student)
        response = getattr(api_client, method)(f'/api/quizzes/{two_question_quiz.id}/{suffix}')
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestQuizSessionFlow:
    def test_start_no_questions_400(self, api_client, student, quiz, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/quizzes/{quiz.id}/session/start/')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_start_creates_in_progress_session(self, api_client, student, two_question_quiz, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/quizzes/{two_question_quiz.id}/session/start/')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['status'] == 'in_progress'
        assert response.data['total_questions'] == 2
        assert response.data['mastered_count'] == 0
        assert len(response.data['remaining_question_ids']) == 2
        attempt = QuizAttempt.objects.get(id=response.data['attempt_id'])
        assert attempt.status == QuizAttempt.STATUS_IN_PROGRESS
        assert attempt.completed_at is None

    def test_start_resumes_existing_session(self, api_client, student, two_question_quiz, enrollment):
        api_client.force_authenticate(user=student)
        first = api_client.post(f'/api/quizzes/{two_question_quiz.id}/session/start/')
        second = api_client.post(f'/api/quizzes/{two_question_quiz.id}/session/start/')
        assert second.status_code == status.HTTP_200_OK
        assert second.data['attempt_id'] == first.data['attempt_id']
        assert QuizAttempt.objects.filter(quiz=two_question_quiz, student=student).count() == 1

    def test_get_session_404_when_none(self, api_client, student, two_question_quiz, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/quizzes/{two_question_quiz.id}/session/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_session_returns_resume_state(self, api_client, student, two_question_quiz, enrollment):
        api_client.force_authenticate(user=student)
        api_client.post(f'/api/quizzes/{two_question_quiz.id}/session/start/')
        q1, q2 = two_question_quiz.questions.all()
        _session_answer(api_client, two_question_quiz, q1, correct=False)

        response = api_client.get(f'/api/quizzes/{two_question_quiz.id}/session/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['answered_count'] == 1
        assert response.data['mastered_count'] == 0
        # q2 (unanswered) queues before the re-queued missed q1
        assert response.data['remaining_question_ids'] == [q2.id, q1.id]
        by_id = {s['question_id']: s for s in response.data['questions']}
        assert by_id[q1.id]['answered'] is True
        assert by_id[q1.id]['first_try_correct'] is False
        assert by_id[q1.id]['mastered'] is False

    def test_abandoned_session_does_not_burn_attempt(self, api_client, student, two_question_quiz, enrollment):
        two_question_quiz.max_attempts = 1
        two_question_quiz.save()
        api_client.force_authenticate(user=student)
        first = api_client.post(f'/api/quizzes/{two_question_quiz.id}/session/start/')
        assert first.status_code == status.HTTP_201_CREATED
        # Abandon and come back: resumes instead of a max-attempts 400.
        again = api_client.post(f'/api/quizzes/{two_question_quiz.id}/session/start/')
        assert again.status_code == status.HTTP_200_OK
        assert again.data['attempt_id'] == first.data['attempt_id']

    def test_start_respects_max_attempts_completed_only(self, api_client, student, two_question_quiz, enrollment):
        two_question_quiz.max_attempts = 1
        two_question_quiz.save()
        api_client.force_authenticate(user=student)
        api_client.post(f'/api/quizzes/{two_question_quiz.id}/session/start/')
        for question in two_question_quiz.questions.all():
            _session_answer(api_client, two_question_quiz, question, correct=True)

        blocked = api_client.post(f'/api/quizzes/{two_question_quiz.id}/session/start/')
        assert blocked.status_code == status.HTTP_400_BAD_REQUEST
        assert 'maximum number of attempts' in blocked.data['detail']

    def test_wrong_then_correct_masters_but_scores_zero(self, api_client, student, two_question_quiz, enrollment):
        api_client.force_authenticate(user=student)
        api_client.post(f'/api/quizzes/{two_question_quiz.id}/session/start/')
        q1, q2 = two_question_quiz.questions.all()

        miss = _session_answer(api_client, two_question_quiz, q1, correct=False)
        assert miss.status_code == status.HTTP_200_OK
        assert miss.data['is_correct'] is False
        assert miss.data['correct_choice_id'] == q1.choices.get(is_correct=True).id
        assert miss.data['remaining_count'] == 2
        assert miss.data['session_complete'] is False

        _session_answer(api_client, two_question_quiz, q2, correct=True)
        retry = _session_answer(api_client, two_question_quiz, q1, correct=True)
        assert retry.data['is_correct'] is True
        assert retry.data['session_complete'] is True

        # First-try record preserved: q1 wrong, mastered anyway. Score = 50%.
        attempt = QuizAttempt.objects.get(quiz=two_question_quiz, student=student)
        answer_q1 = attempt.answers.get(question=q1)
        assert answer_q1.is_correct is False
        assert answer_q1.mastered_at is not None
        assert attempt.status == QuizAttempt.STATUS_COMPLETED
        assert float(attempt.score) == 50.0
        assert attempt.passed is False  # below passing_score=70

        result = retry.data['result']
        assert result['score'] == '50.00'
        assert result['passed'] is False
        assert 'gamification' not in result

    def test_finalize_pass_awards_xp_once(self, api_client, student, two_question_quiz, enrollment):
        api_client.force_authenticate(user=student)
        api_client.post(f'/api/quizzes/{two_question_quiz.id}/session/start/')
        last = None
        for question in two_question_quiz.questions.all():
            last = _session_answer(api_client, two_question_quiz, question, correct=True)

        result = last.data['result']
        assert result['score'] == '100.00'
        assert result['passed'] is True
        assert result['gamification']['xp_awarded'] == 20

        # Re-pass on a fresh session: no double XP.
        api_client.post(f'/api/quizzes/{two_question_quiz.id}/session/start/')
        for question in two_question_quiz.questions.all():
            last = _session_answer(api_client, two_question_quiz, question, correct=True)
        assert last.data['result']['gamification']['xp_awarded'] == 0

    def test_mastered_below_passing_allows_retake(self, api_client, student, two_question_quiz, enrollment):
        two_question_quiz.max_attempts = 2
        two_question_quiz.save()
        api_client.force_authenticate(user=student)
        api_client.post(f'/api/quizzes/{two_question_quiz.id}/session/start/')
        q1, q2 = two_question_quiz.questions.all()
        _session_answer(api_client, two_question_quiz, q1, correct=False)
        _session_answer(api_client, two_question_quiz, q2, correct=False)
        _session_answer(api_client, two_question_quiz, q1, correct=True)
        final = _session_answer(api_client, two_question_quiz, q2, correct=True)
        assert final.data['result']['passed'] is False

        # Mastered-but-failed: a retake is still allowed (1 of 2 used).
        retake = api_client.post(f'/api/quizzes/{two_question_quiz.id}/session/start/')
        assert retake.status_code == status.HTTP_201_CREATED

    def test_answer_rejects_foreign_and_mastered_questions(self, api_client, student, instructor, two_question_quiz, enrollment):
        api_client.force_authenticate(user=student)
        api_client.post(f'/api/quizzes/{two_question_quiz.id}/session/start/')
        q1 = two_question_quiz.questions.first()

        # Question from another quiz
        other_quiz = Quiz.objects.create(
            unit=two_question_quiz.unit, title='Other', passing_score=70, order=9
        )
        foreign_q = Question.objects.create(quiz=other_quiz, text='Foreign', order=1)
        foreign_c = Choice.objects.create(question=foreign_q, text='X', is_correct=True, order=1)
        response = api_client.post(
            f'/api/quizzes/{two_question_quiz.id}/session/answer/',
            {'question_id': foreign_q.id, 'choice_id': foreign_c.id}, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Already-mastered question
        _session_answer(api_client, two_question_quiz, q1, correct=True)
        again = _session_answer(api_client, two_question_quiz, q1, correct=True)
        assert again.status_code == status.HTTP_400_BAD_REQUEST

    def test_answer_without_session_400(self, api_client, student, two_question_quiz, enrollment):
        api_client.force_authenticate(user=student)
        q1 = two_question_quiz.questions.first()
        response = _session_answer(api_client, two_question_quiz, q1, correct=True)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_in_progress_ignored_by_best_score_and_attempts(self, api_client, student, two_question_quiz, enrollment):
        two_question_quiz.max_attempts = 3
        two_question_quiz.save()
        api_client.force_authenticate(user=student)
        api_client.post(f'/api/quizzes/{two_question_quiz.id}/session/start/')
        q1 = two_question_quiz.questions.first()
        _session_answer(api_client, two_question_quiz, q1, correct=True)

        detail = api_client.get(f'/api/quizzes/{two_question_quiz.id}/')
        assert detail.data['best_score'] is None
        assert detail.data['attempt_count'] == 0
        assert detail.data['attempts_remaining'] == 3

        history = api_client.get(f'/api/quizzes/{two_question_quiz.id}/attempts/')
        assert history.data == []
