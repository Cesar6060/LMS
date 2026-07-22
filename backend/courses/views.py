import csv
from django.conf import settings
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes as perm_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import models, transaction
from django.db.models import F, Max, Count
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta

from .models import Course, Unit, Lesson, Enrollment, LessonProgress, Announcement, LessonQuestion, LessonQuestionChoice, LessonQuestionAnswer, LessonQuizAttempt, LessonAttemptAnswer, LessonAttachment, LessonSection
from .serializers import (
    CourseSerializer, CourseListSerializer, CourseCreateSerializer,
    InstructorCourseSerializer, UnitSerializer, UnitCreateSerializer,
    LessonSerializer, LessonListSerializer, LessonCreateSerializer,
    EnrollmentSerializer, EnrollmentCreateSerializer, LessonProgressSerializer,
    LessonProgressUpdateSerializer, AnnouncementSerializer,
    AnnouncementListSerializer, AnnouncementCreateSerializer,
    StudentRosterSerializer, LessonQuestionSerializer, LessonQuestionStudentSerializer,
    LessonQuestionCreateSerializer, AnswerQuestionSerializer, LessonAttachmentSerializer,
    LessonSectionSerializer, LessonSectionCreateSerializer,
    LessonSectionBulkCreateSerializer, CourseMapSerializer
)
from rest_framework.exceptions import PermissionDenied
from .permissions import (
    IsInstructor, IsInstructorOrReadOnly, IsCourseInstructor,
    IsEnrolledOrInstructor,
    is_course_instructor, is_enrolled, can_access_course,
    require_course_instructor, require_course_access, require_enrollment,
    accessible_course_ids,
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
        require_course_instructor(
            request.user, course,
            "Only the course instructor can regenerate the code."
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
    permission_classes = [IsAuthenticated, IsEnrolledOrInstructor]

    def get_queryset(self):
        queryset = Unit.objects.select_related('course').prefetch_related('lessons')
        if self.action == 'list':
            # List only shows units of courses the user teaches or is enrolled in;
            # detail actions keep the full queryset so object permissions return 403
            queryset = queryset.filter(course_id__in=accessible_course_ids(self.request.user))
        return queryset

    def perform_create(self, serializer):
        # UnitCreateSerializer has no course field; units are created via the
        # course-scoped endpoint where ownership is checked.
        raise PermissionDenied("Create units via /api/courses/{code}/units/.")

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
        except (TypeError, ValueError):
            return Response(
                {'error': 'Order must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )

        course = unit.course

        with transaction.atomic():
            others = list(
                Unit.objects.filter(course=course)
                .exclude(pk=unit.pk)
                .order_by('order')
            )
            position = max(1, min(new_order, len(others) + 1))
            sequence = others[:position - 1] + [unit] + others[position - 1:]

            # unique_together('course', 'order') is checked per row, so shift
            # every order past the live range before assigning the final 1..n.
            offset = (
                Unit.objects.filter(course=course).aggregate(m=Max('order'))['m'] or 0
            ) + 1
            Unit.objects.filter(course=course).update(order=F('order') + offset)
            for index, item in enumerate(sequence, start=1):
                Unit.objects.filter(pk=item.pk).update(order=index)

        unit.refresh_from_db()
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
        course = get_object_or_404(Course, code=self.kwargs['course_code'])
        require_course_access(self.request.user, course)
        return Unit.objects.filter(course=course).prefetch_related('lessons')

    def perform_create(self, serializer):
        course = get_object_or_404(Course, code=self.kwargs['course_code'])
        require_course_instructor(
            self.request.user, course,
            "Only the course instructor can add units."
        )

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
        queryset = Lesson.objects.select_related('unit__course')
        if self.action == 'list':
            # List only shows lessons of courses the user teaches or is enrolled in;
            # detail actions keep the full queryset so object permissions return 403
            queryset = queryset.filter(unit__course_id__in=accessible_course_ids(self.request.user))
        return queryset

    def perform_create(self, serializer):
        # LessonCreateSerializer has no unit field; lessons are created via the
        # unit-scoped endpoint where ownership is checked.
        raise PermissionDenied("Create lessons via /api/units/{unit_id}/lessons/.")

    def get_serializer_class(self):
        if self.action == 'list':
            return LessonListSerializer
        return LessonSerializer

    @action(detail=True, methods=['patch'])
    def reorder(self, request, pk=None):
        """
        Reorder a lesson within its unit, or — when an optional `unit` id is
        given — move it to that position in another unit of the same course.
        """
        lesson = self.get_object()
        new_order = request.data.get('order')

        if new_order is None:
            return Response(
                {'error': 'Order is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            new_order = int(new_order)
        except (TypeError, ValueError):
            return Response(
                {'error': 'Order must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )

        source_unit = lesson.unit
        target_unit = source_unit

        target_unit_id = request.data.get('unit')
        if target_unit_id is not None:
            try:
                target_unit_id = int(target_unit_id)
            except (TypeError, ValueError):
                return Response(
                    {'error': 'Unit must be an integer'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            target_unit = Unit.objects.select_related('course').filter(
                pk=target_unit_id
            ).first()
            if target_unit is None or target_unit.course_id != source_unit.course_id:
                return Response(
                    {'error': 'Target unit must belong to the same course.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # get_object() already enforced instructor on the source course;
        # check the target explicitly as well.
        require_course_instructor(request.user, source_unit.course)
        require_course_instructor(request.user, target_unit.course)

        with transaction.atomic():
            target_others = list(
                Lesson.objects.filter(unit=target_unit)
                .exclude(pk=lesson.pk)
                .order_by('order')
            )
            position = max(1, min(new_order, len(target_others) + 1))
            target_sequence = (
                target_others[:position - 1] + [lesson] + target_others[position - 1:]
            )

            unit_ids = {source_unit.pk, target_unit.pk}
            # unique_together('unit', 'order') is checked per row, so shift
            # every order past the live range before assigning the final 1..n.
            offset = (
                Lesson.objects.filter(unit_id__in=unit_ids)
                .aggregate(m=Max('order'))['m'] or 0
            ) + 1
            Lesson.objects.filter(unit_id__in=unit_ids).update(order=F('order') + offset)

            if target_unit.pk != source_unit.pk:
                source_sequence = list(
                    Lesson.objects.filter(unit=source_unit)
                    .exclude(pk=lesson.pk)
                    .order_by('order')
                )
                for index, item in enumerate(source_sequence, start=1):
                    Lesson.objects.filter(pk=item.pk).update(order=index)

            for index, item in enumerate(target_sequence, start=1):
                Lesson.objects.filter(pk=item.pk).update(unit=target_unit, order=index)

        lesson.refresh_from_db()
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
        unit = get_object_or_404(Unit, pk=self.kwargs['unit_id'])
        require_course_access(self.request.user, unit.course)
        return Lesson.objects.filter(unit=unit)

    def perform_create(self, serializer):
        unit = get_object_or_404(Unit, pk=self.kwargs['unit_id'])
        require_course_instructor(
            self.request.user, unit.course,
            "Only the course instructor can add lessons."
        )

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
        require_course_access(
            self.request.user, lesson.unit.course,
            "You must be enrolled in this course."
        )

        # Get or create progress
        progress, created = LessonProgress.objects.get_or_create(
            user=self.request.user,
            lesson=lesson
        )
        return progress

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        updated = serializer.instance

        data = dict(serializer.data)
        # Award gamification XP on the not-completed -> completed transition
        # only (flagged by the update serializer). Award in the view so the
        # response shape is controlled here, not in the read serializer.
        if getattr(updated, '_just_completed', False):
            from gamification.services import award_lesson_completion
            result = award_lesson_completion(request.user, updated.lesson)
            data['gamification'] = result.as_dict()
        return Response(data)


class CourseProgressView(generics.RetrieveAPIView):
    """
    Get overall progress for a course (% complete).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, course_code):
        course = get_object_or_404(Course, code=course_code)
        require_course_access(
            request.user, course,
            "You must be enrolled in this course."
        )

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

        progress_percentage = round((completed_lessons / total_lessons) * 100, 1) if total_lessons > 0 else 0

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

        # Get courses taught by this instructor
        instructor_courses = Course.objects.filter(instructor=user)

        # Total students across all courses (active enrollments only)
        total_students = Enrollment.objects.filter(
            course__in=instructor_courses, is_active=True
        ).count()

        return Response({
            'total_students': total_students,
            'course_count': instructor_courses.count()
        })
    else:
        # Student stats

        # Get actively enrolled courses
        enrolled_course_ids = Enrollment.objects.filter(
            user=user, is_active=True
        ).values_list('course_id', flat=True)

        # Lessons completed
        lessons_completed = LessonProgress.objects.filter(
            user=user,
            completed=True
        ).count()

        return Response({
            'lessons_completed': lessons_completed,
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
    - course_progress_overview: progress bars for each enrolled course

    For Instructors:
    - course_progress_overview: summary of each course taught
    """
    from quizzes.models import QuizAttempt

    user = request.user

    if user.is_instructor:
        # Instructor Dashboard

        # Course progress overview for instructor's courses
        # Use annotations to avoid N+1 queries
        from django.db.models import Count, Q

        instructor_courses_annotated = Course.objects.filter(
            instructor=user
        ).annotate(
            total_students=Count(
                'enrollments',
                filter=Q(enrollments__is_active=True)
            )
        )

        course_progress = [
            {
                'course_code': course.code,
                'course_title': course.title,
                'student_count': course.total_students,
            }
            for course in instructor_courses_annotated
        ]

        return Response({
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

        # Course progress overview - optimized to reduce N+1 queries
        from django.db.models import Count, Q

        # Get course IDs for bulk queries
        course_ids = list(enrollments.values_list('course_id', flat=True))

        # Bulk fetch totals per course using annotations
        course_totals = Course.objects.filter(id__in=course_ids).annotate(
            total_lessons=Count('units__lessons', distinct=True),
            total_quizzes=Count('units__quizzes', distinct=True),
        ).values('id', 'code', 'title', 'total_lessons', 'total_quizzes')

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

        # Bulk fetch user's passed quizzes per course
        passed_quizzes_by_course = dict(
            QuizAttempt.objects.filter(
                student=user,
                quiz__unit__course_id__in=course_ids,
                passed=True,
                status=QuizAttempt.STATUS_COMPLETED,
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
            total_quizzes = totals.get('total_quizzes', 0)

            completed_lessons = completed_lessons_by_course.get(course_id, 0)
            passed_quizzes = passed_quizzes_by_course.get(course_id, 0)

            lesson_percentage = round((completed_lessons / total_lessons) * 100, 1) if total_lessons > 0 else 0
            quiz_percentage = round((passed_quizzes / total_quizzes) * 100, 1) if total_quizzes > 0 else 0

            # Overall progress (weighted average)
            total_items = total_lessons + total_quizzes
            if total_items > 0:
                overall_percentage = round(
                    ((completed_lessons + passed_quizzes) / total_items) * 100, 1
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
                'quizzes': {
                    'passed': passed_quizzes,
                    'total': total_quizzes,
                    'percentage': quiz_percentage,
                },
            })

        return Response({
            'continue_learning': continue_learning,
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
        queryset = Announcement.objects.select_related('course', 'author')
        if self.action == 'list':
            # List only shows announcements of courses the user teaches or is
            # enrolled in; detail keeps the full queryset so reads return 403
            queryset = queryset.filter(course_id__in=accessible_course_ids(self.request.user))
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return AnnouncementListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return AnnouncementCreateSerializer
        return AnnouncementSerializer

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            # Reads require enrollment or course ownership
            require_course_access(
                request.user, obj.course,
                "You must be enrolled in this course."
            )
        else:
            # Only the course instructor can modify announcements
            require_course_instructor(
                request.user, obj.course,
                "Only the course instructor can modify announcements."
            )

    @action(detail=True, methods=['post'])
    def pin(self, request, pk=None):
        """Pin an announcement."""
        announcement = self.get_object()
        require_course_instructor(
            request.user, announcement.course,
            "Only the course instructor can pin announcements."
        )
        announcement.is_pinned = True
        announcement.save(update_fields=['is_pinned'])
        return Response(AnnouncementSerializer(announcement).data)

    @action(detail=True, methods=['post'])
    def unpin(self, request, pk=None):
        """Unpin an announcement."""
        announcement = self.get_object()
        require_course_instructor(
            request.user, announcement.course,
            "Only the course instructor can unpin announcements."
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
        course = get_object_or_404(Course, code=self.kwargs['course_code'])
        require_course_access(
            self.request.user, course,
            "You must be enrolled in this course."
        )
        return Announcement.objects.filter(course=course).select_related('author')

    def perform_create(self, serializer):
        course = get_object_or_404(Course, code=self.kwargs['course_code'])
        require_course_instructor(
            self.request.user, course,
            "Only the course instructor can create announcements."
        )

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
        ).select_related('user').prefetch_related('user__preferences')
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
                    prefs = enrollment.user.preferences
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


def calculate_weighted_grade(quiz_pct, participation_pct, grading_config):
    """
    Weighted overall percentage from the quiz and participation components.
    Components that are None (nothing gradable yet) are skipped and the
    remaining weights renormalized. Without a config, the default 50/50
    weights apply. Returns None when no component is available.
    """
    quizzes_weight = float(grading_config.quizzes_weight) if grading_config else 50.0
    participation_weight = float(grading_config.participation_weight) if grading_config else 50.0

    weighted_total = 0.0
    weight_sum = 0.0
    if quiz_pct is not None and quizzes_weight > 0:
        weighted_total += quiz_pct * quizzes_weight
        weight_sum += quizzes_weight
    if participation_pct is not None and participation_weight > 0:
        weighted_total += participation_pct * participation_weight
        weight_sum += participation_weight

    if weight_sum == 0:
        return None
    return round(weighted_total / weight_sum, 1)


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def gradebook(request, course_code):
    """
    Get the full gradebook for a course (instructor only).
    Returns a matrix of students × quizzes (best attempt per quiz) with a
    lesson-completion (participation) column and a weighted overall grade.
    """
    from django.db.models import Count
    from quizzes.models import Quiz, QuizAttempt
    from .models import CourseGradingConfig

    course = get_object_or_404(Course, code=course_code)
    require_course_instructor(
        request.user, course,
        "Only the course instructor can view the gradebook."
    )

    # Get grading config (for weighted grades)
    try:
        grading_config = course.grading_config
    except CourseGradingConfig.DoesNotExist:
        grading_config = None

    # Get all quizzes for the course, ordered by unit and then order
    quizzes = Quiz.objects.filter(
        unit__course=course
    ).select_related('unit').order_by('unit__order', 'order')

    # Get all actively enrolled students
    enrollments = Enrollment.objects.filter(
        course=course,
        is_active=True
    ).select_related('user').order_by('user__last_name', 'user__first_name')

    # Get all completed quiz attempts and build best score lookup
    quiz_attempts = QuizAttempt.objects.filter(
        quiz__unit__course=course,
        status=QuizAttempt.STATUS_COMPLETED,
    ).select_related('quiz')

    # Build quiz best lookup: {(student_id, quiz_id): best_attempt}
    quiz_best_lookup = {}
    for attempt in quiz_attempts:
        key = (attempt.student_id, attempt.quiz_id)
        if key not in quiz_best_lookup or attempt.score > quiz_best_lookup[key].score:
            quiz_best_lookup[key] = attempt

    gradebook_items = [
        {
            'id': quiz.id,
            'title': quiz.title,
            'unit_title': quiz.unit.title,
            'max_points': quiz.points,
            'type': 'quiz',
        }
        for quiz in quizzes
    ]

    total_possible = sum(q.points for q in quizzes)

    # Lesson completion (participation), bulk-fetched per student
    total_lessons = Lesson.objects.filter(unit__course=course).count()
    completed_lessons_by_student = dict(
        LessonProgress.objects.filter(
            lesson__unit__course=course,
            completed=True
        ).values('user_id').annotate(count=Count('id')).values_list('user_id', 'count')
    )

    # Build students data with grades
    students_data = []
    for enrollment in enrollments:
        student = enrollment.user
        grades = []
        quiz_earned = 0
        quiz_possible = 0

        # Process quiz grades (a cell is either a score or empty)
        for quiz in quizzes:
            best_attempt = quiz_best_lookup.get((student.id, quiz.id))
            if best_attempt:
                points_earned = float(best_attempt.points_earned)
                grades.append({
                    'item_id': quiz.id,
                    'item_type': 'quiz',
                    'points_earned': points_earned,
                    'status': 'graded',
                    'passed': best_attempt.passed,
                    'score_percentage': float(best_attempt.score),
                })
                quiz_earned += points_earned
                quiz_possible += quiz.points
            else:
                grades.append({
                    'item_id': quiz.id,
                    'item_type': 'quiz',
                    'points_earned': None,
                    'status': 'not_started',
                })

        quiz_pct = round((quiz_earned / quiz_possible * 100), 1) if quiz_possible > 0 else None

        # Participation = lesson completion percentage
        if total_lessons > 0:
            completed_lessons = completed_lessons_by_student.get(student.id, 0)
            participation_pct = round((completed_lessons / total_lessons) * 100, 1)
        else:
            participation_pct = None

        percentage = calculate_weighted_grade(quiz_pct, participation_pct, grading_config)

        students_data.append({
            'id': student.id,
            'name': f"{student.first_name} {student.last_name}",
            'email': student.email,
            'grades': grades,
            'total_earned': round(quiz_earned, 2),
            'total_possible': quiz_possible,  # Only count attempted quizzes
            'percentage': percentage,
            'letter_grade': calculate_letter_grade(percentage) if percentage is not None else None,
            'quizzes_percentage': quiz_pct,
            'participation_percentage': participation_pct,
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
        'grading_config': {
            'quizzes_weight': float(grading_config.quizzes_weight),
            'participation_weight': float(grading_config.participation_weight),
        } if grading_config else None,
    })


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def gradebook_export(request, course_code):
    """
    Export gradebook as CSV (instructor only).
    Columns match the gradebook matrix: one per quiz, lesson completion,
    weighted overall percentage and letter grade.
    """
    from django.db.models import Count
    from quizzes.models import Quiz, QuizAttempt
    from .models import CourseGradingConfig

    course = get_object_or_404(Course, code=course_code)

    require_course_instructor(
        request.user, course,
        "Only the course instructor can export the gradebook."
    )

    try:
        grading_config = course.grading_config
    except CourseGradingConfig.DoesNotExist:
        grading_config = None

    # Get all quizzes for the course
    quizzes = Quiz.objects.filter(
        unit__course=course
    ).select_related('unit').order_by('unit__order', 'order')

    # Get all actively enrolled students
    enrollments = Enrollment.objects.filter(
        course=course,
        is_active=True
    ).select_related('user').order_by('user__last_name', 'user__first_name')

    # Get all completed quiz attempts and build best score lookup
    quiz_attempts = QuizAttempt.objects.filter(
        quiz__unit__course=course,
        status=QuizAttempt.STATUS_COMPLETED,
    ).select_related('quiz')

    quiz_best_lookup = {}
    for attempt in quiz_attempts:
        key = (attempt.student_id, attempt.quiz_id)
        if key not in quiz_best_lookup or attempt.score > quiz_best_lookup[key].score:
            quiz_best_lookup[key] = attempt

    # Lesson completion (participation)
    total_lessons = Lesson.objects.filter(unit__course=course).count()
    completed_lessons_by_student = dict(
        LessonProgress.objects.filter(
            lesson__unit__course=course,
            completed=True
        ).values('user_id').annotate(count=Count('id')).values_list('user_id', 'count')
    )

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{course.code}_gradebook.csv"'

    writer = csv.writer(response)

    # Header row
    header = ['Student Name', 'Email']
    for quiz in quizzes:
        header.append(f"{quiz.title} ({quiz.points})")
    header.extend(['Quiz Total', 'Quiz %', 'Lesson Completion %', 'Weighted %', 'Letter Grade'])
    writer.writerow(header)

    # Data rows
    for enrollment in enrollments:
        student = enrollment.user
        row = [f"{student.first_name} {student.last_name}", student.email]

        quiz_earned = 0
        quiz_possible = 0

        for quiz in quizzes:
            best_attempt = quiz_best_lookup.get((student.id, quiz.id))
            if best_attempt:
                points = float(best_attempt.points_earned)
                row.append(points)
                quiz_earned += points
                quiz_possible += quiz.points
            else:
                row.append('-')

        quiz_pct = round((quiz_earned / quiz_possible) * 100, 1) if quiz_possible > 0 else None

        if total_lessons > 0:
            completed_lessons = completed_lessons_by_student.get(student.id, 0)
            participation_pct = round((completed_lessons / total_lessons) * 100, 1)
        else:
            participation_pct = None

        percentage = calculate_weighted_grade(quiz_pct, participation_pct, grading_config)
        letter = calculate_letter_grade(percentage) if percentage is not None else '-'

        row.extend([
            quiz_earned,
            quiz_pct if quiz_pct is not None else '-',
            participation_pct if participation_pct is not None else '-',
            percentage if percentage is not None else '-',
            letter,
        ])
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

    require_course_instructor(
        request.user, course,
        "Only the course instructor can view the student roster."
    )

    enrollments = Enrollment.objects.filter(
        course=course,
        is_active=True
    ).select_related('user').order_by('user__last_name', 'user__first_name')

    serializer = StudentRosterSerializer(enrollments, many=True)
    return Response(serializer.data)


# ==================== Instructor Analytics (Phase 31) ====================

def _analytics_student_rows(course):
    """
    Bulk-computed per-student metrics shared by the analytics overview and
    students endpoints: progress % (roster calc), quiz average and weighted
    grade (gradebook best-attempt calc). One query per data source.
    Returns (rows, enrollments) with rows keyed to the same order.
    """
    from quizzes.models import QuizAttempt
    from .models import CourseGradingConfig

    try:
        grading_config = course.grading_config
    except CourseGradingConfig.DoesNotExist:
        grading_config = None

    enrollments = list(Enrollment.objects.filter(
        course=course,
        is_active=True
    ).select_related('user').order_by('user__last_name', 'user__first_name'))

    total_lessons = Lesson.objects.filter(unit__course=course).count()
    completed_lessons_by_student = dict(
        LessonProgress.objects.filter(
            lesson__unit__course=course,
            completed=True
        ).values('user_id').annotate(count=Count('id')).values_list('user_id', 'count')
    )

    # Best completed attempt per (student, quiz), grouped by student
    best_by_student = {}
    for attempt in QuizAttempt.objects.filter(
        quiz__unit__course=course,
        status=QuizAttempt.STATUS_COMPLETED,
    ).select_related('quiz'):
        per_quiz = best_by_student.setdefault(attempt.student_id, {})
        best = per_quiz.get(attempt.quiz_id)
        if best is None or attempt.score > best.score:
            per_quiz[attempt.quiz_id] = attempt

    rows = []
    for enrollment in enrollments:
        student = enrollment.user

        if total_lessons > 0:
            completed = completed_lessons_by_student.get(student.id, 0)
            progress_pct = round((completed / total_lessons) * 100, 1)
            participation_pct = progress_pct
        else:
            progress_pct = 0
            participation_pct = None

        quiz_earned = 0.0
        quiz_possible = 0
        for attempt in best_by_student.get(student.id, {}).values():
            quiz_earned += attempt.points_earned
            quiz_possible += attempt.quiz.points
        quiz_pct = round((quiz_earned / quiz_possible * 100), 1) if quiz_possible > 0 else None

        rows.append({
            'student': {
                'id': student.id,
                'name': f"{student.first_name} {student.last_name}",
                'email': student.email,
            },
            'progress_percentage': progress_pct,
            'quiz_average': quiz_pct,
            'weighted_grade': calculate_weighted_grade(quiz_pct, participation_pct, grading_config),
        })

    return rows, enrollments


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def analytics_overview(request, course_code):
    """
    Class-level key metrics for the analytics dashboard (instructor only).
    Averages are null when there is nothing to average.
    """
    course = get_object_or_404(Course, code=course_code)
    require_course_instructor(
        request.user, course,
        "Only the course instructor can view course analytics."
    )

    rows, enrollments = _analytics_student_rows(course)

    cutoff = timezone.now() - timedelta(days=7)
    active_last_7_days = sum(
        1 for e in enrollments
        if (e.last_activity_at or e.enrolled_at) >= cutoff
    )

    avg_progress = (
        round(sum(r['progress_percentage'] for r in rows) / len(rows), 1)
        if rows else None
    )
    grades = [r['weighted_grade'] for r in rows if r['weighted_grade'] is not None]
    avg_grade = round(sum(grades) / len(grades), 1) if grades else None

    return Response({
        'course': {
            'code': course.code,
            'title': course.title,
        },
        'student_count': len(rows),
        'avg_progress_percentage': avg_progress,
        'avg_grade_percentage': avg_grade,
        'active_last_7_days': active_last_7_days,
    })


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def analytics_quizzes(request, course_code):
    """
    Per-assessment struggle metrics (instructor only): graded unit quizzes
    (worst average first) and lesson comprehension checks (most stuck
    students first). Kept as two sections — score semantics differ.
    """
    from quizzes.models import Quiz, QuizAttempt

    course = get_object_or_404(Course, code=course_code)
    require_course_instructor(
        request.user, course,
        "Only the course instructor can view course analytics."
    )

    enrolled_ids = set(Enrollment.objects.filter(
        course=course, is_active=True
    ).values_list('user_id', flat=True))
    active_count = len(enrolled_ids)

    # ---- Unit quizzes (graded, best attempt per student) ----
    quiz_stats = {}  # quiz_id -> {student_id: {'best': float, 'passed': bool}}
    for attempt in QuizAttempt.objects.filter(
        quiz__unit__course=course, student_id__in=enrolled_ids,
        status=QuizAttempt.STATUS_COMPLETED,
    ):
        per_student = quiz_stats.setdefault(attempt.quiz_id, {})
        entry = per_student.setdefault(attempt.student_id, {'best': None, 'passed': False})
        score = float(attempt.score)
        if entry['best'] is None or score > entry['best']:
            entry['best'] = score
        entry['passed'] = entry['passed'] or attempt.passed

    unit_quizzes = []
    for quiz in Quiz.objects.filter(
        unit__course=course
    ).select_related('unit').order_by('unit__order', 'order'):
        per_student = quiz_stats.get(quiz.id, {})
        attempted = len(per_student)
        if attempted > 0:
            avg_score = round(sum(e['best'] for e in per_student.values()) / attempted, 1)
            passed = sum(1 for e in per_student.values() if e['passed'])
            pass_rate = round(passed / attempted * 100, 1)
        else:
            avg_score = None
            pass_rate = None
        completion_rate = round(attempted / active_count * 100, 1) if active_count > 0 else None
        unit_quizzes.append({
            'id': quiz.id,
            'title': quiz.title,
            'unit_title': quiz.unit.title,
            'passing_score': quiz.passing_score,
            'avg_score': avg_score,
            'pass_rate': pass_rate,
            'completion_rate': completion_rate,
        })
    unit_quizzes.sort(
        key=lambda q: q['avg_score'] if q['avg_score'] is not None else float('inf')
    )

    # ---- Lesson checks (perfect-score-to-pass, not graded) ----
    check_stats = {}  # lesson_id -> {user_id: {'passed': bool, 'first_pass': int|None}}
    for attempt in LessonQuizAttempt.objects.filter(
        lesson__unit__course=course, user_id__in=enrolled_ids,
        status=LessonQuizAttempt.STATUS_COMPLETED,
    ).order_by('attempt_number'):
        per_student = check_stats.setdefault(attempt.lesson_id, {})
        entry = per_student.setdefault(attempt.user_id, {'passed': False, 'first_pass': None})
        if attempt.passed and entry['first_pass'] is None:
            entry['passed'] = True
            entry['first_pass'] = attempt.attempt_number

    lesson_checks = []
    for lesson in Lesson.objects.filter(
        unit__course=course
    ).annotate(num_questions=Count('questions')).filter(
        num_questions__gt=0
    ).select_related('unit').order_by('unit__order', 'order'):
        per_student = check_stats.get(lesson.id, {})
        attempted = len(per_student)
        first_passes = [e['first_pass'] for e in per_student.values() if e['passed']]
        lesson_checks.append({
            'id': lesson.id,
            'title': lesson.title,
            'unit_title': lesson.unit.title,
            'attempted_count': attempted,
            'passed_count': len(first_passes),
            'stuck_count': attempted - len(first_passes),
            'avg_attempts_to_pass': (
                round(sum(first_passes) / len(first_passes), 1) if first_passes else None
            ),
        })
    lesson_checks.sort(key=lambda l: -l['stuck_count'])

    return Response({
        'unit_quizzes': unit_quizzes,
        'lesson_checks': lesson_checks,
    })


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def analytics_students(request, course_code):
    """
    Per-student analytics rows (instructor only): progress, grades, streak
    and an at-risk flag (progress < 50% OR inactive 7+ days, same rule as
    the roster's is_inactive).
    """
    from gamification.models import GameProfile

    course = get_object_or_404(Course, code=course_code)
    require_course_instructor(
        request.user, course,
        "Only the course instructor can view course analytics."
    )

    rows, enrollments = _analytics_student_rows(course)

    streaks = dict(GameProfile.objects.filter(
        user_id__in=[e.user_id for e in enrollments]
    ).values_list('user_id', 'current_streak'))

    now = timezone.now()
    for row, enrollment in zip(rows, enrollments):
        is_inactive = (now - (enrollment.last_activity_at or enrollment.enrolled_at)) > timedelta(days=7)
        row['last_activity_at'] = enrollment.last_activity_at
        row['current_streak'] = streaks.get(enrollment.user_id, 0)
        row['at_risk'] = row['progress_percentage'] < 50 or is_inactive

    return Response({'students': rows})


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def analytics_activity(request, course_code):
    """
    Daily activity counts for the last 30 days (instructor only), zero-filled
    so the frontend never has to: lessons completed, unit-quiz attempts and
    lesson-check attempts by enrolled students.
    """
    from django.db.models.functions import TruncDate
    from quizzes.models import QuizAttempt

    course = get_object_or_404(Course, code=course_code)
    require_course_instructor(
        request.user, course,
        "Only the course instructor can view course analytics."
    )

    today = timezone.localdate()
    start = today - timedelta(days=29)

    enrolled_ids = set(Enrollment.objects.filter(
        course=course, is_active=True
    ).values_list('user_id', flat=True))

    def counts_by_day(queryset, datetime_field):
        # order_by() clears model default ordering so it can't leak into GROUP BY
        return dict(
            queryset.annotate(day=TruncDate(datetime_field))
            .filter(day__gte=start, day__lte=today)
            .values('day').annotate(count=Count('id'))
            .order_by().values_list('day', 'count')
        )

    lessons_completed = counts_by_day(
        LessonProgress.objects.filter(
            lesson__unit__course=course,
            user_id__in=enrolled_ids,
            completed=True,
            completed_at__isnull=False,
        ),
        'completed_at',
    )
    quiz_attempts = counts_by_day(
        QuizAttempt.objects.filter(
            quiz__unit__course=course,
            student_id__in=enrolled_ids,
            status=QuizAttempt.STATUS_COMPLETED,
        ),
        'completed_at',
    )
    lesson_check_attempts = counts_by_day(
        LessonQuizAttempt.objects.filter(
            lesson__unit__course=course,
            user_id__in=enrolled_ids,
            status=LessonQuizAttempt.STATUS_COMPLETED,
            completed_at__isnull=False,
        ),
        'completed_at',
    )

    days = []
    for offset in range(30):
        day = start + timedelta(days=offset)
        days.append({
            'date': day.isoformat(),
            'lessons_completed': lessons_completed.get(day, 0),
            'quiz_attempts': quiz_attempts.get(day, 0),
            'lesson_check_attempts': lesson_check_attempts.get(day, 0),
        })

    return Response({'days': days})


@api_view(['DELETE'])
@perm_classes([IsAuthenticated])
def remove_student(request, course_code, enrollment_id):
    """
    Remove a student from a course (soft delete - preserves grades).
    """
    course = get_object_or_404(Course, code=course_code)

    require_course_instructor(
        request.user, course,
        "Only the course instructor can remove students."
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

    require_course_instructor(
        request.user, course,
        "Only the course instructor can send invitations."
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
        raise PermissionDenied("You must be enrolled in this course.")


@api_view(['GET', 'PUT'])
@perm_classes([IsAuthenticated])
def course_grading_config(request, course_code):
    """Get or update course grading configuration."""
    from .models import CourseGradingConfig
    from .serializers import GradingConfigSerializer

    course = get_object_or_404(Course, code=course_code)

    # GET is allowed for enrolled students and instructor
    # PUT is only for instructor
    if request.method == 'PUT':
        require_course_instructor(
            request.user, course,
            "Only the course instructor can update grading settings."
        )
    else:
        require_course_access(
            request.user, course,
            "You must be enrolled in this course."
        )

    # Get or create config with defaults
    config, created = CourseGradingConfig.objects.get_or_create(
        course=course,
        defaults={
            'quizzes_weight': 50,
            'participation_weight': 50,
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
    Returns quiz and participation grades, weighted average, and letter grade.
    """
    from .models import CourseGradingConfig
    from quizzes.models import Quiz, QuizAttempt

    course = get_object_or_404(Course, code=course_code)

    require_course_access(
        request.user, course,
        "You must be enrolled in this course."
    )

    # Get grading config (or use defaults)
    try:
        config = course.grading_config
    except CourseGradingConfig.DoesNotExist:
        config = None

    # Calculate quiz grades and build per-quiz grade items
    all_quizzes = Quiz.objects.filter(
        unit__course=course
    ).select_related('unit').order_by('unit__order', 'order')

    quiz_earned = 0
    quiz_possible = 0
    grade_items = []

    for quiz in all_quizzes:
        best_attempt = QuizAttempt.objects.filter(
            quiz=quiz, student=request.user,
            status=QuizAttempt.STATUS_COMPLETED,
        ).order_by('-score').first()

        if best_attempt:
            points_earned = float(best_attempt.points_earned)
            quiz_earned += points_earned
            quiz_possible += quiz.points
            grade_items.append({
                'id': quiz.id,
                'type': 'quiz',
                'title': quiz.title,
                'unit_title': quiz.unit.title,
                'max_points': quiz.points,
                'points_earned': points_earned,
                'status': 'graded',
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
                'passed': None,
            })

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
    weighted_percentage = calculate_weighted_grade(
        quiz_percentage, participation_percentage, config
    )

    # Calculate letter grade
    letter_grade = calculate_letter_grade(weighted_percentage) if weighted_percentage is not None else None

    return Response({
        'course': {
            'code': course.code,
            'title': course.title,
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

    is_instructor = is_course_instructor(request.user, course)
    require_course_access(request.user, course, "You must be enrolled in this course.")

    if request.method == 'GET':
        questions = lesson.questions.prefetch_related('choices').all()

        if is_instructor:
            serializer = LessonQuestionSerializer(questions, many=True)
        else:
            serializer = LessonQuestionStudentSerializer(questions, many=True)

        return Response(serializer.data)

    elif request.method == 'POST':
        require_course_instructor(
            request.user, course,
            "Only the instructor can create questions."
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

    is_instructor = is_course_instructor(request.user, course)
    require_course_access(request.user, course, "You must be enrolled in this course.")

    if request.method == 'GET':
        if is_instructor:
            serializer = LessonQuestionSerializer(question)
        else:
            serializer = LessonQuestionStudentSerializer(question)
        return Response(serializer.data)

    elif request.method == 'PUT':
        require_course_instructor(
            request.user, course,
            "Only the instructor can update questions."
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
        require_course_instructor(
            request.user, course,
            "Only the instructor can delete questions."
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

    require_course_access(request.user, course, "You must be enrolled in this course.")

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

    require_course_access(request.user, course, "You must be enrolled in this course.")

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

    # Attempt info (completed sessions only). Phase 32 retired the attempt
    # cap — mastery-retry guarantees a pass, so the check is always
    # attemptable. Keys are kept for the old-client response contract.
    attempts = LessonQuizAttempt.objects.filter(
        user=request.user,
        lesson=lesson,
        status=LessonQuizAttempt.STATUS_COMPLETED,
    )
    attempt_count = attempts.count()
    has_passed = attempts.filter(passed=True).exists()

    return Response({
        'total_questions': total_questions,
        'answered_questions': answered_count,
        'correct_answers': correct_count,
        'all_correct': all_correct,
        'can_complete_lesson': has_passed or all_correct,
        'attempt_count': attempt_count,
        'max_attempts': None,
        'attempts_remaining': None,
        'can_attempt': True,
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

    require_course_access(request.user, course, "You must be enrolled in this course.")

    # Check if quiz has questions
    questions = lesson.questions.prefetch_related('choices').all()
    total_questions = questions.count()

    if total_questions == 0:
        return Response(
            {'error': 'This lesson has no quiz questions.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check attempt limits (completed sessions only — an abandoned in-progress
    # mastery session must not inflate the cap or the attempt number)
    max_attempts = lesson.max_quiz_attempts
    current_attempts = LessonQuizAttempt.objects.filter(
        user=request.user,
        lesson=lesson,
        status=LessonQuizAttempt.STATUS_COMPLETED,
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

    # Create attempt record (number from Max over ALL rows so an in-progress
    # session row can't collide with the unique attempt_number)
    passed = correct_count == total_questions
    last_number = LessonQuizAttempt.objects.filter(
        user=request.user, lesson=lesson
    ).aggregate(Max('attempt_number'))['attempt_number__max'] or 0
    attempt = LessonQuizAttempt.objects.create(
        user=request.user,
        lesson=lesson,
        attempt_number=last_number + 1,
        score=correct_count,
        total_questions=total_questions,
        passed=passed,
        completed_at=timezone.now()
    )

    # Calculate remaining attempts
    attempts_remaining = None
    if max_attempts > 0:
        attempts_remaining = max(0, max_attempts - (current_attempts + 1))

    response_data = {
        'attempt_number': attempt.attempt_number,
        'score': correct_count,
        'total_questions': total_questions,
        'percentage': attempt.percentage,
        'passed': passed,
        'results': results,
        'attempts_remaining': attempts_remaining,
        'can_complete_lesson': passed,
    }
    if passed:
        from gamification.services import award_lesson_quiz_pass
        response_data['gamification'] = award_lesson_quiz_pass(request.user, lesson).as_dict()
    return Response(response_data)


# ============================================
# Lesson-Check Mastery Sessions (Phase 32)
# ============================================
# Duolingo-style flow for lesson comprehension checks: one question at a
# time, instant feedback, missed questions re-queued until mastered. The
# attempt cap (Lesson.max_quiz_attempts) is retired — mastery guarantees a
# pass — but the model field stays for painless rollback.

def _lesson_session_state(lesson, attempt):
    """Resume/progress payload for an in-progress lesson-check session."""
    questions = list(lesson.questions.all())
    answers = {a.question_id: a for a in attempt.session_answers.all()}

    question_status = []
    for question in questions:
        answer = answers.get(question.id)
        question_status.append({
            'question_id': question.id,
            'answered': answer is not None,
            'first_try_correct': answer.is_correct if answer else None,
            'mastered': bool(answer and answer.mastered_at),
        })

    unanswered = [q.id for q in questions if q.id not in answers]
    requeued = [
        q.id for q in questions
        if q.id in answers and not answers[q.id].mastered_at
    ]

    mastered_count = sum(1 for s in question_status if s['mastered'])
    return {
        'attempt_id': attempt.id,
        'lesson_id': lesson.id,
        'status': attempt.status,
        'questions': question_status,
        'remaining_question_ids': unanswered + requeued,
        'total_questions': len(questions),
        'mastered_count': mastered_count,
        'answered_count': len(answers),
    }


@api_view(['POST'])
@perm_classes([IsAuthenticated])
def start_lesson_quiz_session(request, lesson_id):
    """
    Start (or resume) a mastery session for a lesson's comprehension check.
    Students only. max_quiz_attempts is intentionally ignored (cap retired).
    """
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    require_enrollment(request.user, lesson.unit.course)

    if not lesson.questions.exists():
        return Response(
            {'detail': 'This lesson has no quiz questions.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    existing = LessonQuizAttempt.objects.filter(
        user=request.user, lesson=lesson,
        status=LessonQuizAttempt.STATUS_IN_PROGRESS,
    ).first()
    if existing:
        return Response(_lesson_session_state(lesson, existing))

    last_number = LessonQuizAttempt.objects.filter(
        user=request.user, lesson=lesson
    ).aggregate(Max('attempt_number'))['attempt_number__max'] or 0
    attempt = LessonQuizAttempt.objects.create(
        user=request.user,
        lesson=lesson,
        attempt_number=last_number + 1,
        score=0,
        total_questions=lesson.questions.count(),
        passed=False,
        status=LessonQuizAttempt.STATUS_IN_PROGRESS,
    )
    return Response(_lesson_session_state(lesson, attempt), status=status.HTTP_201_CREATED)


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def get_lesson_quiz_session(request, lesson_id):
    """Resume state for the current in-progress session; 404 if none."""
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    require_enrollment(request.user, lesson.unit.course)

    attempt = LessonQuizAttempt.objects.filter(
        user=request.user, lesson=lesson,
        status=LessonQuizAttempt.STATUS_IN_PROGRESS,
    ).first()
    if attempt is None:
        return Response(
            {'detail': 'No in-progress session for this lesson check.'},
            status=status.HTTP_404_NOT_FOUND
        )
    return Response(_lesson_session_state(lesson, attempt))


@api_view(['POST'])
@perm_classes([IsAuthenticated])
def answer_lesson_quiz_session(request, lesson_id):
    """
    Grade one answer in a lesson-check mastery session. First answers are the
    permanent first-try record; every graded answer also updates the legacy
    LessonQuestionAnswer row (latest answer) so questions-status and lesson
    completion gating stay consistent. Finalizes when all mastered:
    score = first-try correct count, passed=True, XP awarded once.
    """
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    require_enrollment(request.user, lesson.unit.course)

    attempt = LessonQuizAttempt.objects.filter(
        user=request.user, lesson=lesson,
        status=LessonQuizAttempt.STATUS_IN_PROGRESS,
    ).first()
    if attempt is None:
        return Response(
            {'detail': 'No in-progress session for this lesson check. Start one first.'},
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
        question = lesson.questions.get(id=question_id)
    except LessonQuestion.DoesNotExist:
        return Response(
            {'detail': 'Question does not belong to this lesson.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        choice = question.choices.get(id=choice_id)
    except LessonQuestionChoice.DoesNotExist:
        return Response(
            {'detail': 'Choice does not belong to this question.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    is_correct = choice.is_correct
    # First try creates the permanent score record; get_or_create is
    # race-safe under the (attempt, question) uniqueness — a concurrent
    # duplicate answer can't 500, the loser just sees the winner's row.
    answer, created = LessonAttemptAnswer.objects.get_or_create(
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

    # Keep the legacy latest-answer record in sync on every graded answer so
    # questions-status (all_correct / can_complete_lesson) stays consistent.
    # NOTE: update_or_create would pass update_fields=['selected_choice'] on
    # the update path (Django 4.2+), silently dropping the is_correct value
    # recomputed in LessonQuestionAnswer.save() — use a full save instead.
    legacy_answer, legacy_created = LessonQuestionAnswer.objects.get_or_create(
        user=request.user,
        question=question,
        defaults={'selected_choice': choice}
    )
    if not legacy_created:
        legacy_answer.selected_choice = choice
        legacy_answer.save()

    total_questions = lesson.questions.count()
    mastered_count = attempt.session_answers.filter(mastered_at__isnull=False).count()
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
        # Auto-finalize: mastery means the session passed; score records
        # first-try correctness for analytics.
        first_try_correct = attempt.session_answers.filter(is_correct=True).count()
        attempt.score = first_try_correct
        attempt.total_questions = total_questions
        attempt.passed = True
        attempt.status = LessonQuizAttempt.STATUS_COMPLETED
        attempt.completed_at = timezone.now()
        attempt.save()

        from gamification.services import award_lesson_quiz_pass
        result = {
            'attempt_number': attempt.attempt_number,
            'score': first_try_correct,
            'total_questions': total_questions,
            'percentage': attempt.percentage,
            'passed': True,
            'can_complete_lesson': True,
            'gamification': award_lesson_quiz_pass(request.user, lesson).as_dict(),
        }
        data['result'] = result

    return Response(data)


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

    require_course_access(request.user, course, "You must be enrolled in this course.")

    if request.method == 'GET':
        attachments = lesson.attachments.all()
        serializer = LessonAttachmentSerializer(
            attachments, many=True, context={'request': request}
        )
        return Response(serializer.data)

    elif request.method == 'POST':
        require_course_instructor(
            request.user, course,
            "Only instructors can upload attachments."
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

        # Allowed file extensions (whitelist). svg/html are deliberately excluded:
        # they can carry inline scripts and are served from a host that could be
        # same-origin in some configs, so an uploaded .svg/.html is a stored-XSS
        # vector. Ship code samples as .txt or inside a .zip instead.
        ALLOWED_EXTENSIONS = {
            'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx',
            'txt', 'md', 'csv',
            'png', 'jpg', 'jpeg', 'gif', 'webp',
            'zip', 'rar', '7z',
            'mp3', 'wav', 'mp4', 'webm', 'mov',
            'py', 'js', 'css', 'json'  # code files
        }

        # Validate file sizes and file types
        max_size = settings.ATTACHMENT_MAX_UPLOAD_BYTES
        limit_mb = max_size // (1024 * 1024)
        for f in files:
            if f.size > max_size:
                return Response(
                    {'error': f'File "{f.name}" exceeds {limit_mb}MB limit'},
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

    require_course_instructor(
        request.user, course,
        "Only instructors can delete attachments."
    )

    attachment = get_object_or_404(LessonAttachment, pk=attachment_id, lesson=lesson)

    # Delete the file from storage
    if attachment.file:
        attachment.file.delete(save=False)

    attachment.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ==============================================
# Lesson Sections (Phase 17: Lesson Pagination)
# ==============================================

@api_view(['GET', 'POST'])
@perm_classes([IsAuthenticated])
def lesson_sections(request, lesson_id):
    """
    GET: List sections for a lesson (students and instructors)
    POST: Create a new section (instructor only)
    """
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    course = lesson.unit.course

    require_course_access(request.user, course, "You must be enrolled in this course.")

    if request.method == 'GET':
        sections = lesson.sections.all().order_by('order')
        serializer = LessonSectionSerializer(sections, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        require_course_instructor(
            request.user, course,
            "Only instructors can create sections."
        )

        serializer = LessonSectionCreateSerializer(data=request.data)
        if serializer.is_valid():
            # Auto-assign order if not provided
            order = serializer.validated_data.get('order')
            if order is None:
                max_order = lesson.sections.aggregate(Max('order'))['order__max']
                order = (max_order or -1) + 1

            section = serializer.save(lesson=lesson, order=order)
            return Response(
                LessonSectionSerializer(section).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@perm_classes([IsAuthenticated])
def lesson_section_detail(request, lesson_id, section_id):
    """
    GET: Get a single section
    PUT: Update a section (instructor only)
    DELETE: Delete a section (instructor only)
    """
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    course = lesson.unit.course
    section = get_object_or_404(LessonSection, pk=section_id, lesson=lesson)

    require_course_access(request.user, course, "You must be enrolled in this course.")

    if request.method == 'GET':
        serializer = LessonSectionSerializer(section)
        return Response(serializer.data)

    elif request.method == 'PUT':
        require_course_instructor(
            request.user, course,
            "Only instructors can update sections."
        )

        serializer = LessonSectionCreateSerializer(section, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(LessonSectionSerializer(section).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        require_course_instructor(
            request.user, course,
            "Only instructors can delete sections."
        )

        deleted_order = section.order
        section.delete()

        # Reorder remaining sections to fill the gap
        lesson.sections.filter(order__gt=deleted_order).update(order=F('order') - 1)

        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@perm_classes([IsAuthenticated])
def lesson_sections_reorder(request, lesson_id):
    """
    Reorder sections for a lesson.
    Expects: { "section_ids": [3, 1, 2] }
    """
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    course = lesson.unit.course

    require_course_instructor(
        request.user, course,
        "Only instructors can reorder sections."
    )

    section_ids = request.data.get('section_ids', [])
    if not section_ids:
        return Response(
            {'error': 'section_ids is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Verify all section IDs belong to this lesson
    existing_ids = set(lesson.sections.values_list('id', flat=True))
    provided_ids = set(section_ids)

    if existing_ids != provided_ids:
        return Response(
            {'error': 'Invalid section IDs provided'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # To avoid unique_together constraint violations, first set all to temporary high values
    # then set them to their final order
    offset = 10000
    for i, section_id in enumerate(section_ids):
        LessonSection.objects.filter(pk=section_id).update(order=offset + i)

    # Now set the final order values
    for new_order, section_id in enumerate(section_ids):
        LessonSection.objects.filter(pk=section_id).update(order=new_order)

    # Return updated sections
    sections = lesson.sections.all().order_by('order')
    serializer = LessonSectionSerializer(sections, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@perm_classes([IsAuthenticated])
def lesson_sections_bulk_create(request, lesson_id):
    """
    Atomically create many sections at once (paste-to-split authoring).
    Expects: { "sections": [{ "title", "content", "video_type", "video_id" }, ...] }
    New sections are appended after existing ones with server-assigned order.
    All-or-nothing: a single invalid child rolls back the whole batch (400).
    """
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    course = lesson.unit.course

    require_course_instructor(
        request.user, course,
        "Only instructors can create sections."
    )

    serializer = LessonSectionBulkCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    sections_data = serializer.validated_data['sections']

    with transaction.atomic():
        max_order = lesson.sections.aggregate(Max('order'))['order__max']
        start_order = (max_order or -1) + 1

        created = []
        for i, data in enumerate(sections_data):
            data.pop('order', None)  # server assigns order; ignore any incoming value
            created.append(
                LessonSection.objects.create(
                    lesson=lesson, order=start_order + i, **data
                )
            )

    return Response(
        LessonSectionSerializer(created, many=True).data,
        status=status.HTTP_201_CREATED
    )


# ============================================
# Instructor Progress Reset
# ============================================

@api_view(['POST'])
@perm_classes([IsAuthenticated])
def reset_lesson_progress(request, lesson_id):
    """
    Reset lesson progress for the current user (instructor only).
    This resets:
    - LessonProgress (completed, video_position, current_section)
    - LessonQuizAttempt records
    - LessonQuestionAnswer records

    Used by instructors to repeatedly test the student experience.
    """
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    course = lesson.unit.course

    # Only allow instructors of this course to reset their progress
    require_course_instructor(
        request.user, course,
        "Only the course instructor can reset their progress."
    )

    # Reset LessonProgress
    LessonProgress.objects.filter(
        user=request.user,
        lesson=lesson
    ).update(
        completed=False,
        video_position=0,
        current_section=0
    )

    # Delete quiz attempts
    LessonQuizAttempt.objects.filter(
        user=request.user,
        lesson=lesson
    ).delete()

    # Delete question answers
    LessonQuestionAnswer.objects.filter(
        user=request.user,
        question__lesson=lesson
    ).delete()

    return Response({'message': 'Progress reset successfully'})


# ============================================
# Instructor Calendar & Reminders
# ============================================

from .models import InstructorReminder
from .serializers import InstructorReminderSerializer, InstructorReminderCreateSerializer


class InstructorReminderViewSet(viewsets.ModelViewSet):
    """ViewSet for instructor reminders."""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only instructors can access reminders
        if not self.request.user.is_instructor:
            return InstructorReminder.objects.none()
        return InstructorReminder.objects.filter(instructor=self.request.user)

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return InstructorReminderCreateSerializer
        return InstructorReminderSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        # Only instructors can create reminders
        if not self.request.user.is_instructor:
            raise PermissionDenied("Only instructors can create reminders.")
        serializer.save(instructor=self.request.user)


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def instructor_calendar(request):
    """
    Get calendar events for the instructor's dashboard.
    Returns custom reminders for a date range.

    Query params:
    - start_date: YYYY-MM-DD (defaults to today)
    - end_date: YYYY-MM-DD (defaults to 7 days from start)
    """
    from datetime import datetime, timedelta
    from django.utils import timezone

    if not request.user.is_instructor:
        raise PermissionDenied("Only instructors can access this endpoint.")

    # Parse date range
    today = timezone.now().date()
    start_date_str = request.query_params.get('start_date')
    end_date_str = request.query_params.get('end_date')

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid start_date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
    else:
        start_date = today

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid end_date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
    else:
        end_date = start_date + timedelta(days=6)

    events = []

    # Get custom reminders
    reminders = InstructorReminder.objects.filter(
        instructor=request.user,
        date__gte=start_date,
        date__lte=end_date
    ).select_related('course')

    for reminder in reminders:
        events.append({
            'id': f'reminder-{reminder.id}',
            'type': 'reminder',
            'title': reminder.title,
            'description': reminder.description,
            'course_code': reminder.course.code if reminder.course else None,
            'date': reminder.date.isoformat(),
            'time': reminder.time.strftime('%H:%M') if reminder.time else None,
            'end_time': reminder.end_time.strftime('%H:%M') if reminder.end_time else None,
            'color': reminder.color,
            'reminder_id': reminder.id,
        })

    # Sort by date and time
    events.sort(key=lambda x: (x['date'], x['time'] or '23:59'))

    return Response({
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'events': events,
    })


# ==================== Course Map (Phase 35) ====================

@api_view(['GET'])
@perm_classes([IsAuthenticated])
def course_map(request, course_code):
    """
    Duolingo-style course map: every unit's lessons then its quizzes as one
    flattened node sequence, with per-node completed/current/unlocked/locked
    state for the requesting user. Gating is soft — this endpoint only
    describes state; nothing new is enforced anywhere.

    States: a node is unlocked if it is first in the sequence or the previous
    node is completed; a quiz that is some lesson's required_quiz unlocks
    together with that lesson (else the pair would deadlock); `current` is the
    first unlocked-but-incomplete node. Everything else incomplete is locked.
    """
    from quizzes.models import QuizAttempt

    course = get_object_or_404(
        Course.objects.prefetch_related('units__lessons', 'units__quizzes'),
        code=course_code
    )
    require_course_access(request.user, course)

    # One query for the user's completed lessons in this course.
    completed_lesson_ids = set(
        LessonProgress.objects.filter(
            user=request.user, lesson__unit__course=course, completed=True
        ).values_list('lesson_id', flat=True)
    )

    # One query for the user's graded quiz attempts: best % and pass state.
    quiz_stats = QuizAttempt.objects.filter(
        student=request.user,
        quiz__unit__course=course,
        status=QuizAttempt.STATUS_COMPLETED,
    ).values('quiz_id').annotate(
        best_score=Max('score'),
        passed_count=Count('id', filter=models.Q(passed=True)),
    )
    best_scores = {row['quiz_id']: float(row['best_score']) for row in quiz_stats}
    passed_quiz_ids = {row['quiz_id'] for row in quiz_stats if row['passed_count']}

    # Flatten: for each unit (by order), lessons (by order) then quizzes
    # (by order) as boss nodes. Model Meta orderings apply to the prefetches.
    nodes = []
    unit_groups = []
    for unit in course.units.all():
        unit_start = len(nodes)
        for lesson in unit.lessons.all():
            nodes.append({
                'node_type': 'lesson',
                'obj': lesson,
                'completed': lesson.id in completed_lesson_ids,
            })
        for quiz in unit.quizzes.all():
            nodes.append({
                'node_type': 'quiz',
                'obj': quiz,
                'completed': quiz.id in passed_quiz_ids,
            })
        unit_groups.append((unit, nodes[unit_start:]))

    # Base unlock rule: first node, or previous node completed.
    for i, node in enumerate(nodes):
        node['unlocked'] = i == 0 or nodes[i - 1]['completed']

    # Deadlock exception: a quiz required by a lesson unlocks with that lesson
    # (the lesson can't complete until the quiz passes, so the quiz must never
    # wait on the lesson's completion).
    required_unlocked_quiz_ids = {
        node['obj'].required_quiz_id
        for node in nodes
        if node['node_type'] == 'lesson'
        and node['unlocked']
        and node['obj'].required_quiz_id
    }
    for node in nodes:
        if node['node_type'] == 'quiz' and node['obj'].id in required_unlocked_quiz_ids:
            node['unlocked'] = True

    # Current = first unlocked-but-incomplete node in the sequence.
    current_node_id = None
    for node in nodes:
        if node['unlocked'] and not node['completed']:
            node['current'] = True
            current_node_id = f"{node['node_type']}-{node['obj'].id}"
            break

    def node_payload(node):
        obj = node['obj']
        if node['completed']:
            state = 'completed'
        elif node.get('current'):
            state = 'current'
        elif node['unlocked']:
            state = 'unlocked'
        else:
            state = 'locked'
        payload = {
            'node_type': node['node_type'],
            'id': obj.id,
            'title': obj.title,
            'order': obj.order,
            'state': state,
        }
        if node['node_type'] == 'quiz':
            payload['passing_score'] = obj.passing_score
            payload['best_score'] = best_scores.get(obj.id)
        return payload

    data = {
        'course_code': course.code,
        'course_title': course.title,
        'total_nodes': len(nodes),
        'completed_nodes': sum(1 for node in nodes if node['completed']),
        'current_node_id': current_node_id,
        'units': [
            {
                'id': unit.id,
                'title': unit.title,
                'order': unit.order,
                'nodes': [node_payload(node) for node in group],
            }
            for unit, group in unit_groups
        ],
    }
    return Response(CourseMapSerializer(data).data)
