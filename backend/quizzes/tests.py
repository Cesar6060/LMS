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


# ===========================================================================
# Phase 63 — query-count and shape guards for the N+1 rewrite
# ===========================================================================
#
# QuizListSerializer used to cost four queries per quiz (best_score,
# attempt_count, attempts_remaining, and the question_count model property),
# and every answer row on quiz_attempts cost its own lookup for the correct
# choice. These pin the bulk replacements: query volume must not scale with the
# number of quizzes or answers, and the values must be unchanged — including
# the quizzes with no attempts, which is what a grouped query drops.


def queries_against(ctx, table):
    return [q['sql'] for q in ctx.captured_queries if table in q['sql'].lower()]


@pytest.mark.django_db
class TestPhase63QuizListQueryCounts:

    @pytest.fixture
    def many_quizzes(self, unit, student):
        """12 quizzes; the student has attempts on only some of them."""
        quizzes = []
        for i in range(12):
            q = Quiz.objects.create(
                unit=unit, title=f'Q{i}', passing_score=70, points=10,
                order=i, max_attempts=3)
            Question.objects.create(quiz=q, text=f'q{i}?', order=1)
            quizzes.append(q)
        # Attempts on the first four only.
        for i, q in enumerate(quizzes[:4]):
            QuizAttempt.objects.create(
                quiz=q, student=student, score=50 + i * 10, passed=i > 1,
                status=QuizAttempt.STATUS_COMPLETED)
        return quizzes

    def test_student_list_does_not_scale_with_quizzes(
            self, api_client, student, enrollment, unit, many_quizzes):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        api_client.force_authenticate(user=student)
        with CaptureQueriesContext(connection) as ctx:
            response = api_client.get(f'/api/units/{unit.id}/quizzes/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 12
        assert len(queries_against(ctx, 'quizzes_quizattempt')) <= 1, (
            'best_score/attempt_count/attempts_remaining must share one '
            'grouped query'
        )
        assert len(queries_against(ctx, 'quizzes_question')) <= 1, (
            'question_count must be annotated, not a per-quiz property call'
        )

    def test_adding_quizzes_does_not_add_queries(
            self, api_client, student, enrollment, unit, many_quizzes):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        api_client.force_authenticate(user=student)
        url = f'/api/units/{unit.id}/quizzes/'
        with CaptureQueriesContext(connection) as small:
            api_client.get(url)

        for i in range(100, 112):
            Quiz.objects.create(
                unit=unit, title=f'X{i}', passing_score=70, points=10, order=i)

        with CaptureQueriesContext(connection) as big:
            response = api_client.get(url)
        assert len(response.data) == 24
        assert len(big.captured_queries) == len(small.captured_queries), (
            f'{len(small.captured_queries)} queries for 12 quizzes vs '
            f'{len(big.captured_queries)} for 24 — still scaling'
        )


@pytest.mark.django_db
class TestPhase63QuizListValues:
    """Values must match what the per-quiz queries returned."""

    @pytest.fixture
    def graded_quiz(self, unit, student):
        quiz = Quiz.objects.create(
            unit=unit, title='Graded', passing_score=70, points=10, order=1,
            max_attempts=3)
        Question.objects.create(quiz=quiz, text='q?', order=1)
        for score in (40, 90, 60):
            QuizAttempt.objects.create(
                quiz=quiz, student=student, score=score, passed=score >= 70,
                status=QuizAttempt.STATUS_COMPLETED)
        return quiz

    def _list(self, api_client, unit):
        response = api_client.get(f'/api/units/{unit.id}/quizzes/')
        assert response.status_code == status.HTTP_200_OK
        return {q['title']: q for q in response.data}

    def test_best_score_is_the_highest_completed_attempt(
            self, api_client, student, enrollment, unit, graded_quiz):
        api_client.force_authenticate(user=student)
        row = self._list(api_client, unit)['Graded']

        assert row['best_score']['score'] == 90.0
        assert row['best_score']['passed'] is True
        assert row['attempt_count'] == 3
        assert row['attempts_remaining'] == 0
        assert row['question_count'] == 1

    def test_quiz_with_no_attempts(
            self, api_client, student, enrollment, unit, quiz):
        """The row a grouped query drops."""
        api_client.force_authenticate(user=student)
        row = self._list(api_client, unit)['Test Quiz']

        assert row['best_score'] is None
        assert row['attempt_count'] == 0
        assert row['question_count'] == 0

    def test_unlimited_attempts_reports_none(
            self, api_client, student, enrollment, unit, graded_quiz):
        graded_quiz.max_attempts = 0
        graded_quiz.save()

        api_client.force_authenticate(user=student)
        row = self._list(api_client, unit)['Graded']
        assert row['attempts_remaining'] is None

    def test_in_progress_attempts_are_not_counted(
            self, api_client, student, enrollment, unit, graded_quiz):
        QuizAttempt.objects.create(
            quiz=graded_quiz, student=student, score=0,
            status=QuizAttempt.STATUS_IN_PROGRESS)

        api_client.force_authenticate(user=student)
        row = self._list(api_client, unit)['Graded']
        assert row['attempt_count'] == 3

    def test_another_students_attempts_are_not_counted(
            self, api_client, student, enrollment, unit, graded_quiz):
        other = User.objects.create_user(email='o@test.com', password='x')
        Enrollment.objects.create(user=other, course=unit.course)
        QuizAttempt.objects.create(
            quiz=graded_quiz, student=other, score=100, passed=True,
            status=QuizAttempt.STATUS_COMPLETED)

        api_client.force_authenticate(user=student)
        row = self._list(api_client, unit)['Graded']
        assert row['attempt_count'] == 3
        assert row['best_score']['score'] == 90.0

    def test_instructor_sees_all_completed_attempts(
            self, api_client, instructor, unit, graded_quiz, student):
        other = User.objects.create_user(email='o2@test.com', password='x')
        QuizAttempt.objects.create(
            quiz=graded_quiz, student=other, score=100, passed=True,
            status=QuizAttempt.STATUS_COMPLETED)

        api_client.force_authenticate(user=instructor)
        row = self._list(api_client, unit)['Graded']
        assert row['attempt_count'] == 4
        assert row['best_score'] is None
        assert row['attempts_remaining'] is None

    def test_single_object_render_matches_the_list(
            self, api_client, student, enrollment, unit, graded_quiz):
        """The many=False fallback path — no ListSerializer to prime it."""
        from rest_framework.test import APIRequestFactory

        from .serializers import QuizListSerializer

        api_client.force_authenticate(user=student)
        from_list = self._list(api_client, unit)['Graded']

        request = APIRequestFactory().get('/')
        request.user = student
        single = QuizListSerializer(
            graded_quiz, context={'request': request}).data

        for field in ('best_score', 'attempt_count', 'attempts_remaining',
                      'question_count'):
            assert single[field] == from_list[field], field


@pytest.mark.django_db
class TestPhase63QuizAttemptAnswers:
    """Answer rows must not cost a query each for their correct choice."""

    @pytest.fixture
    def attempt_with_answers(self, quiz, student):
        from .models import AttemptAnswer

        attempt = QuizAttempt.objects.create(
            quiz=quiz, student=student, score=50, passed=False,
            status=QuizAttempt.STATUS_COMPLETED)
        for i in range(12):
            question = Question.objects.create(
                quiz=quiz, text=f'q{i}?', order=i)
            wrong = Choice.objects.create(
                question=question, text='no', is_correct=False, order=1)
            Choice.objects.create(
                question=question, text='yes', is_correct=True, order=2)
            AttemptAnswer.objects.create(
                attempt=attempt, question=question, selected_choice=wrong,
                is_correct=False)
        return attempt

    def test_choice_queries_do_not_scale_with_answers(
            self, api_client, student, enrollment, quiz, attempt_with_answers):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        api_client.force_authenticate(user=student)
        with CaptureQueriesContext(connection) as ctx:
            response = api_client.get(f'/api/quizzes/{quiz.id}/attempts/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data[0]['answers']) == 12
        assert len(queries_against(ctx, 'quizzes_choice')) <= 2, (
            'correct_choice_text must read the prefetch cache'
        )
        # Two constant quiz queries: the view's own get_object_or_404 and the
        # attempts query's select_related join. Neither scales per attempt,
        # which is what the next test pins.
        assert len(queries_against(ctx, 'quizzes_quiz"')) <= 2

    def test_adding_attempts_does_not_add_queries(
            self, api_client, student, enrollment, quiz, attempt_with_answers):
        """quiz_title was a query per attempt before select_related('quiz')."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        api_client.force_authenticate(user=student)
        url = f'/api/quizzes/{quiz.id}/attempts/'
        with CaptureQueriesContext(connection) as small:
            api_client.get(url)

        for score in (10, 20, 30):
            QuizAttempt.objects.create(
                quiz=quiz, student=student, score=score, passed=False,
                status=QuizAttempt.STATUS_COMPLETED)

        with CaptureQueriesContext(connection) as big:
            response = api_client.get(url)
        assert len(response.data) == 4

        assert len(big.captured_queries) == len(small.captured_queries), (
            f'{len(small.captured_queries)} queries for 1 attempt vs '
            f'{len(big.captured_queries)} for 4 — still scaling'
        )

    def test_answer_values_are_unchanged(
            self, api_client, student, enrollment, quiz, attempt_with_answers):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/quizzes/{quiz.id}/attempts/')

        answers = response.data[0]['answers']
        assert all(a['correct_choice_text'] == 'yes' for a in answers)
        assert all(a['selected_choice_text'] == 'no' for a in answers)
        assert all(a['is_correct'] is False for a in answers)

    def test_question_with_no_correct_choice_reports_none(
            self, api_client, student, enrollment, quiz):
        from .models import AttemptAnswer

        attempt = QuizAttempt.objects.create(
            quiz=quiz, student=student, score=0, passed=False,
            status=QuizAttempt.STATUS_COMPLETED)
        question = Question.objects.create(quiz=quiz, text='broken?', order=1)
        choice = Choice.objects.create(
            question=question, text='only', is_correct=False, order=1)
        AttemptAnswer.objects.create(
            attempt=attempt, question=question, selected_choice=choice,
            is_correct=False)

        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/quizzes/{quiz.id}/attempts/')
        assert response.data[0]['answers'][0]['correct_choice_text'] is None


# ==================== Phase 66: quizzes inside locked units ====================

@pytest.fixture
def locked_unit(course):
    return Unit.objects.create(
        course=course, title='Locked Unit', order=2, is_locked=True)


@pytest.fixture
def locked_quiz(locked_unit):
    return Quiz.objects.create(
        unit=locked_unit, title='Locked Quiz', passing_score=70,
        points=10, order=1)


@pytest.mark.django_db
class TestLockedUnitQuizAccess:
    LOCK_DETAIL = 'This unit is locked by your instructor.'

    def test_quiz_endpoints_in_locked_unit_403_for_student(
            self, api_client, student, enrollment, locked_quiz, locked_unit):
        api_client.force_authenticate(user=student)

        reads = [
            f'/api/quizzes/{locked_quiz.id}/',
            f'/api/units/{locked_unit.id}/quizzes/',
            f'/api/quizzes/{locked_quiz.id}/session/',
        ]
        for url in reads:
            response = api_client.get(url)
            assert response.status_code == status.HTTP_403_FORBIDDEN, url
            assert response.data['detail'] == self.LOCK_DETAIL

        writes = [
            f'/api/quizzes/{locked_quiz.id}/submit/',
            f'/api/quizzes/{locked_quiz.id}/session/start/',
            f'/api/quizzes/{locked_quiz.id}/session/answer/',
        ]
        for url in writes:
            response = api_client.post(url, {})
            assert response.status_code == status.HTTP_403_FORBIDDEN, url
            assert response.data['detail'] == self.LOCK_DETAIL

    def test_no_attempt_is_created_for_a_locked_quiz(
            self, api_client, student, enrollment, locked_quiz):
        api_client.force_authenticate(user=student)
        api_client.post(f'/api/quizzes/{locked_quiz.id}/session/start/', {})
        assert not QuizAttempt.objects.filter(
            quiz=locked_quiz, student=student).exists()

    def test_instructor_reads_locked_quiz_normally(
            self, api_client, instructor, locked_quiz, locked_unit):
        api_client.force_authenticate(user=instructor)

        assert api_client.get(
            f'/api/quizzes/{locked_quiz.id}/'
        ).status_code == status.HTTP_200_OK
        assert api_client.get(
            f'/api/units/{locked_unit.id}/quizzes/'
        ).status_code == status.HTTP_200_OK

    def test_course_quiz_list_filters_locked_units(
            self, api_client, student, enrollment, course, quiz, locked_quiz):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/{course.code}/quizzes/')

        assert response.status_code == status.HTTP_200_OK
        titles = {q['title'] for q in response.data}
        assert 'Test Quiz' in titles
        assert 'Locked Quiz' not in titles

    def test_course_quiz_list_keeps_locked_units_for_instructor(
            self, api_client, instructor, course, quiz, locked_quiz):
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/{course.code}/quizzes/')

        titles = {q['title'] for q in response.data}
        assert {'Test Quiz', 'Locked Quiz'} <= titles

    def test_unlocking_restores_student_access(
            self, api_client, student, enrollment, locked_quiz, locked_unit):
        api_client.force_authenticate(user=student)
        assert api_client.get(
            f'/api/quizzes/{locked_quiz.id}/'
        ).status_code == status.HTTP_403_FORBIDDEN

        locked_unit.is_locked = False
        locked_unit.save(update_fields=['is_locked'])

        assert api_client.get(
            f'/api/quizzes/{locked_quiz.id}/'
        ).status_code == status.HTTP_200_OK
