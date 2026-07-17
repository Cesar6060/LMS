from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Max

from courses.models import Unit
from courses.permissions import is_course_instructor, is_enrolled
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

    # Check max attempts
    if quiz.max_attempts > 0:
        user_attempts = QuizAttempt.objects.filter(quiz=quiz, student=request.user).count()
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

    # Create attempt
    attempt = QuizAttempt.objects.create(
        quiz=quiz,
        student=request.user,
        score=0,
        passed=False
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

    # Return results
    return Response(QuizAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)


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
        attempts = QuizAttempt.objects.filter(quiz=quiz).select_related('student')
    else:
        # Students see only their attempts
        attempts = QuizAttempt.objects.filter(quiz=quiz, student=request.user)

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

    # Get the most recent attempt for this student (not the best one, to avoid corrupting history)
    attempt = QuizAttempt.objects.filter(quiz=quiz, student=student).order_by('-completed_at').first()

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
            passed=passed
        )

    return Response({
        'success': True,
        'points': points,
        'score': attempt.score,
        'passed': attempt.passed
    })
