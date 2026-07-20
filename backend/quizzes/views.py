from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Max
from django.utils import timezone

from courses.models import Unit
from courses.permissions import is_course_instructor, is_enrolled, require_enrollment
from .models import Quiz, Question, Choice, QuizAttempt, AttemptAnswer
from .serializers import (
    QuizListSerializer, QuizDetailSerializer, QuizStudentDetailSerializer,
    QuizCreateUpdateSerializer, QuestionCreateUpdateSerializer,
    QuizAttemptSerializer, QuizSubmissionSerializer
)


# ==================== Quiz Views ====================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def unit_quizzes(request, unit_id):
    """List quizzes in a unit or create a new quiz."""
    unit = get_object_or_404(Unit, id=unit_id)
    course = unit.course

    # Check access
    if not is_course_instructor(request.user, course) and not is_enrolled(request.user, course):
        return Response(
            {'detail': 'You must be enrolled or the instructor to access quizzes.'},
            status=status.HTTP_403_FORBIDDEN
        )

    if request.method == 'GET':
        quizzes = Quiz.objects.filter(unit=unit)
        serializer = QuizListSerializer(quizzes, many=True, context={'request': request})
        return Response(serializer.data)

    elif request.method == 'POST':
        # Only instructor can create quizzes
        if not is_course_instructor(request.user, course):
            return Response(
                {'detail': 'Only the instructor can create quizzes.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = QuizCreateUpdateSerializer(data=request.data)
        if serializer.is_valid():
            # Auto-set order if not provided
            if 'order' not in request.data or request.data['order'] == 0:
                max_order = Quiz.objects.filter(unit=unit).aggregate(Max('order'))['order__max']
                serializer.validated_data['order'] = (max_order or 0) + 1

            quiz = serializer.save(unit=unit)
            return Response(
                QuizDetailSerializer(quiz, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def quiz_detail(request, quiz_id):
    """Get, update, or delete a quiz."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    course = quiz.unit.course

    # Check access
    if not is_course_instructor(request.user, course) and not is_enrolled(request.user, course):
        return Response(
            {'detail': 'You must be enrolled or the instructor to access this quiz.'},
            status=status.HTTP_403_FORBIDDEN
        )

    if request.method == 'GET':
        # Instructors see correct answers, students don't
        if is_course_instructor(request.user, course):
            serializer = QuizDetailSerializer(quiz, context={'request': request})
        else:
            serializer = QuizStudentDetailSerializer(quiz, context={'request': request})
        return Response(serializer.data)

    elif request.method == 'PUT':
        if not is_course_instructor(request.user, course):
            return Response(
                {'detail': 'Only the instructor can update quizzes.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = QuizCreateUpdateSerializer(quiz, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(QuizDetailSerializer(quiz, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        if not is_course_instructor(request.user, course):
            return Response(
                {'detail': 'Only the instructor can delete quizzes.'},
                status=status.HTTP_403_FORBIDDEN
            )

        quiz.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== Question Views ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quiz_add_question(request, quiz_id):
    """Add a question to a quiz."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    course = quiz.unit.course

    if not is_course_instructor(request.user, course):
        return Response(
            {'detail': 'Only the instructor can add questions.'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = QuestionCreateUpdateSerializer(data=request.data)
    if serializer.is_valid():
        # Auto-set order if not provided
        if 'order' not in request.data or request.data.get('order') == 0:
            max_order = Question.objects.filter(quiz=quiz).aggregate(Max('order'))['order__max']
            serializer.validated_data['order'] = (max_order or 0) + 1

        question = serializer.save(quiz=quiz)
        return Response(
            QuestionCreateUpdateSerializer(question).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def question_detail(request, question_id):
    """Update or delete a question."""
    question = get_object_or_404(Question, id=question_id)
    course = question.quiz.unit.course

    if not is_course_instructor(request.user, course):
        return Response(
            {'detail': 'Only the instructor can modify questions.'},
            status=status.HTTP_403_FORBIDDEN
        )

    if request.method == 'PUT':
        serializer = QuestionCreateUpdateSerializer(question, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== Quiz Taking Views ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_quiz(request, quiz_id):
    """Submit quiz answers and get results."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    course = quiz.unit.course

    # Only enrolled students can submit
    if not is_enrolled(request.user, course):
        return Response(
            {'detail': 'You must be enrolled to take this quiz.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Check max attempts (completed only — abandoned sessions don't burn one)
    if quiz.max_attempts > 0:
        user_attempts = QuizAttempt.objects.filter(
            quiz=quiz, student=request.user, status=QuizAttempt.STATUS_COMPLETED
        ).count()
        if user_attempts >= quiz.max_attempts:
            return Response(
                {'detail': f'You have reached the maximum number of attempts ({quiz.max_attempts}) for this quiz.'},
                status=status.HTTP_400_BAD_REQUEST
            )

    serializer = QuizSubmissionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    answers_data = serializer.validated_data['answers']
    questions = quiz.questions.all()

    if not questions.exists():
        return Response(
            {'detail': 'This quiz has no questions.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Calculate score
    correct_count = 0
    total_questions = questions.count()

    # Create attempt (legacy batch submits are completed immediately)
    attempt = QuizAttempt.objects.create(
        quiz=quiz,
        student=request.user,
        score=0,
        passed=False,
        status=QuizAttempt.STATUS_COMPLETED,
        completed_at=timezone.now(),
    )

    # Process each question
    for question in questions:
        question_id_str = str(question.id)
        selected_choice_id = answers_data.get(question_id_str)

        selected_choice = None
        is_correct = False

        if selected_choice_id:
            try:
                selected_choice = Choice.objects.get(id=selected_choice_id, question=question)
                is_correct = selected_choice.is_correct
                if is_correct:
                    correct_count += 1
            except Choice.DoesNotExist:
                pass

        AttemptAnswer.objects.create(
            attempt=attempt,
            question=question,
            selected_choice=selected_choice,
            is_correct=is_correct
        )

    # Calculate final score
    score = (correct_count / total_questions) * 100 if total_questions > 0 else 0
    passed = score >= quiz.passing_score

    attempt.score = round(score, 2)
    attempt.passed = passed
    attempt.save()

    # Return results (+ gamification delta on a pass)
    data = dict(QuizAttemptSerializer(attempt).data)
    if passed:
        from gamification.services import award_quiz_pass
        data['gamification'] = award_quiz_pass(request.user, quiz).as_dict()
    return Response(data, status=status.HTTP_201_CREATED)


# ==================== Quiz Session Flow (Phase 32) ====================
# Duolingo-style mastery sessions: one question at a time, instant feedback,
# missed questions re-queued until every question is answered correctly.
# The recorded score is FIRST-TRY correctness only.

def _quiz_session_state(quiz, attempt):
    """Resume/progress payload for an in-progress session."""
    questions = list(quiz.questions.all())
    answers = {a.question_id: a for a in attempt.answers.all()}

    question_status = []
    for question in questions:
        answer = answers.get(question.id)
        question_status.append({
            'question_id': question.id,
            'answered': answer is not None,
            'first_try_correct': answer.is_correct if answer else None,
            'mastered': bool(answer and answer.mastered_at),
        })

    # Unanswered questions first (original order), then missed ones re-queued.
    unanswered = [q.id for q in questions if q.id not in answers]
    requeued = [
        q.id for q in questions
        if q.id in answers and not answers[q.id].mastered_at
    ]

    mastered_count = sum(1 for s in question_status if s['mastered'])
    return {
        'attempt_id': attempt.id,
        'quiz_id': quiz.id,
        'status': attempt.status,
        'questions': question_status,
        'remaining_question_ids': unanswered + requeued,
        'total_questions': len(questions),
        'mastered_count': mastered_count,
        'answered_count': len(answers),
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_quiz_session(request, quiz_id):
    """
    Start (or resume) a mastery session for a quiz. Students only.
    max_attempts is enforced against COMPLETED attempts — an abandoned
    in-progress session does not burn an attempt.
    """
    quiz = get_object_or_404(Quiz, id=quiz_id)
    require_enrollment(request.user, quiz.unit.course, "You must be enrolled to take this quiz.")

    if not quiz.questions.exists():
        return Response(
            {'detail': 'This quiz has no questions.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    existing = QuizAttempt.objects.filter(
        quiz=quiz, student=request.user, status=QuizAttempt.STATUS_IN_PROGRESS
    ).first()
    if existing:
        return Response(_quiz_session_state(quiz, existing))

    if quiz.max_attempts > 0:
        completed = QuizAttempt.objects.filter(
            quiz=quiz, student=request.user, status=QuizAttempt.STATUS_COMPLETED
        ).count()
        if completed >= quiz.max_attempts:
            return Response(
                {'detail': f'You have reached the maximum number of attempts ({quiz.max_attempts}) for this quiz.'},
                status=status.HTTP_400_BAD_REQUEST
            )

    attempt = QuizAttempt.objects.create(
        quiz=quiz,
        student=request.user,
        score=0,
        passed=False,
        status=QuizAttempt.STATUS_IN_PROGRESS,
        completed_at=None,
    )
    return Response(_quiz_session_state(quiz, attempt), status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_quiz_session(request, quiz_id):
    """Resume state for the current in-progress session; 404 if none."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    require_enrollment(request.user, quiz.unit.course, "You must be enrolled to take this quiz.")

    attempt = QuizAttempt.objects.filter(
        quiz=quiz, student=request.user, status=QuizAttempt.STATUS_IN_PROGRESS
    ).first()
    if attempt is None:
        return Response(
            {'detail': 'No in-progress session for this quiz.'},
            status=status.HTTP_404_NOT_FOUND
        )
    return Response(_quiz_session_state(quiz, attempt))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def answer_quiz_session(request, quiz_id):
    """
    Grade one answer in a mastery session. The first answer for a question is
    the permanent first-try record; correct answers (first try or re-queue)
    stamp mastered_at. When the last question masters, the attempt finalizes:
    score = first-try correctness %, XP awarded on pass.
    """
    quiz = get_object_or_404(Quiz, id=quiz_id)
    require_enrollment(request.user, quiz.unit.course, "You must be enrolled to take this quiz.")

    attempt = QuizAttempt.objects.filter(
        quiz=quiz, student=request.user, status=QuizAttempt.STATUS_IN_PROGRESS
    ).first()
    if attempt is None:
        return Response(
            {'detail': 'No in-progress session for this quiz. Start one first.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    question_id = request.data.get('question_id')
    choice_id = request.data.get('choice_id')
    if question_id is None or choice_id is None:
        return Response(
            {'detail': 'question_id and choice_id are required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        question = quiz.questions.get(id=question_id)
    except Question.DoesNotExist:
        return Response(
            {'detail': 'Question does not belong to this quiz.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        choice = question.choices.get(id=choice_id)
    except Choice.DoesNotExist:
        return Response(
            {'detail': 'Choice does not belong to this question.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    is_correct = choice.is_correct
    # First try creates the permanent score record; get_or_create is
    # race-safe under the (attempt, question) uniqueness — a concurrent
    # duplicate answer can't 500, the loser just sees the winner's row.
    answer, created = AttemptAnswer.objects.get_or_create(
        attempt=attempt,
        question=question,
        defaults={
            'selected_choice': choice,
            'is_correct': is_correct,
            'mastered_at': timezone.now() if is_correct else None,
        },
    )
    if not created:
        if answer.mastered_at:
            return Response(
                {'detail': 'This question is already mastered.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if is_correct:
            # Mastery retry: never touch the first-try record.
            answer.mastered_at = timezone.now()
            answer.save(update_fields=['mastered_at'])

    total_questions = quiz.questions.count()
    mastered_count = attempt.answers.filter(mastered_at__isnull=False).count()
    remaining_count = total_questions - mastered_count

    correct_choice = question.choices.filter(is_correct=True).first()
    data = {
        'is_correct': is_correct,
        'correct_choice_id': correct_choice.id if correct_choice else None,
        'correct_choice_text': correct_choice.text if correct_choice else None,
        'remaining_count': remaining_count,
        'session_complete': remaining_count == 0,
    }

    if remaining_count == 0:
        # Auto-finalize: score from FIRST-TRY correctness, same formula as
        # the legacy batch submit.
        first_try_correct = attempt.answers.filter(is_correct=True).count()
        score = (first_try_correct / total_questions) * 100 if total_questions > 0 else 0
        passed = score >= quiz.passing_score

        attempt.score = round(score, 2)
        attempt.passed = passed
        attempt.status = QuizAttempt.STATUS_COMPLETED
        attempt.completed_at = timezone.now()
        attempt.save()

        result = dict(QuizAttemptSerializer(attempt).data)
        if passed:
            from gamification.services import award_quiz_pass
            result['gamification'] = award_quiz_pass(request.user, quiz).as_dict()
        data['result'] = result

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def quiz_attempts(request, quiz_id):
    """Get user's attempts for a quiz."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    course = quiz.unit.course

    # Check access
    if not is_course_instructor(request.user, course) and not is_enrolled(request.user, course):
        return Response(
            {'detail': 'You must be enrolled or the instructor to view attempts.'},
            status=status.HTTP_403_FORBIDDEN
        )

    if is_course_instructor(request.user, course):
        # Instructors see all attempts
        attempts = QuizAttempt.objects.filter(
            quiz=quiz, status=QuizAttempt.STATUS_COMPLETED
        ).select_related('student')
    else:
        # Students see only their attempts
        attempts = QuizAttempt.objects.filter(
            quiz=quiz, student=request.user, status=QuizAttempt.STATUS_COMPLETED
        )

    serializer = QuizAttemptSerializer(attempts, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def course_quizzes(request, course_code):
    """Get all quizzes in a course."""
    from courses.models import Course
    course = get_object_or_404(Course, code=course_code)

    # Check access
    if not is_course_instructor(request.user, course) and not is_enrolled(request.user, course):
        return Response(
            {'detail': 'You must be enrolled or the instructor to view quizzes.'},
            status=status.HTTP_403_FORBIDDEN
        )

    quizzes = Quiz.objects.filter(unit__course=course).select_related('unit')
    serializer = QuizListSerializer(quizzes, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quick_grade_quiz(request, quiz_id, student_id):
    """
    Quick grade endpoint for gradebook inline editing of quiz scores.
    Updates or creates a quiz attempt with the specified score.
    """
    from accounts.models import User

    quiz = get_object_or_404(Quiz, id=quiz_id)
    course = quiz.unit.course

    # Only instructor can use quick grade
    if not is_course_instructor(request.user, course):
        return Response(
            {'detail': 'Only the course instructor can grade.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Get the student
    student = get_object_or_404(User, id=student_id)

    # Verify student is enrolled
    if not is_enrolled(student, course):
        return Response(
            {'error': 'Student is not enrolled in this course.'},
            status=status.HTTP_404_NOT_FOUND
        )

    points = request.data.get('points')
    if points is None:
        return Response(
            {'error': 'Points value is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        points = float(points)
    except (ValueError, TypeError):
        return Response(
            {'error': 'Points must be a number.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if points < 0 or points > quiz.points:
        return Response(
            {'error': f'Points must be between 0 and {quiz.points}.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Calculate score percentage from points
    score = (points / quiz.points) * 100 if quiz.points > 0 else 0
    passed = score >= quiz.passing_score

    # Get the most recent completed attempt for this student
    # (not the best one, to avoid corrupting history)
    attempt = QuizAttempt.objects.filter(
        quiz=quiz, student=student, status=QuizAttempt.STATUS_COMPLETED
    ).order_by('-completed_at').first()

    if attempt:
        # Update existing attempt
        attempt.score = round(score, 2)
        attempt.passed = passed
        attempt.save()
    else:
        # Create new attempt (manual grade without actual answers)
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student=student,
            score=round(score, 2),
            passed=passed,
            status=QuizAttempt.STATUS_COMPLETED,
            completed_at=timezone.now(),
        )

    return Response({
        'success': True,
        'points': points,
        'score': attempt.score,
        'passed': attempt.passed
    })
