import csv
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes as perm_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import models
from django.db.models import F, Max, Count
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta

from .models import Course, Unit, Lesson, Enrollment, LessonProgress, Announcement, LessonQuestion, LessonQuestionChoice, LessonQuestionAnswer, LessonQuizAttempt, LessonAttachment
from .serializers import (
    CourseSerializer, CourseListSerializer, CourseCreateSerializer,
    InstructorCourseSerializer, UnitSerializer, UnitCreateSerializer,
    LessonSerializer, LessonListSerializer, LessonCreateSerializer,
    EnrollmentSerializer, EnrollmentCreateSerializer, LessonProgressSerializer,
    LessonProgressUpdateSerializer, AnnouncementSerializer,
    AnnouncementListSerializer, AnnouncementCreateSerializer,
    StudentRosterSerializer, LessonQuestionSerializer, LessonQuestionStudentSerializer,
    LessonQuestionCreateSerializer, AnswerQuestionSerializer, LessonAttachmentSerializer
)
from .permissions import (
    IsInstructor, IsInstructorOrReadOnly, IsCourseInstructor,
    IsEnrolledOrInstructor
)


class CourseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Course CRUD operations.

    list: Get all active courses
    retrieve: Get course details by code
    create: Create a new course (instructors only)
    update: Update a course (course instructor only)
    destroy: Delete a course (course instructor only)
    """
    lookup_field = 'code'
    permission_classes = [IsAuthenticated, IsInstructorOrReadOnly, IsCourseInstructor]

    def get_queryset(self):
        queryset = Course.objects.select_related('instructor').prefetch_related(
            'units__lessons', 'enrollments'
        )

        if self.request.user.is_instructor:
            # Instructors see all courses (for browsing/reference)
            return queryset
        else:
            # Students only see courses they are actively enrolled in
            enrolled_course_ids = Enrollment.objects.filter(
                user=self.request.user, is_active=True
            ).values_list('course_id', flat=True)
            return queryset.filter(id__in=enrolled_course_ids, is_active=True)

    def get_serializer_class(self):
        if self.action == 'list':
            return CourseListSerializer
        elif self.action == 'create':
            return CourseCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return CourseCreateSerializer
        return CourseSerializer

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def enroll(self, request, code=None):
        """Enroll in a course using enrollment code."""
        course = get_object_or_404(Course, code=code, is_active=True)

        # Verify enrollment code matches
        provided_code = request.data.get('enrollment_code', '').upper()
        if provided_code != course.enrollment_code:
            return Response(
                {'error': 'Invalid enrollment code'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if already enrolled (only active enrollments)
        existing = Enrollment.objects.filter(user=request.user, course=course).first()
        if existing and existing.is_active:
            return Response(
                {'error': 'You are already enrolled in this course'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Re-activate if previously removed
        if existing and not existing.is_active:
            existing.is_active = True
            existing.save(update_fields=['is_active'])
            serializer = EnrollmentSerializer(existing)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Check if user is instructor
        if course.instructor == request.user:
            return Response(
                {'error': 'Instructors cannot enroll in their own courses'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create enrollment
        enrollment = Enrollment.objects.create(user=request.user, course=course)
        return Response(
            EnrollmentSerializer(enrollment).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsInstructor])
    def regenerate_code(self, request, code=None):
        """Regenerate enrollment code (instructor only)."""
        course = self.get_object()

        if course.instructor != request.user:
            return Response(
                {'error': 'Only the course instructor can regenerate the code'},
                status=status.HTTP_403_FORBIDDEN
            )

        new_code = course.regenerate_enrollment_code()
        return Response({'enrollment_code': new_code})


class InstructorCourseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for instructors to view their courses with enrollment codes.
    """
    serializer_class = InstructorCourseSerializer
    permission_classes = [IsAuthenticated, IsInstructor]

    def get_queryset(self):
        return Course.objects.filter(
            instructor=self.request.user
        ).prefetch_related('units__lessons', 'enrollments')


class UnitViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Unit CRUD operations.
    """
    serializer_class = UnitSerializer
    permission_classes = [IsAuthenticated, IsCourseInstructor]

    def get_queryset(self):
        return Unit.objects.select_related('course').prefetch_related('lessons')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return UnitCreateSerializer
        return UnitSerializer

    @action(detail=True, methods=['patch'])
    def reorder(self, request, pk=None):
        """Reorder a unit within its course."""
        unit = self.get_object()
        new_order = request.data.get('order')

        if new_order is None:
            return Response(
                {'error': 'Order is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            new_order = int(new_order)
        except ValueError:
            return Response(
                {'error': 'Order must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_order = unit.order
        course = unit.course

        if new_order == old_order:
            return Response(UnitSerializer(unit).data)

        # Reorder other units
        if new_order > old_order:
            # Moving down: shift units between old and new position up
            Unit.objects.filter(
                course=course,
                order__gt=old_order,
                order__lte=new_order
            ).update(order=F('order') - 1)
        else:
            # Moving up: shift units between new and old position down
            Unit.objects.filter(
                course=course,
                order__gte=new_order,
                order__lt=old_order
            ).update(order=F('order') + 1)

        unit.order = new_order
        unit.save()

        return Response(UnitSerializer(unit).data)


class CourseUnitsView(generics.ListCreateAPIView):
    """
    List units for a course or create a new unit.
    """
    permission_classes = [IsAuthenticated, IsInstructorOrReadOnly]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UnitCreateSerializer
        return UnitSerializer

    def get_queryset(self):
        course_code = self.kwargs['course_code']
        return Unit.objects.filter(
            course__code=course_code
        ).prefetch_related('lessons')

    def perform_create(self, serializer):
        course = get_object_or_404(Course, code=self.kwargs['course_code'])

        # Check if user is instructor
        if course.instructor != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only the course instructor can add units.")

        # Set order to next available
        max_order = course.units.aggregate(
            max_order=Max('order')
        )['max_order'] or 0

        serializer.save(course=course, order=max_order + 1)


class LessonViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Lesson CRUD operations.
    """
    permission_classes = [IsAuthenticated, IsEnrolledOrInstructor]

    def get_queryset(self):
        return Lesson.objects.select_related('unit__course')

    def get_serializer_class(self):
        if self.action == 'list':
            return LessonListSerializer
        return LessonSerializer

    @action(detail=True, methods=['patch'])
    def reorder(self, request, pk=None):
        """Reorder a lesson within its unit."""
        lesson = self.get_object()
        new_order = request.data.get('order')

        if new_order is None:
            return Response(
                {'error': 'Order is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            new_order = int(new_order)
        except ValueError:
            return Response(
                {'error': 'Order must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_order = lesson.order
        unit = lesson.unit

        if new_order == old_order:
            return Response(LessonSerializer(lesson).data)

        # Reorder other lessons
        if new_order > old_order:
            Lesson.objects.filter(
                unit=unit,
                order__gt=old_order,
                order__lte=new_order
            ).update(order=F('order') - 1)
        else:
            Lesson.objects.filter(
                unit=unit,
                order__gte=new_order,
                order__lt=old_order
            ).update(order=F('order') + 1)

        lesson.order = new_order
        lesson.save()

        return Response(LessonSerializer(lesson).data)


class UnitLessonsView(generics.ListCreateAPIView):
    """
    List lessons for a unit or create a new lesson.
    """
    permission_classes = [IsAuthenticated, IsInstructorOrReadOnly]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return LessonCreateSerializer
        return LessonSerializer

    def get_queryset(self):
        unit_id = self.kwargs['unit_id']
        return Lesson.objects.filter(unit_id=unit_id)

    def perform_create(self, serializer):
        unit = get_object_or_404(Unit, pk=self.kwargs['unit_id'])

        # Check if user is instructor
        if unit.course.instructor != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only the course instructor can add lessons.")

        # Set order to next available
        max_order = unit.lessons.aggregate(
            max_order=Max('order')
        )['max_order'] or 0

        serializer.save(unit=unit, order=max_order + 1)


class EnrollmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing enrollments.
    """
    serializer_class = EnrollmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Enrollment.objects.filter(
            user=self.request.user, is_active=True
        ).select_related('course__instructor')

    def get_serializer_class(self):
        if self.action == 'create':
            return EnrollmentCreateSerializer
        return EnrollmentSerializer

    def create(self, request, *args, **kwargs):
        """Enroll using enrollment code."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enrollment = serializer.save()
        return Response(
            EnrollmentSerializer(enrollment).data,
            status=status.HTTP_201_CREATED
        )


class LessonProgressView(generics.RetrieveUpdateAPIView):
    """
    Get or update progress for a specific lesson.
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return LessonProgressUpdateSerializer
        return LessonProgressSerializer

    def get_object(self):
        lesson = get_object_or_404(Lesson, pk=self.kwargs['lesson_id'])

        # Verify user is enrolled or instructor
        course = lesson.unit.course
        if course.instructor != self.request.user:
            if not Enrollment.objects.filter(
                user=self.request.user,
                course=course,
                is_active=True
            ).exists():
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You must be enrolled in this course.")

        # Get or create progress
        progress, created = LessonProgress.objects.get_or_create(
            user=self.request.user,
            lesson=lesson
        )
        return progress


class CourseProgressView(generics.RetrieveAPIView):
    """
    Get overall progress for a course (% complete).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, course_code):
        course = get_object_or_404(Course, code=course_code)

        # Verify user is enrolled or instructor
        if course.instructor != request.user:
            if not Enrollment.objects.filter(
                user=request.user,
                course=course,
                is_active=True
            ).exists():
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You must be enrolled in this course.")

        # Count total lessons in course
        total_lessons = Lesson.objects.filter(unit__course=course).count()

        if total_lessons == 0:
            return Response({
                'total_lessons': 0,
                'completed_lessons': 0,
                'progress_percentage': 0
            })

        # Count completed lessons for this user
        completed_lessons = LessonProgress.objects.filter(
            user=request.user,
            lesson__unit__course=course,
            completed=True
        ).count()

        progress_percentage = round((completed_lessons / total_lessons) * 100, 1)

        return Response({
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'progress_percentage': progress_percentage
        })


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def dashboard_stats(request):
    """
    Get dashboard statistics for the current user.
    Returns different stats for instructors vs students.
    """
    user = request.user

    if user.is_instructor:
        # Instructor stats
        from assignments.models import Submission

        # Get courses taught by this instructor
        instructor_courses = Course.objects.filter(instructor=user)

        # Count pending submissions (submitted but not graded)
        pending_grades = Submission.objects.filter(
            assignment__unit__course__in=instructor_courses,
            status='submitted'
        ).count()

        # Total students across all courses (active enrollments only)
        total_students = Enrollment.objects.filter(
            course__in=instructor_courses, is_active=True
        ).count()

        return Response({
            'pending_grades': pending_grades,
            'total_students': total_students,
            'course_count': instructor_courses.count()
        })
    else:
        # Student stats
        from assignments.models import Assignment, Submission

        # Get actively enrolled courses
        enrolled_course_ids = Enrollment.objects.filter(
            user=user, is_active=True
        ).values_list('course_id', flat=True)

        # Lessons completed
        lessons_completed = LessonProgress.objects.filter(
            user=user,
            completed=True
        ).count()

        # Assignments due in next 7 days
        now = timezone.now()
        week_from_now = now + timedelta(days=7)

        assignments_due = Assignment.objects.filter(
            unit__course_id__in=enrolled_course_ids,
            due_date__gte=now,
            due_date__lte=week_from_now
        ).exclude(
            submissions__student=user,
            submissions__status__in=['submitted', 'graded']
        ).count()

        return Response({
            'lessons_completed': lessons_completed,
            'assignments_due': assignments_due,
            'course_count': len(enrolled_course_ids)
        })


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def enhanced_dashboard(request):
    """
    Get enhanced dashboard data for the current user.
    Returns different data for instructors vs students.

    For Students:
    - continue_learning: most recently accessed course with current lesson info
    - upcoming_deadlines: next 3 assignments/quizzes due
    - course_progress_overview: progress bars for each enrolled course

    For Instructors:
    - recent_submissions: last 5 submissions needing review
    - course_progress_overview: summary of each course taught
    """
    from assignments.models import Assignment, Submission
    from quizzes.models import Quiz, QuizAttempt

    user = request.user
    now = timezone.now()

    if user.is_instructor:
        # Instructor Dashboard

        # Get courses taught by this instructor
        instructor_courses = Course.objects.filter(instructor=user)

        # Recent submissions needing review (submitted but not graded)
        recent_submissions = Submission.objects.filter(
            assignment__unit__course__in=instructor_courses,
            status='submitted'
        ).select_related(
            'student', 'assignment', 'assignment__unit__course'
        ).order_by('-submitted_at')[:5]

        recent_submissions_data = []
        for sub in recent_submissions:
            recent_submissions_data.append({
                'id': sub.id,
                'student_name': sub.student.get_full_name() or sub.student.email,
                'student_email': sub.student.email,
                'assignment_title': sub.assignment.title,
                'course_code': sub.assignment.unit.course.code,
                'course_title': sub.assignment.unit.course.title,
                'submitted_at': sub.submitted_at.isoformat() if sub.submitted_at else None,
                'is_late': sub.is_late,
            })

        # Course progress overview for instructor's courses
        # Use annotations to avoid N+1 queries
        from django.db.models import Count, Q

        instructor_courses_annotated = Course.objects.filter(
            instructor=user
        ).annotate(
            total_students=Count(
                'enrollments',
                filter=Q(enrollments__is_active=True)
            ),
            pending_submissions=Count(
                'units__assignments__submissions',
                filter=Q(units__assignments__submissions__status='submitted')
            )
        )

        course_progress = [
            {
                'course_code': course.code,
                'course_title': course.title,
                'student_count': course.total_students,
                'pending_submissions': course.pending_submissions,
            }
            for course in instructor_courses_annotated
        ]

        return Response({
            'recent_submissions': recent_submissions_data,
            'course_progress_overview': course_progress,
            'is_instructor': True,
        })

    else:
        # Student Dashboard

        # Get actively enrolled courses
        enrollments = Enrollment.objects.filter(
            user=user, is_active=True
        ).select_related('course').order_by('-last_activity_at')

        # Continue Learning: most recently accessed course
        continue_learning = None
        if enrollments.exists():
            most_recent_enrollment = enrollments.first()
            course = most_recent_enrollment.course

            # Find current lesson (first incomplete or last completed)
            completed_lessons = LessonProgress.objects.filter(
                user=user,
                lesson__unit__course=course,
                completed=True
            ).values_list('lesson_id', flat=True)

            # Get all lessons in course order
            all_lessons = Lesson.objects.filter(
                unit__course=course
            ).select_related('unit').order_by('unit__order', 'order')

            current_lesson = None
            completed_lessons_set = set(completed_lessons)
            for lesson in all_lessons:
                if lesson.id not in completed_lessons_set:
                    current_lesson = lesson
                    break

            # If all lessons completed, show the last one
            if not current_lesson and all_lessons.exists():
                current_lesson = all_lessons.last()

            # Calculate progress
            total_lessons = all_lessons.count()
            completed_count = len(completed_lessons)
            progress_percentage = round((completed_count / total_lessons) * 100, 1) if total_lessons > 0 else 0

            continue_learning = {
                'course_code': course.code,
                'course_title': course.title,
                'current_lesson': {
                    'id': current_lesson.id,
                    'title': current_lesson.title,
                    'unit_title': current_lesson.unit.title,
                } if current_lesson else None,
                'progress_percentage': progress_percentage,
                'completed_lessons': completed_count,
                'total_lessons': total_lessons,
                'last_activity_at': most_recent_enrollment.last_activity_at.isoformat() if most_recent_enrollment.last_activity_at else None,
            }

        # Upcoming deadlines: next 3 assignments/quizzes due
        enrolled_course_ids = enrollments.values_list('course_id', flat=True)

        # Get IDs of assignments the user has already submitted/graded
        submitted_assignment_ids = Submission.objects.filter(
            student=user,
            status__in=['submitted', 'graded']
        ).values_list('assignment_id', flat=True)

        # Get assignments with due dates in the future, excluding already submitted
        upcoming_assignments = Assignment.objects.filter(
            unit__course_id__in=enrolled_course_ids,
            due_date__gte=now
        ).exclude(
            id__in=submitted_assignment_ids
        ).select_related('unit__course').order_by('due_date')[:3]

        upcoming_deadlines = []
        for assignment in upcoming_assignments:
            # Check if student has a draft submission
            has_draft = Submission.objects.filter(
                assignment=assignment,
                student=user,
                status='draft'
            ).exists()

            upcoming_deadlines.append({
                'id': assignment.id,
                'type': 'assignment',
                'title': assignment.title,
                'course_code': assignment.unit.course.code,
                'course_title': assignment.unit.course.title,
                'due_date': assignment.due_date.isoformat(),
                'max_points': assignment.max_points,
                'has_draft': has_draft,
            })

        # Course progress overview - optimized to reduce N+1 queries
        from django.db.models import Count, Q

        # Get course IDs for bulk queries
        course_ids = list(enrollments.values_list('course_id', flat=True))

        # Bulk fetch totals per course using annotations
        course_totals = Course.objects.filter(id__in=course_ids).annotate(
            total_lessons=Count('units__lessons', distinct=True),
            total_assignments=Count('units__assignments', distinct=True),
            total_quizzes=Count('units__quizzes', distinct=True),
        ).values('id', 'code', 'title', 'total_lessons', 'total_assignments', 'total_quizzes')

        # Build lookup dict
        totals_by_course = {c['id']: c for c in course_totals}

        # Bulk fetch user's completed lessons per course
        completed_lessons_by_course = dict(
            LessonProgress.objects.filter(
                user=user,
                lesson__unit__course_id__in=course_ids,
                completed=True
            ).values('lesson__unit__course_id').annotate(
                count=Count('id')
            ).values_list('lesson__unit__course_id', 'count')
        )

        # Bulk fetch user's completed assignments per course
        completed_assignments_by_course = dict(
            Submission.objects.filter(
                student=user,
                assignment__unit__course_id__in=course_ids,
                status__in=['submitted', 'graded']
            ).values('assignment__unit__course_id').annotate(
                count=Count('id')
            ).values_list('assignment__unit__course_id', 'count')
        )

        # Bulk fetch user's passed quizzes per course
        passed_quizzes_by_course = dict(
            QuizAttempt.objects.filter(
                student=user,
                quiz__unit__course_id__in=course_ids,
                passed=True
            ).values('quiz__unit__course_id').annotate(
                count=Count('quiz', distinct=True)
            ).values_list('quiz__unit__course_id', 'count')
        )

        # Build course progress from pre-fetched data
        course_progress = []
        for enrollment in enrollments:
            course_id = enrollment.course_id
            totals = totals_by_course.get(course_id, {})

            total_lessons = totals.get('total_lessons', 0)
            total_assignments = totals.get('total_assignments', 0)
            total_quizzes = totals.get('total_quizzes', 0)

            completed_lessons = completed_lessons_by_course.get(course_id, 0)
            completed_assignments = completed_assignments_by_course.get(course_id, 0)
            passed_quizzes = passed_quizzes_by_course.get(course_id, 0)

            lesson_percentage = round((completed_lessons / total_lessons) * 100, 1) if total_lessons > 0 else 0
            assignment_percentage = round((completed_assignments / total_assignments) * 100, 1) if total_assignments > 0 else 0
            quiz_percentage = round((passed_quizzes / total_quizzes) * 100, 1) if total_quizzes > 0 else 0

            # Overall progress (weighted average)
            total_items = total_lessons + total_assignments + total_quizzes
            if total_items > 0:
                overall_percentage = round(
                    ((completed_lessons + completed_assignments + passed_quizzes) / total_items) * 100, 1
                )
            else:
                overall_percentage = 0

            course_progress.append({
                'course_code': totals.get('code', ''),
                'course_title': totals.get('title', ''),
                'overall_percentage': overall_percentage,
                'lessons': {
                    'completed': completed_lessons,
                    'total': total_lessons,
                    'percentage': lesson_percentage,
                },
                'assignments': {
                    'completed': completed_assignments,
                    'total': total_assignments,
                    'percentage': assignment_percentage,
                },
                'quizzes': {
                    'passed': passed_quizzes,
                    'total': total_quizzes,
                    'percentage': quiz_percentage,
                },
            })

        return Response({
            'continue_learning': continue_learning,
            'upcoming_deadlines': upcoming_deadlines,
            'course_progress_overview': course_progress,
            'is_instructor': False,
        })


class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Announcement CRUD operations.
    Only instructors can create/update/delete announcements.
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Announcement.objects.select_related('course', 'author')

    def get_serializer_class(self):
        if self.action == 'list':
            return AnnouncementListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return AnnouncementCreateSerializer
        return AnnouncementSerializer

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        # Only the course instructor can modify announcements
        if request.method not in ['GET', 'HEAD', 'OPTIONS']:
            if obj.course.instructor != request.user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Only the course instructor can modify announcements.")

    @action(detail=True, methods=['post'])
    def pin(self, request, pk=None):
        """Pin an announcement."""
        announcement = self.get_object()
        if announcement.course.instructor != request.user:
            return Response(
                {'error': 'Only the course instructor can pin announcements'},
                status=status.HTTP_403_FORBIDDEN
            )
        announcement.is_pinned = True
        announcement.save(update_fields=['is_pinned'])
        return Response(AnnouncementSerializer(announcement).data)

    @action(detail=True, methods=['post'])
    def unpin(self, request, pk=None):
        """Unpin an announcement."""
        announcement = self.get_object()
        if announcement.course.instructor != request.user:
            return Response(
                {'error': 'Only the course instructor can unpin announcements'},
                status=status.HTTP_403_FORBIDDEN
            )
        announcement.is_pinned = False
        announcement.save(update_fields=['is_pinned'])
        return Response(AnnouncementSerializer(announcement).data)


class CourseAnnouncementsView(generics.ListCreateAPIView):
    """
    List announcements for a course or create a new announcement.
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AnnouncementCreateSerializer
        return AnnouncementListSerializer

    def get_queryset(self):
        course_code = self.kwargs['course_code']
        course = get_object_or_404(Course, code=course_code)

        # Verify user is enrolled or instructor
        if course.instructor != self.request.user:
            if not Enrollment.objects.filter(
                user=self.request.user,
                course=course,
                is_active=True
            ).exists():
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You must be enrolled in this course.")

        return Announcement.objects.filter(course=course).select_related('author')

    def perform_create(self, serializer):
        course = get_object_or_404(Course, code=self.kwargs['course_code'])

        # Only instructor can create announcements
        if course.instructor != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only the course instructor can create announcements.")

        announcement = serializer.save(course=course, author=self.request.user)

        # Create notifications for enrolled students
        self._notify_enrolled_students(announcement)

    def _notify_enrolled_students(self, announcement):
        """Create notifications and optionally send emails to enrolled students."""
        from notifications.models import Notification
        from accounts.models import UserPreferences
        from core.email import send_announcement_email, send_emails_async
        from django.conf import settings

        # Prefetch user preferences to avoid N+1 queries
        enrollments = Enrollment.objects.filter(
            course=announcement.course, is_active=True
        ).select_related('user').prefetch_related('user__userpreferences')
        notifications = []
        email_tasks = []

        for enrollment in enrollments:
            # Create in-app notification
            notifications.append(Notification(
                recipient=enrollment.user,
                type='announcement',
                title=f"New Announcement: {announcement.title}",
                message=announcement.content[:200] + ('...' if len(announcement.content) > 200 else ''),
                related_url=f"/courses/{announcement.course.code}/announcements/{announcement.id}"
            ))

            # Queue email if announcement has send_email=True and user has opted in
            if announcement.send_email:
                # Check preferences (already prefetched)
                should_send = True
                try:
                    prefs = enrollment.user.userpreferences
                    should_send = prefs.email_announcements
                except UserPreferences.DoesNotExist:
                    pass

                if should_send:
                    email_tasks.append((
                        send_announcement_email,
                        (),
                        {
                            'recipient_email': enrollment.user.email,
                            'course_title': announcement.course.title,
                            'announcement_title': announcement.title,
                            'announcement_content': announcement.content,
                            'announcement_url': f"{settings.FRONTEND_URL}/courses/{announcement.course.code}/announcements/{announcement.id}",
                            'instructor_name': announcement.author.get_full_name() or announcement.author.email,
                            'posted_date': announcement.created_at.strftime('%B %d, %Y'),
                        }
                    ))

        if notifications:
            Notification.objects.bulk_create(notifications)

        # Send emails asynchronously to avoid blocking
        if email_tasks:
            send_emails_async(email_tasks)


def calculate_letter_grade(percentage):
    """Convert percentage to letter grade."""
    if percentage >= 90:
        return 'A'
    elif percentage >= 80:
        return 'B'
    elif percentage >= 70:
        return 'C'
    elif percentage >= 60:
        return 'D'
    else:
        return 'F'


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def gradebook(request, course_code):
    """
    Get the full gradebook for a course (instructor only).
    Returns a matrix of students × gradebook items (assignments + quizzes) with grades.
    Uses weighted grades if CourseGradingConfig exists.
    """
    from assignments.models import Assignment, Submission
    from quizzes.models import Quiz, QuizAttempt
    from .models import CourseGradingConfig

    course = get_object_or_404(Course, code=course_code)

    # Only instructor can view gradebook
    if request.user != course.instructor:
        return Response(
            {'error': 'Only the course instructor can view the gradebook.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Get grading config (for weighted grades)
    try:
        grading_config = course.grading_config
    except CourseGradingConfig.DoesNotExist:
        grading_config = None

    # Get all assignments for the course, ordered by unit and then order
    assignments = Assignment.objects.filter(
        unit__course=course
    ).select_related('unit').order_by('unit__order', 'order')

    # Get all quizzes for the course, ordered by unit and then order
    quizzes = Quiz.objects.filter(
        unit__course=course
    ).select_related('unit').order_by('unit__order', 'order')

    # Get all actively enrolled students
    enrollments = Enrollment.objects.filter(
        course=course,
        is_active=True
    ).select_related('user').order_by('user__last_name', 'user__first_name')

    # Get all submissions for this course
    submissions = Submission.objects.filter(
        assignment__unit__course=course
    ).select_related('grade')

    # Build submission lookup: {(student_id, assignment_id): submission}
    submission_lookup = {
        (s.student_id, s.assignment_id): s for s in submissions
    }

    # Get all quiz attempts and build best score lookup
    quiz_attempts = QuizAttempt.objects.filter(
        quiz__unit__course=course
    ).select_related('quiz')

    # Build quiz best lookup: {(student_id, quiz_id): best_attempt}
    quiz_best_lookup = {}
    for attempt in quiz_attempts:
        key = (attempt.student_id, attempt.quiz_id)
        if key not in quiz_best_lookup or attempt.score > quiz_best_lookup[key].score:
            quiz_best_lookup[key] = attempt

    # Build combined gradebook items list (assignments + quizzes)
    gradebook_items = []

    for assignment in assignments:
        gradebook_items.append({
            'id': assignment.id,
            'title': assignment.title,
            'unit_title': assignment.unit.title,
            'max_points': assignment.max_points,
            'due_date': assignment.due_date.isoformat() if assignment.due_date else None,
            'type': 'assignment',
        })

    for quiz in quizzes:
        gradebook_items.append({
            'id': quiz.id,
            'title': quiz.title,
            'unit_title': quiz.unit.title,
            'max_points': quiz.points,
            'due_date': None,
            'type': 'quiz',
        })

    # Calculate total possible points (assignments + quizzes)
    total_possible = sum(a.max_points for a in assignments) + sum(q.points for q in quizzes)

    # Build students data with grades
    students_data = []
    for enrollment in enrollments:
        student = enrollment.user
        grades = []
        total_earned = 0
        graded_possible = 0

        # Track category totals for weighted grading
        assignment_earned = 0
        assignment_possible = 0
        quiz_earned = 0
        quiz_possible = 0

        # Process assignment grades
        for assignment in assignments:
            submission = submission_lookup.get((student.id, assignment.id))

            if submission:
                if submission.status == 'graded' and hasattr(submission, 'grade'):
                    # Apply late penalty to get final grade
                    raw_points = submission.grade.points
                    late_penalty = float(submission.late_penalty_applied or 0)
                    final_points = max(0, raw_points - late_penalty)
                    grades.append({
                        'item_id': assignment.id,
                        'item_type': 'assignment',
                        'points_earned': final_points,
                        'status': 'graded',
                        'is_late': submission.is_late,
                        'late_penalty': late_penalty if late_penalty > 0 else None,
                    })
                    total_earned += final_points
                    graded_possible += assignment.max_points
                    # Track for weighted calculation
                    assignment_earned += final_points
                    assignment_possible += assignment.max_points
                elif submission.status == 'submitted':
                    grades.append({
                        'item_id': assignment.id,
                        'item_type': 'assignment',
                        'points_earned': None,
                        'status': 'submitted',
                        'is_late': submission.is_late,
                    })
                else:
                    # Draft - treat as missing
                    is_late = False
                    if assignment.due_date and timezone.now() > assignment.due_date:
                        is_late = True
                    grades.append({
                        'item_id': assignment.id,
                        'item_type': 'assignment',
                        'points_earned': None,
                        'status': 'missing' if is_late else 'not_started',
                        'is_late': is_late,
                    })
            else:
                # No submission at all
                is_late = False
                if assignment.due_date and timezone.now() > assignment.due_date:
                    is_late = True
                grades.append({
                    'item_id': assignment.id,
                    'item_type': 'assignment',
                    'points_earned': None,
                    'status': 'missing' if is_late else 'not_started',
                    'is_late': is_late,
                })

        # Process quiz grades
        for quiz in quizzes:
            best_attempt = quiz_best_lookup.get((student.id, quiz.id))
            if best_attempt:
                points_earned = float(best_attempt.points_earned)
                grades.append({
                    'item_id': quiz.id,
                    'item_type': 'quiz',
                    'points_earned': points_earned,
                    'status': 'graded',
                    'is_late': False,
                    'passed': best_attempt.passed,
                    'score_percentage': float(best_attempt.score),
                })
                total_earned += points_earned
                graded_possible += quiz.points
                # Track for weighted calculation
                quiz_earned += points_earned
                quiz_possible += quiz.points
            else:
                grades.append({
                    'item_id': quiz.id,
                    'item_type': 'quiz',
                    'points_earned': None,
                    'status': 'not_started',
                    'is_late': False,
                })

        # Calculate percentage - use weighted if config exists
        if grading_config:
            # Calculate category percentages
            assignment_pct = (assignment_earned / assignment_possible * 100) if assignment_possible > 0 else None
            quiz_pct = (quiz_earned / quiz_possible * 100) if quiz_possible > 0 else None

            # Calculate lesson completion for participation
            total_lessons = Lesson.objects.filter(unit__course=course).count()
            if total_lessons > 0:
                completed_lessons = LessonProgress.objects.filter(
                    user=student,
                    lesson__unit__course=course,
                    completed=True
                ).count()
                participation_pct = (completed_lessons / total_lessons) * 100
            else:
                participation_pct = None

            # Calculate weighted average
            weighted_total = 0
            weight_sum = 0

            if assignment_pct is not None and float(grading_config.assignments_weight) > 0:
                weighted_total += assignment_pct * float(grading_config.assignments_weight)
                weight_sum += float(grading_config.assignments_weight)

            if quiz_pct is not None and float(grading_config.quizzes_weight) > 0:
                weighted_total += quiz_pct * float(grading_config.quizzes_weight)
                weight_sum += float(grading_config.quizzes_weight)

            if participation_pct is not None and float(grading_config.participation_weight) > 0:
                weighted_total += participation_pct * float(grading_config.participation_weight)
                weight_sum += float(grading_config.participation_weight)

            if weight_sum > 0:
                percentage = round(weighted_total / weight_sum, 1)
            else:
                percentage = None
        else:
            # Simple percentage based on graded items only
            if graded_possible > 0:
                percentage = round((total_earned / graded_possible) * 100, 1)
            else:
                percentage = None

        students_data.append({
            'id': student.id,
            'name': f"{student.first_name} {student.last_name}",
            'email': student.email,
            'grades': grades,
            'total_earned': round(total_earned, 2),
            'total_possible': graded_possible,  # Only count graded items
            'percentage': percentage,
            'letter_grade': calculate_letter_grade(percentage) if percentage is not None else None,
        })

    return Response({
        'course': {
            'code': course.code,
            'title': course.title,
        },
        'gradebook_items': gradebook_items,
        'students': students_data,
        'total_possible': total_possible,
        'has_quizzes': quizzes.exists(),
        'has_assignments': assignments.exists(),
        'grading_config': {
            'assignments_weight': float(grading_config.assignments_weight),
            'quizzes_weight': float(grading_config.quizzes_weight),
            'participation_weight': float(grading_config.participation_weight),
        } if grading_config else None,
    })


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def gradebook_export(request, course_code):
    """
    Export gradebook as CSV (instructor only).
    Includes both assignments and quizzes.
    """
    from assignments.models import Assignment, Submission
    from quizzes.models import Quiz, QuizAttempt

    course = get_object_or_404(Course, code=course_code)

    # Only instructor can export gradebook
    if request.user != course.instructor:
        return Response(
            {'error': 'Only the course instructor can export the gradebook.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Get all assignments for the course
    assignments = Assignment.objects.filter(
        unit__course=course
    ).select_related('unit').order_by('unit__order', 'order')

    # Get all quizzes for the course
    quizzes = Quiz.objects.filter(
        unit__course=course
    ).select_related('unit').order_by('unit__order', 'order')

    # Get all actively enrolled students
    enrollments = Enrollment.objects.filter(
        course=course,
        is_active=True
    ).select_related('user').order_by('user__last_name', 'user__first_name')

    # Get all submissions
    submissions = Submission.objects.filter(
        assignment__unit__course=course
    ).select_related('grade')

    submission_lookup = {
        (s.student_id, s.assignment_id): s for s in submissions
    }

    # Get all quiz attempts and build best score lookup
    quiz_attempts = QuizAttempt.objects.filter(
        quiz__unit__course=course
    ).select_related('quiz')

    quiz_best_lookup = {}
    for attempt in quiz_attempts:
        key = (attempt.student_id, attempt.quiz_id)
        if key not in quiz_best_lookup or attempt.score > quiz_best_lookup[key].score:
            quiz_best_lookup[key] = attempt

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{course.code}_gradebook.csv"'

    writer = csv.writer(response)

    # Header row
    header = ['Student Name', 'Email']
    for assignment in assignments:
        header.append(f"[A] {assignment.title} ({assignment.max_points})")
    for quiz in quizzes:
        header.append(f"[Q] {quiz.title} ({quiz.points})")
    header.extend(['Total Earned', 'Total Possible', 'Percentage', 'Letter Grade'])
    writer.writerow(header)

    # Data rows
    for enrollment in enrollments:
        student = enrollment.user
        row = [f"{student.first_name} {student.last_name}", student.email]

        total_earned = 0
        graded_possible = 0

        # Process assignments
        for assignment in assignments:
            submission = submission_lookup.get((student.id, assignment.id))

            if submission and submission.status == 'graded' and hasattr(submission, 'grade'):
                points = submission.grade.points
                row.append(points)
                total_earned += points
                graded_possible += assignment.max_points
            elif submission and submission.status == 'submitted':
                row.append('Pending')
            else:
                is_late = assignment.due_date and timezone.now() > assignment.due_date
                row.append('Missing' if is_late else '-')

        # Process quizzes
        for quiz in quizzes:
            best_attempt = quiz_best_lookup.get((student.id, quiz.id))
            if best_attempt:
                points = float(best_attempt.points_earned)
                row.append(points)
                total_earned += points
                graded_possible += quiz.points
            else:
                row.append('-')

        if graded_possible > 0:
            percentage = round((total_earned / graded_possible) * 100, 1)
            letter = calculate_letter_grade(percentage)
        else:
            percentage = '-'
            letter = '-'

        row.extend([total_earned, graded_possible, percentage, letter])
        writer.writerow(row)

    return response


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def student_roster(request, course_code):
    """
    Get the student roster for a course (instructor only).
    Returns list of enrolled students with activity data.
    """
    course = get_object_or_404(Course, code=course_code)

    if request.user != course.instructor:
        return Response(
            {'error': 'Only the course instructor can view the student roster.'},
            status=status.HTTP_403_FORBIDDEN
        )

    enrollments = Enrollment.objects.filter(
        course=course,
        is_active=True
    ).select_related('user').order_by('user__last_name', 'user__first_name')

    serializer = StudentRosterSerializer(enrollments, many=True)
    return Response(serializer.data)


@api_view(['DELETE'])
@perm_classes([IsAuthenticated])
def remove_student(request, course_code, enrollment_id):
    """
    Remove a student from a course (soft delete - preserves grades).
    """
    course = get_object_or_404(Course, code=course_code)

    if request.user != course.instructor:
        return Response(
            {'error': 'Only the course instructor can remove students.'},
            status=status.HTTP_403_FORBIDDEN
        )

    enrollment = get_object_or_404(Enrollment, id=enrollment_id, course=course)

    # Soft delete - preserve grades
    enrollment.is_active = False
    enrollment.save(update_fields=['is_active'])

    return Response({'message': 'Student removed from course.'})


@api_view(['POST'])
@perm_classes([IsAuthenticated])
def send_course_invite(request, course_code):
    """
    Send course invitation email to a student.
    """
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError

    course = get_object_or_404(Course, code=course_code)

    if request.user != course.instructor:
        return Response(
            {'error': 'Only the course instructor can send invitations.'},
            status=status.HTTP_403_FORBIDDEN
        )

    email = request.data.get('email', '').strip().lower()
    if not email:
        return Response(
            {'error': 'Email address is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate email format
    try:
        validate_email(email)
    except ValidationError:
        return Response(
            {'error': 'Invalid email address.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check if already enrolled
    from accounts.models import User
    existing_user = User.objects.filter(email=email).first()
    if existing_user:
        if Enrollment.objects.filter(user=existing_user, course=course, is_active=True).exists():
            return Response(
                {'error': 'This student is already enrolled in the course.'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # Send invitation email using template
    from core.email import send_course_invitation_email

    instructor_name = course.instructor.get_full_name() or course.instructor.email

    success = send_course_invitation_email(
        recipient_email=email,
        course_title=course.title,
        instructor_name=instructor_name,
        enrollment_code=course.enrollment_code
    )

    if not success:
        return Response(
            {'error': 'Failed to send email. Please try again later.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response({
        'message': f'Invitation sent to {email}',
        'email': email
    })


@api_view(['POST'])
@perm_classes([IsAuthenticated])
def update_course_activity(request, course_code):
    """
    Update the last_activity_at timestamp for the current user's enrollment.
    Called when a student accesses course content.
    """
    course = get_object_or_404(Course, code=course_code)

    try:
        enrollment = Enrollment.objects.get(
            user=request.user,
            course=course,
            is_active=True
        )
        enrollment.update_activity()
        return Response({'status': 'updated'})
    except Enrollment.DoesNotExist:
        return Response({'status': 'not_enrolled'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET', 'PUT'])
@perm_classes([IsAuthenticated])
def course_grading_config(request, course_code):
    """Get or update course grading configuration."""
    from .models import CourseGradingConfig
    from .serializers import GradingConfigSerializer

    course = get_object_or_404(Course, code=course_code)

    # GET is allowed for enrolled students and instructor
    # PUT is only for instructor
    if request.method == 'PUT' and request.user != course.instructor:
        return Response(
            {'error': 'Only the course instructor can update grading settings.'},
            status=status.HTTP_403_FORBIDDEN
        )

    if request.method == 'GET':
        # Check if user has access (instructor or enrolled)
        is_enrolled = Enrollment.objects.filter(
            user=request.user, course=course, is_active=True
        ).exists()
        if request.user != course.instructor and not is_enrolled:
            return Response(
                {'error': 'You must be enrolled in this course.'},
                status=status.HTTP_403_FORBIDDEN
            )

    # Get or create config with defaults
    config, created = CourseGradingConfig.objects.get_or_create(
        course=course,
        defaults={
            'assignments_weight': 50,
            'quizzes_weight': 50,
            'participation_weight': 0,
        }
    )

    if request.method == 'GET':
        serializer = GradingConfigSerializer(config)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = GradingConfigSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def student_grade_summary(request, course_code):
    """
    Get current user's grade summary for a course.
    Returns category grades, weighted average, and letter grade.
    """
    from .models import CourseGradingConfig
    from assignments.models import Assignment, Submission
    from quizzes.models import Quiz, QuizAttempt

    course = get_object_or_404(Course, code=course_code)

    # Must be enrolled or instructor
    is_enrolled = Enrollment.objects.filter(
        user=request.user, course=course, is_active=True
    ).exists()

    if request.user != course.instructor and not is_enrolled:
        return Response(
            {'error': 'You must be enrolled in this course.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Get grading config (or use defaults)
    try:
        config = course.grading_config
    except CourseGradingConfig.DoesNotExist:
        config = None

    # Calculate assignment grades
    assignments = Assignment.objects.filter(unit__course=course)
    submissions = Submission.objects.filter(
        assignment__in=assignments,
        student=request.user,
        status='graded'
    ).select_related('grade', 'assignment')

    assignment_earned = 0
    assignment_possible = 0
    for sub in submissions:
        if hasattr(sub, 'grade') and sub.grade:
            raw_points = sub.grade.points
            penalty = float(sub.late_penalty_applied or 0)
            assignment_earned += max(0, raw_points - penalty)
            assignment_possible += sub.assignment.max_points

    assignment_percentage = (
        round((assignment_earned / assignment_possible) * 100, 1)
        if assignment_possible > 0 else None
    )

    # Calculate quiz grades
    quizzes = Quiz.objects.filter(unit__course=course)
    quiz_earned = 0
    quiz_possible = 0

    for quiz in quizzes:
        best_attempt = QuizAttempt.objects.filter(
            quiz=quiz, student=request.user
        ).order_by('-score').first()

        if best_attempt:
            quiz_earned += float(best_attempt.points_earned)
            quiz_possible += quiz.points

    quiz_percentage = (
        round((quiz_earned / quiz_possible) * 100, 1)
        if quiz_possible > 0 else None
    )

    # Calculate participation (lesson completion)
    total_lessons = Lesson.objects.filter(unit__course=course).count()
    completed_lessons = LessonProgress.objects.filter(
        user=request.user,
        lesson__unit__course=course,
        completed=True
    ).count()

    participation_percentage = (
        round((completed_lessons / total_lessons) * 100, 1)
        if total_lessons > 0 else None
    )

    # Calculate weighted average
    weighted_percentage = None
    if config:
        weighted_total = 0
        weight_sum = 0

        if assignment_percentage is not None and float(config.assignments_weight) > 0:
            weighted_total += assignment_percentage * float(config.assignments_weight)
            weight_sum += float(config.assignments_weight)

        if quiz_percentage is not None and float(config.quizzes_weight) > 0:
            weighted_total += quiz_percentage * float(config.quizzes_weight)
            weight_sum += float(config.quizzes_weight)

        if participation_percentage is not None and float(config.participation_weight) > 0:
            weighted_total += participation_percentage * float(config.participation_weight)
            weight_sum += float(config.participation_weight)

        if weight_sum > 0:
            weighted_percentage = round(weighted_total / weight_sum, 1)
    else:
        # Default: simple average of available categories
        percentages = [p for p in [assignment_percentage, quiz_percentage] if p is not None]
        if percentages:
            weighted_percentage = round(sum(percentages) / len(percentages), 1)

    # Calculate letter grade
    letter_grade = calculate_letter_grade(weighted_percentage) if weighted_percentage is not None else None

    # Build individual grade items for display
    grade_items = []

    # Get all assignments with their submission status
    all_assignments = Assignment.objects.filter(
        unit__course=course
    ).select_related('unit').order_by('unit__order', 'order')

    submission_lookup = {}
    all_submissions = Submission.objects.filter(
        assignment__unit__course=course,
        student=request.user
    ).select_related('grade', 'assignment')
    for sub in all_submissions:
        submission_lookup[sub.assignment_id] = sub

    now = timezone.now()
    for assignment in all_assignments:
        # Skip assignments that aren't available yet (available_from in future)
        if assignment.available_from and assignment.available_from > now:
            continue

        sub = submission_lookup.get(assignment.id)
        if sub:
            # Has a submission
            if sub.status == 'graded' and hasattr(sub, 'grade') and sub.grade:
                points = sub.grade.points
                penalty = float(sub.late_penalty_applied or 0)
                final_points = max(0, points - penalty)
                item_status = 'graded'
            elif sub.status == 'submitted':
                final_points = None
                item_status = 'submitted'
            else:
                # Draft status
                final_points = None
                item_status = 'not_started'
            is_late = sub.is_late
        else:
            # No submission
            final_points = None
            is_late = False
            # Check if past due date OR past available_until
            past_due = assignment.due_date and assignment.due_date < now
            past_available = assignment.available_until and assignment.available_until < now
            if past_due or past_available:
                item_status = 'missing'
            else:
                item_status = 'not_started'

        grade_items.append({
            'id': assignment.id,
            'type': 'assignment',
            'title': assignment.title,
            'unit_title': assignment.unit.title,
            'max_points': assignment.max_points,
            'points_earned': round(final_points, 2) if final_points is not None else None,
            'status': item_status,
            'is_late': is_late,
            'due_date': assignment.due_date.isoformat() if assignment.due_date else None,
        })

    # Get all quizzes with their best attempt
    all_quizzes = Quiz.objects.filter(
        unit__course=course
    ).select_related('unit').order_by('unit__order', 'order')

    for quiz in all_quizzes:
        best_attempt = QuizAttempt.objects.filter(
            quiz=quiz, student=request.user
        ).order_by('-score').first()

        if best_attempt:
            grade_items.append({
                'id': quiz.id,
                'type': 'quiz',
                'title': quiz.title,
                'unit_title': quiz.unit.title,
                'max_points': quiz.points,
                'points_earned': float(best_attempt.points_earned),
                'status': 'graded',
                'is_late': False,  # Quizzes don't have due dates currently
                'due_date': None,
                'passed': best_attempt.passed,
            })
        else:
            grade_items.append({
                'id': quiz.id,
                'type': 'quiz',
                'title': quiz.title,
                'unit_title': quiz.unit.title,
                'max_points': quiz.points,
                'points_earned': None,
                'status': 'not_started',
                'is_late': False,
                'due_date': None,
                'passed': None,
            })

    return Response({
        'course': {
            'code': course.code,
            'title': course.title,
        },
        'assignments': {
            'earned': round(assignment_earned, 2),
            'possible': assignment_possible,
            'percentage': assignment_percentage,
            'weight': float(config.assignments_weight) if config else None,
        },
        'quizzes': {
            'earned': round(quiz_earned, 2),
            'possible': quiz_possible,
            'percentage': quiz_percentage,
            'weight': float(config.quizzes_weight) if config else None,
        },
        'participation': {
            'completed': completed_lessons,
            'total': total_lessons,
            'percentage': participation_percentage,
            'weight': float(config.participation_weight) if config else None,
        },
        'overall': {
            'percentage': weighted_percentage,
            'letter_grade': letter_grade,
        },
        'is_weighted': config is not None,
        'grade_items': grade_items,
    })


# ============================================
# Lesson Questions (Mini Comprehension Quizzes)
# ============================================

@api_view(['GET', 'POST'])
@perm_classes([IsAuthenticated])
def lesson_questions(request, lesson_id):
    """
    GET: Get questions for a lesson.
        - Instructors see correct answers
        - Students see questions without correct answer indicators
    POST: Create a new question (instructor only).
    """
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    course = lesson.unit.course

    # Check access
    is_instructor = request.user == course.instructor
    is_enrolled = Enrollment.objects.filter(
        user=request.user, course=course, is_active=True
    ).exists()

    if not is_instructor and not is_enrolled:
        return Response(
            {'error': 'You must be enrolled in this course.'},
            status=status.HTTP_403_FORBIDDEN
        )

    if request.method == 'GET':
        questions = lesson.questions.prefetch_related('choices').all()

        if is_instructor:
            serializer = LessonQuestionSerializer(questions, many=True)
        else:
            serializer = LessonQuestionStudentSerializer(questions, many=True)

        return Response(serializer.data)

    elif request.method == 'POST':
        if not is_instructor:
            return Response(
                {'error': 'Only the instructor can create questions.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = LessonQuestionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Determine order
        max_order = lesson.questions.aggregate(max_order=Max('order'))['max_order'] or 0

        # Create the question
        question = LessonQuestion.objects.create(
            lesson=lesson,
            text=data['text'],
            order=data.get('order', max_order + 1)
        )

        # Create choices
        for i, choice_data in enumerate(data['choices']):
            LessonQuestionChoice.objects.create(
                question=question,
                text=choice_data['text'],
                is_correct=choice_data.get('is_correct', False),
                order=choice_data.get('order', i)
            )

        # Invalidate lesson completions - students need to answer the new question
        # Reset completed status for all students who completed this lesson
        LessonProgress.objects.filter(lesson=lesson, completed=True).update(
            completed=False,
            completed_at=None
        )

        # Return the created question with choices
        question.refresh_from_db()
        return Response(
            LessonQuestionSerializer(question).data,
            status=status.HTTP_201_CREATED
        )


@api_view(['GET', 'PUT', 'DELETE'])
@perm_classes([IsAuthenticated])
def lesson_question_detail(request, lesson_id, question_id):
    """
    GET: Get a single question.
    PUT: Update a question (instructor only).
    DELETE: Delete a question (instructor only).
    """
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    question = get_object_or_404(LessonQuestion, pk=question_id, lesson=lesson)
    course = lesson.unit.course

    # Check access
    is_instructor = request.user == course.instructor
    is_enrolled = Enrollment.objects.filter(
        user=request.user, course=course, is_active=True
    ).exists()

    if not is_instructor and not is_enrolled:
        return Response(
            {'error': 'You must be enrolled in this course.'},
            status=status.HTTP_403_FORBIDDEN
        )

    if request.method == 'GET':
        if is_instructor:
            serializer = LessonQuestionSerializer(question)
        else:
            serializer = LessonQuestionStudentSerializer(question)
        return Response(serializer.data)

    elif request.method == 'PUT':
        if not is_instructor:
            return Response(
                {'error': 'Only the instructor can update questions.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = LessonQuestionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Update question text and order
        question.text = data['text']
        if 'order' in data:
            question.order = data['order']
        question.save()

        # Delete existing student answers since question is being modified
        # Students will need to re-answer the updated question
        question.answers.all().delete()

        # Clear all quiz attempts for this lesson since questions changed
        # Students will need to retake the quiz
        LessonQuizAttempt.objects.filter(lesson=lesson).delete()

        # Invalidate lesson completions since quiz content changed
        LessonProgress.objects.filter(lesson=lesson, completed=True).update(
            completed=False,
            completed_at=None
        )

        # Delete existing choices and recreate
        question.choices.all().delete()
        for i, choice_data in enumerate(data['choices']):
            LessonQuestionChoice.objects.create(
                question=question,
                text=choice_data['text'],
                is_correct=choice_data.get('is_correct', False),
                order=choice_data.get('order', i)
            )

        question.refresh_from_db()
        return Response(LessonQuestionSerializer(question).data)

    elif request.method == 'DELETE':
        if not is_instructor:
            return Response(
                {'error': 'Only the instructor can delete questions.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Clear all quiz attempts for this lesson since questions changed
        LessonQuizAttempt.objects.filter(lesson=lesson).delete()

        # Clear all answers for this lesson
        LessonQuestionAnswer.objects.filter(question__lesson=lesson).delete()

        # Invalidate lesson completions since quiz content changed
        LessonProgress.objects.filter(lesson=lesson, completed=True).update(
            completed=False,
            completed_at=None
        )

        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@perm_classes([IsAuthenticated])
def answer_lesson_question(request, lesson_id):
    """
    Submit an answer to a lesson question.
    Returns whether the answer was correct and the correct answer.
    """
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    course = lesson.unit.course

    # Check enrollment
    is_enrolled = Enrollment.objects.filter(
        user=request.user, course=course, is_active=True
    ).exists()
    is_instructor = request.user == course.instructor

    if not is_enrolled and not is_instructor:
        return Response(
            {'error': 'You must be enrolled in this course.'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = AnswerQuestionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    question = serializer.validated_data['question']
    choice = serializer.validated_data['choice']

    # Verify question belongs to this lesson
    if question.lesson_id != lesson.id:
        return Response(
            {'error': 'Question does not belong to this lesson.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Create or update the answer
    answer, created = LessonQuestionAnswer.objects.update_or_create(
        user=request.user,
        question=question,
        defaults={'selected_choice': choice}
    )

    # Find the correct choice to return in response
    correct_choice = question.choices.filter(is_correct=True).first()

    return Response({
        'is_correct': answer.is_correct,
        'correct_choice_id': correct_choice.id if correct_choice else None,
        'correct_choice_text': correct_choice.text if correct_choice else None,
    })


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def lesson_questions_status(request, lesson_id):
    """
    Get the status of a student's progress on lesson questions.
    Returns total questions, answered count, correct count, and whether they can complete the lesson.
    """
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    course = lesson.unit.course

    # Check enrollment
    is_enrolled = Enrollment.objects.filter(
        user=request.user, course=course, is_active=True
    ).exists()
    is_instructor = request.user == course.instructor

    if not is_enrolled and not is_instructor:
        return Response(
            {'error': 'You must be enrolled in this course.'},
            status=status.HTTP_403_FORBIDDEN
        )

    total_questions = lesson.questions.count()

    if total_questions == 0:
        return Response({
            'total_questions': 0,
            'answered_questions': 0,
            'correct_answers': 0,
            'all_correct': True,
            'can_complete_lesson': True,
        })

    answers = LessonQuestionAnswer.objects.filter(
        user=request.user,
        question__lesson=lesson
    )

    answered_count = answers.count()
    correct_count = answers.filter(is_correct=True).count()
    all_correct = correct_count == total_questions

    # Get attempt info
    attempts = LessonQuizAttempt.objects.filter(
        user=request.user,
        lesson=lesson
    )
    attempt_count = attempts.count()
    best_attempt = attempts.filter(passed=True).first()
    max_attempts = lesson.max_quiz_attempts  # 0 = unlimited

    # Check if can attempt
    can_attempt = max_attempts == 0 or attempt_count < max_attempts
    attempts_remaining = None if max_attempts == 0 else max(0, max_attempts - attempt_count)

    has_passed = best_attempt is not None

    return Response({
        'total_questions': total_questions,
        'answered_questions': answered_count,
        'correct_answers': correct_count,
        'all_correct': all_correct,
        'can_complete_lesson': has_passed or all_correct,
        'attempt_count': attempt_count,
        'max_attempts': max_attempts if max_attempts > 0 else None,
        'attempts_remaining': attempts_remaining,
        'can_attempt': can_attempt,
        'has_passed': has_passed,
    })


@api_view(['POST'])
@perm_classes([IsAuthenticated])
def submit_lesson_quiz(request, lesson_id):
    """
    Submit all answers for a lesson quiz at once.
    Creates an attempt record and stores all answers.
    """
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    course = lesson.unit.course

    # Check enrollment
    is_enrolled = Enrollment.objects.filter(
        user=request.user, course=course, is_active=True
    ).exists()
    is_instructor = request.user == course.instructor

    if not is_enrolled and not is_instructor:
        return Response(
            {'error': 'You must be enrolled in this course.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Check if quiz has questions
    questions = lesson.questions.prefetch_related('choices').all()
    total_questions = questions.count()

    if total_questions == 0:
        return Response(
            {'error': 'This lesson has no quiz questions.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check attempt limits
    max_attempts = lesson.max_quiz_attempts
    current_attempts = LessonQuizAttempt.objects.filter(
        user=request.user,
        lesson=lesson
    ).count()

    if max_attempts > 0 and current_attempts >= max_attempts:
        return Response(
            {'error': f'You have reached the maximum number of attempts ({max_attempts}).'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate answers format
    answers = request.data.get('answers', {})
    if not isinstance(answers, dict):
        return Response(
            {'error': 'Answers must be a dictionary of question_id: choice_id'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Process answers
    correct_count = 0
    results = []

    for question in questions:
        choice_id = answers.get(str(question.id))

        if choice_id is None:
            results.append({
                'question_id': question.id,
                'is_correct': False,
                'selected_choice_id': None,
                'correct_choice_id': question.choices.filter(is_correct=True).first().id if question.choices.filter(is_correct=True).exists() else None,
            })
            continue

        try:
            choice = question.choices.get(id=choice_id)
        except LessonQuestionChoice.DoesNotExist:
            results.append({
                'question_id': question.id,
                'is_correct': False,
                'selected_choice_id': choice_id,
                'correct_choice_id': question.choices.filter(is_correct=True).first().id if question.choices.filter(is_correct=True).exists() else None,
            })
            continue

        is_correct = choice.is_correct
        if is_correct:
            correct_count += 1

        # Save the answer
        LessonQuestionAnswer.objects.update_or_create(
            user=request.user,
            question=question,
            defaults={'selected_choice': choice}
        )

        correct_choice = question.choices.filter(is_correct=True).first()
        results.append({
            'question_id': question.id,
            'is_correct': is_correct,
            'selected_choice_id': choice.id,
            'correct_choice_id': correct_choice.id if correct_choice else None,
        })

    # Create attempt record
    passed = correct_count == total_questions
    attempt = LessonQuizAttempt.objects.create(
        user=request.user,
        lesson=lesson,
        attempt_number=current_attempts + 1,
        score=correct_count,
        total_questions=total_questions,
        passed=passed,
        completed_at=timezone.now()
    )

    # Calculate remaining attempts
    attempts_remaining = None
    if max_attempts > 0:
        attempts_remaining = max(0, max_attempts - (current_attempts + 1))

    return Response({
        'attempt_number': attempt.attempt_number,
        'score': correct_count,
        'total_questions': total_questions,
        'percentage': attempt.percentage,
        'passed': passed,
        'results': results,
        'attempts_remaining': attempts_remaining,
        'can_complete_lesson': passed,
    })


# ============================================
# Lesson Attachments
# ============================================

@api_view(['GET', 'POST'])
@perm_classes([IsAuthenticated])
def lesson_attachments(request, lesson_id):
    """
    GET: List attachments for a lesson (students and instructors)
    POST: Upload attachment to a lesson (instructor only)
    """
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    course = lesson.unit.course

    # Check access - must be instructor or enrolled student
    is_instructor = request.user == course.instructor
    is_enrolled = Enrollment.objects.filter(
        user=request.user, course=course, is_active=True
    ).exists()

    if not is_instructor and not is_enrolled:
        return Response(
            {'error': 'Access denied'},
            status=status.HTTP_403_FORBIDDEN
        )

    if request.method == 'GET':
        attachments = lesson.attachments.all()
        serializer = LessonAttachmentSerializer(
            attachments, many=True, context={'request': request}
        )
        return Response(serializer.data)

    elif request.method == 'POST':
        # Only instructor can upload
        if not is_instructor:
            return Response(
                {'error': 'Only instructors can upload attachments'},
                status=status.HTTP_403_FORBIDDEN
            )

        files = request.FILES.getlist('files')
        if not files:
            return Response(
                {'error': 'No files provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check file limit (max 10 per lesson)
        current_count = lesson.attachments.count()
        if current_count + len(files) > 10:
            remaining = 10 - current_count
            return Response(
                {'error': f'Maximum 10 attachments per lesson. You have {current_count}, can add {remaining} more.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Allowed file extensions (whitelist)
        ALLOWED_EXTENSIONS = {
            'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx',
            'txt', 'md', 'csv',
            'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg',
            'zip', 'rar', '7z',
            'mp3', 'wav', 'mp4', 'webm', 'mov',
            'py', 'js', 'html', 'css', 'json'  # code files
        }

        # Validate file sizes (max 10MB each) and file types
        max_size = 10 * 1024 * 1024  # 10MB
        for f in files:
            if f.size > max_size:
                return Response(
                    {'error': f'File "{f.name}" exceeds 10MB limit'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate file extension
            file_ext = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
            if not file_ext or file_ext not in ALLOWED_EXTENSIONS:
                return Response(
                    {'error': f'File type ".{file_ext}" is not allowed. Allowed types: {", ".join(sorted(ALLOWED_EXTENSIONS))}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Create attachments
        created = []
        for f in files:
            # Get file extension
            file_type = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
            attachment = LessonAttachment.objects.create(
                lesson=lesson,
                file=f,
                filename=f.name,
                file_type=file_type,
                file_size=f.size
            )
            created.append(attachment)

        serializer = LessonAttachmentSerializer(
            created, many=True, context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@perm_classes([IsAuthenticated])
def lesson_attachment_detail(request, lesson_id, attachment_id):
    """Delete an attachment (instructor only)."""
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    course = lesson.unit.course

    # Only instructor can delete
    if request.user != course.instructor:
        return Response(
            {'error': 'Only instructors can delete attachments'},
            status=status.HTTP_403_FORBIDDEN
        )

    attachment = get_object_or_404(LessonAttachment, pk=attachment_id, lesson=lesson)

    # Delete the file from storage
    if attachment.file:
        attachment.file.delete(save=False)

    attachment.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
