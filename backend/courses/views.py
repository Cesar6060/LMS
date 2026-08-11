import csv
import re

from django.conf import settings
from rest_framework import viewsets, status, generics
from rest_framework.decorators import (
    action, api_view, permission_classes as perm_classes, throttle_classes,
)
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, models, transaction
from django.db.models import F, Max, Count, Q
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta

from PIL import Image as PILImage

from allauth.account.models import EmailAddress
from accounts.models import User
from accounts.serializers import UserSerializer
from core.demo import is_demo_email, require_not_demo, require_not_demo_course
from core.uploads import verify_upload
from core.email import send_course_invite_link_email, send_emails_async
from core.pagination import RosterPagination
from core.throttling import (
    ClientIPAnonRateThrottle, ClientIPScopedRateThrottle,
    ClientIPScopedWriteRateThrottle, ClientIPUserRateThrottle,
)
from .models import Course, Unit, Lesson, Enrollment, LessonProgress, Announcement, LessonQuestion, LessonQuestionChoice, LessonQuestionAnswer, LessonQuizAttempt, LessonAttemptAnswer, LessonAttachment, LessonSection, CourseInvite, generate_join_code, normalize_join_code
from .serializers import (
    CourseSerializer, CourseListSerializer, CourseCreateSerializer,
    InstructorCourseSerializer, UnitSerializer, UnitCreateSerializer,
    LessonSerializer, LessonListSerializer, LessonCreateSerializer,
    EnrollmentSerializer, EnrollmentCreateSerializer, LessonProgressSerializer,
    LessonProgressUpdateSerializer, AnnouncementSerializer,
    AnnouncementListSerializer, AnnouncementCreateSerializer,
    StudentRosterSerializer, LessonQuestionSerializer, LessonQuestionStudentSerializer,
    LessonQuestionCreateSerializer, LessonAttachmentSerializer,
    LessonSectionSerializer, LessonSectionCreateSerializer,
    LessonSectionBulkCreateSerializer, CourseMapSerializer, CourseInviteSerializer,
    prefetch_active_enrollments,
)
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied
from .permissions import (
    IsInstructor, IsInstructorOrReadOnly, IsCourseInstructor,
    IsEnrolledOrInstructor,
    is_course_instructor, is_enrolled, can_access_course,
    require_course_instructor, require_course_access, require_enrollment,
    require_pending_invite, require_unit_unlocked, locked_unit_ids_for,
    accessible_course_ids, INVITE_REQUIRED_DETAIL,
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
        # `enrollments` is prefetched through the active-only alias: both
        # student_count and is_enrolled used .filter() on the related manager,
        # which rebuilds the queryset and hits the database however it was
        # prefetched. See ActiveEnrollmentCountMixin.
        queryset = Course.objects.select_related('instructor').prefetch_related(
            'units__lessons', prefetch_active_enrollments()
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
        """Enroll in a course using an enrollment code AND a pending invite.

        Phase 68: the enrollment code is a SECOND FACTOR, not the
        authorization. `require_pending_invite` is what says this caller was
        asked to join this course; without it a code overheard in a hallway
        enrolled anyone with an account, and a removed student re-added
        themselves with the code their instructor had read to the class. Do
        not "simplify" the invite check away — it is the whole security
        contract of this action, and it must stay identical to the one in
        `EnrollmentCreateSerializer` (the other code-based join path).
        """
        # The demo account lives in DEMO101 only — with a leaked enrollment
        # code it must not be able to join a real course and see a real
        # roster. Mirrors the destroy() guard below (both directions closed).
        require_not_demo(request.user)
        course = get_object_or_404(Course, code=code, is_active=True)

        # Verify enrollment code matches. Coerced first: `.upper()` on a
        # non-string body (`{"enrollment_code": 123}`) used to raise
        # AttributeError and 500. Same treatment as normalize_join_code.
        raw_code = request.data.get('enrollment_code', '')
        provided_code = raw_code.upper() if isinstance(raw_code, str) else ''
        if provided_code != course.enrollment_code:
            return Response(
                {'detail': 'Invalid enrollment code'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if already enrolled (only active enrollments)
        existing = Enrollment.objects.filter(user=request.user, course=course).first()
        if existing and existing.is_active:
            return Response(
                {'detail': 'You are already enrolled in this course'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user is instructor
        if course.instructor == request.user:
            return Response(
                {'detail': 'Instructors cannot enroll in their own courses'},
                status=status.HTTP_400_BAD_REQUEST
            )

        require_pending_invite(request.user, course)

        # A soft-deleted enrollment is NOT revived here any more. Removal is
        # the instructor's decision and sticks until they re-invite, at which
        # point accept_invite's _activate_enrollment brings the row back with
        # its grades — that path, and only that path. The refusal reuses the
        # invite-required body verbatim so it never tells a student they were
        # removed, and so this branch is indistinguishable from "no invite".
        if existing:
            raise PermissionDenied(INVITE_REQUIRED_DETAIL)

        try:
            with transaction.atomic():
                enrollment = Enrollment.objects.create(
                    user=request.user, course=course)
                # The invite check above is a read; this write is the one that
                # actually claims the invitation, and it re-tests pending() in
                # its WHERE clause. If it matches nothing, an instructor's
                # revoke landed in the gap and won — roll the enrollment back.
                if not consume_invite_for(request.user, course):
                    raise PermissionDenied(INVITE_REQUIRED_DETAIL)
        except IntegrityError:
            # A concurrent request (an impatient double-click is enough) beat
            # us to the unique ('user','course') row between the check above
            # and this insert. That is the already-enrolled case, not a 500.
            #
            # Confirmed by re-reading, NOT assumed from the exception class: a
            # bare `except IntegrityError` would quietly relabel any future
            # constraint reachable from this block as a business-rule 400 and
            # hide it from Sentry. Anything that is not the duplicate we
            # expect gets re-raised.
            if not Enrollment.objects.filter(
                    user=request.user, course=course).exists():
                raise
            return Response(
                {'detail': 'You are already enrolled in this course'},
                status=status.HTTP_400_BAD_REQUEST
            )
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
        ).select_related('instructor').prefetch_related(
            'units__lessons', prefetch_active_enrollments()
        )


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

    def perform_update(self, serializer):
        # Locking a unit changes what an entire class can see — a shared
        # surface, so the demo account is refused it (learning writes stay
        # open per the demo policy). Only checked when the lock is actually
        # part of the payload, so demo instructors can still rename a unit.
        if 'is_locked' in serializer.validated_data:
            require_not_demo(self.request.user)
        serializer.save()

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
        return Response(UnitSerializer(unit, context={'request': request}).data)


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
        # Same shared-surface rule as the toggle in UnitViewSet.perform_update:
        # creating a unit already locked must not be a way around it.
        if serializer.validated_data.get('is_locked'):
            require_not_demo(self.request.user)

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
            # Phase 66: the lock gate lives in get_object(), which a list never
            # calls — so a locked unit's lessons would otherwise stream out of
            # here with their titles and bodies. Drop locked units unless the
            # requester teaches the course.
            queryset = queryset.exclude(
                Q(unit__is_locked=True)
                & ~Q(unit__course__instructor=self.request.user)
            )
        else:
            # Detail serves LessonSerializer, which nests sections and
            # attachments in full — so these rows are being fetched either way
            # and prefetching also feeds the count fields for free. Deliberately
            # NOT applied to list: LessonListSerializer nests neither, and
            # loading every section's markdown just to count rows is worse than
            # the three bulk count queries it would save.
            queryset = queryset.prefetch_related(
                'sections', 'attachments', 'questions')
        return queryset

    def get_object(self):
        # Locked units are refused here rather than in retrieve() so every
        # detail action (including reorder) is covered by one check. The
        # helper no-ops for the course instructor, so authoring is unaffected.
        lesson = super().get_object()
        require_unit_unlocked(self.request.user, lesson.unit)
        return lesson

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
        return Response(LessonSerializer(lesson, context={'request': request}).data)


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
        require_unit_unlocked(self.request.user, unit)
        # Serves LessonSerializer, which nests sections and attachments in full
        # and reports counts over all three relations.
        return Lesson.objects.filter(unit=unit).select_related(
            'unit__course'
        ).prefetch_related('sections', 'attachments', 'questions')

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
        # Same guard as CourseViewSet.enroll — this is the second join path.
        require_not_demo(request.user)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enrollment = serializer.save()
        return Response(
            EnrollmentSerializer(enrollment).data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        """PUT/PATCH — inert today (every field is read-only), guarded anyway.

        create() and destroy() both refuse the demo account; without this the
        one remaining mutating action would silently inherit demo write
        access the moment any field on EnrollmentSerializer becomes writable.
        """
        require_not_demo(request.user)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Self-unenroll — soft delete, and never for the demo account.

        Two problems with the inherited ModelViewSet.destroy (Phase 55, A4):

        1. It hard-deleted the row, cascading the student's progress away,
           where the instructor-side `remove_student` soft-deletes precisely to
           preserve grades. Same operation, two different outcomes.
        2. Every demo visitor shares one account, so a single visitor could
           un-enroll `jdoe@demo.com` for everybody until an operator re-ran
           `seed_demo_account`. Refusing outright matches the rest of the demo
           lockdown (see accounts.serializers.ProtectedPasswordChangeSerializer).
        """
        enrollment = self.get_object()
        require_not_demo(request.user)

        enrollment.is_active = False
        enrollment.save(update_fields=['is_active'])
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        # Blocks reads AND writes: a locked unit must not accrue new progress.
        require_unit_unlocked(self.request.user, lesson.unit)

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

        # Locked units drop out of BOTH sides (phase 66): a student who has
        # finished everything currently unlocked must read 100%, and their
        # completions inside a since-locked unit must not inflate the numerator.
        total_lessons = Lesson.objects.filter(
            unit__course=course, unit__is_locked=False
        ).count()

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
            lesson__unit__is_locked=False,
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

        # Lessons completed. Locked units are excluded here too, or this stat
        # disagrees with every other progress surface by exactly the amount
        # hidden behind the lock (phase 66).
        lessons_completed = LessonProgress.objects.filter(
            user=user,
            lesson__unit__is_locked=False,
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
                lesson__unit__is_locked=False,
                completed=True
            ).values_list('lesson_id', flat=True)

            # Get all lessons in course order. Locked units are skipped, so
            # "continue" never points a student at a lesson they'd be 403'd on
            # and the progress readout matches the course progress endpoint.
            all_lessons = Lesson.objects.filter(
                unit__course=course, unit__is_locked=False
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

        # Bulk fetch totals per course using annotations. Locked units are
        # filtered out of both totals so a dashboard card agrees with the
        # course progress endpoint (phase 66).
        course_totals = Course.objects.filter(id__in=course_ids).annotate(
            total_lessons=Count(
                'units__lessons', distinct=True,
                filter=Q(units__is_locked=False),
            ),
            total_quizzes=Count(
                'units__quizzes', distinct=True,
                filter=Q(units__is_locked=False),
            ),
        ).values('id', 'code', 'title', 'total_lessons', 'total_quizzes')

        # Build lookup dict
        totals_by_course = {c['id']: c for c in course_totals}

        # Bulk fetch user's completed lessons per course
        completed_lessons_by_course = dict(
            LessonProgress.objects.filter(
                user=user,
                lesson__unit__course_id__in=course_ids,
                lesson__unit__is_locked=False,
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
                quiz__unit__is_locked=False,
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

    def create(self, request, *args, **kwargs):
        """Announcements are created course-scoped, never through this route.

        Phase 73. check_object_permissions below only runs for detail routes,
        so create reached serializer.save() with no ownership check at all —
        any authenticated student could post here. It failed as an
        IntegrityError (course and author are non-null and
        AnnouncementCreateSerializer carries neither) rather than a 403, which
        turned a missing authorization check into a 500 and hid it.

        CourseAnnouncementsView is the real creation path and does check
        require_course_instructor. Closing this one rather than duplicating
        that logic keeps a single guarded entry point.
        """
        raise MethodNotAllowed(
            request.method,
            detail='Create announcements at /api/courses/<code>/announcements/.',
        )

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
                            'triggered_by': announcement.author,
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
    # Quizzes in locked units are ungradeable — students cannot open them — so
    # they must not add points to the possible total (phase 66).
    quizzes = Quiz.objects.filter(
        unit__course=course, unit__is_locked=False
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

    # Lesson completion (participation), bulk-fetched per student.
    # Locked units are excluded from both sides so participation matches the
    # progress the student is actually able to make (phase 66).
    total_lessons = Lesson.objects.filter(
        unit__course=course, unit__is_locked=False
    ).count()
    completed_lessons_by_student = dict(
        LessonProgress.objects.filter(
            lesson__unit__course=course,
            lesson__unit__is_locked=False,
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
    # Quizzes in locked units are ungradeable — students cannot open them — so
    # they must not add points to the possible total (phase 66).
    quizzes = Quiz.objects.filter(
        unit__course=course, unit__is_locked=False
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

    # Lesson completion (participation) — locked units excluded (phase 66)
    total_lessons = Lesson.objects.filter(
        unit__course=course, unit__is_locked=False
    ).count()
    completed_lessons_by_student = dict(
        LessonProgress.objects.filter(
            lesson__unit__course=course,
            lesson__unit__is_locked=False,
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

    # Paginated in Phase 55 (A6): the roster had no ceiling, and each row costs
    # a serializer pass over activity data. The roster page has no paging UI —
    # the client walks `next` — so this bounds the response size without
    # changing what an instructor sees.
    paginator = RosterPagination()
    page = paginator.paginate_queryset(enrollments, request)
    serializer = StudentRosterSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


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

    # Locked units excluded from both sides (phase 66)
    total_lessons = Lesson.objects.filter(
        unit__course=course, unit__is_locked=False
    ).count()
    completed_lessons_by_student = dict(
        LessonProgress.objects.filter(
            lesson__unit__course=course,
            lesson__unit__is_locked=False,
            completed=True
        ).values('user_id').annotate(count=Count('id')).values_list('user_id', 'count')
    )

    # Best completed attempt per (student, quiz), grouped by student. Attempts
    # in a locked unit are dropped so analytics agrees with the gradebook —
    # otherwise locking a unit leaves stale scores driving at_risk flags.
    best_by_student = {}
    for attempt in QuizAttempt.objects.filter(
        quiz__unit__course=course,
        quiz__unit__is_locked=False,
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

    # Locked units are excluded here too, matching the gradebook and
    # _analytics_student_rows (phase 66). Listing an assessment that has no
    # gradebook column and feeds no student's average is the same
    # analytics-disagrees-with-the-gradebook trap, one level down.
    unit_quizzes = []
    for quiz in Quiz.objects.filter(
        unit__course=course, unit__is_locked=False
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
        unit__course=course, unit__is_locked=False
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


# ==================== Course Invites (Phase 51) ====================

def _mask_email(email):
    """j***e@example.com — enough for the invitee to recognize themselves."""
    local, _, domain = email.partition('@')
    if len(local) <= 2:
        masked = f'{local[:1]}***'
    else:
        masked = f'{local[0]}***{local[-1]}'
    return f'{masked}@{domain}'


def _activate_enrollment(user, course):
    """Create the enrollment, or reactivate a soft-deleted one."""
    enrollment, created = Enrollment.objects.get_or_create(
        user=user, course=course)
    if not created and not enrollment.is_active:
        enrollment.is_active = True
        enrollment.save(update_fields=['is_active'])
    return enrollment


def consume_invite_for(user, course):
    """Claim the caller's pending invite on `course`. True if one was claimed.

    Phase 68: a code-based enrollment consumes its invite exactly as
    `accept_invite` does. Without this the invite stays pending and remains a
    live second way in, so a later removal could be undone with an invitation
    that was already spent.

    Targeted `filter(...).update(...)` rather than fetch-then-save, mirroring
    the phase-67 delivery writes: it re-checks `pending()` in the WHERE clause
    at write time, so it cannot clobber a concurrent revoke.

    The boolean matters. `require_pending_invite` is a read, and an instructor
    revoking in the gap between that read and the insert would otherwise lose
    a race they should win — leaving an active enrollment hanging off an
    invite the roster shows as "revoked". Callers treat False as a refusal and
    roll the enrollment back, which makes THIS the authoritative check.
    """
    email = (getattr(user, 'email', '') or '').lower()
    if not email:
        return False
    return bool(course.invites.pending().filter(email=email).update(
        accepted_at=timezone.now()))


def invite_url_for(invite):
    """The accept-page URL for an invite.

    One helper for the email and the on-demand copy-link endpoint, so the two
    can never drift into handing out different URLs for the same token.
    """
    return f'{settings.FRONTEND_URL}/invite/{invite.token}'


def _instructor_reply_to(course):
    """Reply-To for invites: the instructor, when that is a real address.

    A student who hits Reply on an invite otherwise bounces off
    noreply@ — and a From domain nobody can reply to scores badly at
    district mail gateways. The demo account is excluded: it must never have
    its address handed out, and it triggers no real mail anyway.
    """
    email = (getattr(course.instructor, 'email', '') or '').strip()
    if not email or is_demo_email(email):
        return None
    return [email]


# Below this length a "secret" is not a credential any real deployment uses,
# and blind substring replacement would shred every error message that
# happens to contain those characters — turning the one diagnostic the
# instructor gets into unreadable noise. Legibility wins at that size.
_SCRUBBABLE_SECRET_LENGTH = 8


def _delivery_error_text(exc):
    """The failure text stored on the invite and shown to the instructor.

    The raw exception is the useful part — "which host refused us, and why"
    is exactly what the roster needs to say. But it is third-party text going
    onto a UI, so the one secret this process holds that could plausibly ride
    along in an SMTP error is scrubbed first.

    Defense in depth, not a guarantee: Django's SMTP backend does not echo the
    password back, so this is here for the exception nobody predicted. Both
    forms are matched because smtplib carries the server's reply as `bytes`,
    and `str(exc)` therefore renders it through `bytes.__repr__` — a password
    containing a backslash or quote reaches the text escaped, and a plain
    substring check would sail straight past it.
    """
    text = str(exc) or 'Send failed.'
    secret = getattr(settings, 'EMAIL_HOST_PASSWORD', '') or ''

    if len(secret) >= _SCRUBBABLE_SECRET_LENGTH:
        # repr() of the secret minus its surrounding quotes is the escaped
        # form; identical to the plain form for ordinary passwords, so the
        # alternation costs nothing there.
        escaped = repr(secret)[1:-1]
        pattern = '|'.join(
            re.escape(form) for form in dict.fromkeys((secret, escaped)))
        text = re.sub(pattern, '[redacted]', text, flags=re.IGNORECASE)

    return text[:255]


def _send_invite_email_and_record(invite_id, **send_kwargs):
    """Send one invite and persist what SMTP did with it (Phase 67).

    Runs on the `send_emails_async` daemon thread. Writes through a targeted
    `filter(pk=...).update(...)` rather than `invite.save()` so it can only
    ever touch the two delivery columns — a concurrent revoke or re-issue on
    the same row is not clobbered by a stale in-memory instance.
    """
    try:
        sent = send_course_invite_link_email(fail_silently=False, **send_kwargs)
    except Exception as exc:
        CourseInvite.objects.filter(pk=invite_id).update(
            email_sent_at=None, email_error=_delivery_error_text(exc))
        raise

    if not sent:
        # The only non-exception falsy path is the demo-account refusal.
        CourseInvite.objects.filter(pk=invite_id).update(
            email_sent_at=None, email_error='Email was not sent.')
        return

    CourseInvite.objects.filter(pk=invite_id).update(
        email_sent_at=timezone.now(), email_error=None)


def _queue_invite_email(invite, email_tasks):
    instructor_name = (
        invite.invited_by.get_full_name() or invite.invited_by.email)
    email_tasks.append((
        _send_invite_email_and_record,
        (invite.pk,),
        {
            'recipient_email': invite.email,
            'course_title': invite.course.title,
            'instructor_name': instructor_name,
            'invite_url': invite_url_for(invite),
            'triggered_by': invite.invited_by,
            'reply_to': _instructor_reply_to(invite.course),
        },
    ))


@api_view(['GET', 'POST'])
@perm_classes([IsAuthenticated])
# @throttle_classes REPLACES DEFAULT_THROTTLE_CLASSES, and the scoped class
# below exempts safe methods — so listing this way left GET with no throttle at
# all. Re-list the global per-user ceiling to cover the read, exactly as
# lesson_section_import_slide does. (demo_login, accept_invite and the
# password-reset views used to drop the globals as well; phase 73 re-listed
# them, so this is now the pattern everywhere rather than the exception.)
@throttle_classes([ClientIPUserRateThrottle, ClientIPScopedWriteRateThrottle])
def course_invites(request, course_code):
    """List invites for a course, or bulk-invite students by email.

    POST body: {"emails": ["a@x.com", ...]}. Per-email outcomes: invited,
    resent (non-revoked invite existed — token/expiry refreshed, email
    re-sent), already_enrolled (skipped), invalid.
    """
    course = get_object_or_404(Course, code=course_code)
    require_course_instructor(
        request.user, course,
        "Only the course instructor can manage invitations."
    )

    if request.method == 'GET':
        invites = course.invites.select_related('invited_by').all()
        return Response(CourseInviteSerializer(invites, many=True).data)

    emails = request.data.get('emails')
    if not isinstance(emails, list) or not emails:
        return Response(
            {'detail': 'Provide a non-empty list of email addresses.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    results = []
    seen = set()
    email_tasks = []
    for raw in emails:
        email = str(raw).strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)

        try:
            validate_email(email)
        except DjangoValidationError:
            results.append({'email': email, 'status': 'invalid'})
            continue

        # The shared demo account and the instructor's own address can never
        # meaningfully accept an invite.
        if is_demo_email(email) or email == course.instructor.email.strip().lower():
            results.append({'email': email, 'status': 'invalid'})
            continue

        existing_user = User.objects.filter(email=email).first()
        if existing_user and Enrollment.objects.filter(
                user=existing_user, course=course, is_active=True).exists():
            results.append({'email': email, 'status': 'already_enrolled'})
            continue

        invite = CourseInvite.objects.filter(
            course=course, email=email, revoked_at__isnull=True).first()
        if invite is not None:
            was_pending = invite.is_pending
            invite.refresh(invited_by=request.user)
            results.append({
                'email': email,
                'status': 'resent' if was_pending else 'invited',
            })
        else:
            invite = CourseInvite.objects.create(
                course=course, email=email, invited_by=request.user)
            results.append({'email': email, 'status': 'invited'})

        _queue_invite_email(invite, email_tasks)

    if email_tasks:
        send_emails_async(email_tasks)

    return Response({'results': results})


# @api_view exposes the generated view class as `.cls`; the scoped throttle
# reads its scope from there (rate: THROTTLE_INVITE_SEND, unset = unlimited).
course_invites.cls.throttle_scope = 'invite_send'


@api_view(['DELETE'])
@perm_classes([IsAuthenticated])
def revoke_course_invite(request, course_code, invite_id):
    """Soft-revoke a pending invite; its link stops working immediately."""
    course = get_object_or_404(Course, code=course_code)
    require_course_instructor(
        request.user, course,
        "Only the course instructor can manage invitations."
    )

    invite = get_object_or_404(CourseInvite, id=invite_id, course=course)
    if invite.accepted_at is not None:
        return Response(
            {'detail': 'This invite has already been accepted and cannot '
                       'be revoked. Remove the student from the roster '
                       'instead.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if invite.revoked_at is None:
        invite.revoked_at = timezone.now()
        invite.save(update_fields=['revoked_at'])

    return Response({'message': f'Invite for {invite.email} revoked.'})


# Instructor-facing wording; INVITE_DEAD_DETAILS below is what the invitee
# sees. Handing out a link that is already dead is worse than refusing.
INVITE_LINK_DEAD_DETAILS = {
    'accepted': 'This invitation has already been accepted, so its link no '
                'longer works. The student is on the roster.',
    'revoked': 'This invitation has been revoked. Re-invite the student to '
               'get a working link.',
    'expired': 'This invitation has expired. Re-send it to get a fresh link.',
}


@api_view(['GET'])
@perm_classes([IsAuthenticated])
# Re-list the global per-user ceiling: @throttle_classes replaces
# DEFAULT_THROTTLE_CLASSES wholesale, and THROTTLE_INVITE_LINK is unset
# locally and in tests (see the note on course_invites).
@throttle_classes([ClientIPUserRateThrottle, ClientIPScopedRateThrottle])
def invite_link(request, course_code, invite_id):
    """The invite URL for one pending invite, fetched on demand (Phase 67).

    The instructor's out-of-band path when our mail never lands: copy the
    link, hand it over in class or by text. Deliberately NOT part of the
    invite list payload — a live token in a bulk response ends up in browser
    cache, proxy logs, and screen shares.
    """
    course = get_object_or_404(Course, code=course_code)
    require_course_instructor(
        request.user, course,
        "Only the course instructor can manage invitations."
    )
    # Same guard as the join-code endpoints. Handing out a live token for the
    # shared demo course is not a real scenario today, but the two new
    # instructor endpoints in this phase have to agree — an asymmetric demo
    # guard is how one of them quietly becomes the way in.
    require_not_demo_course(course)

    # Scoped by course, not just by id: an invite belonging to someone else's
    # course must 404 here even though this instructor is an instructor.
    invite = get_object_or_404(CourseInvite, id=invite_id, course=course)
    if not invite.is_pending:
        return Response(
            {'detail': INVITE_LINK_DEAD_DETAILS[invite.status],
             'status': invite.status},
            status=status.HTTP_400_BAD_REQUEST
        )

    return Response({'invite_url': invite_url_for(invite)})


invite_link.cls.throttle_scope = 'invite_link'


# Phase 68. Deleting is for tidying the roster, not for cancelling anything:
# a PENDING invite must be revoked (which stops its link working) before it
# can be removed, so a misclick can never void a live invitation. Deleting a
# closed invite destroys no enrollment — the `Enrollment` row is the record
# that matters and lives in a separate table.
PENDING_INVITE_DELETE_DETAIL = (
    'This invitation is still open. Revoke it first if you want to cancel it, '
    'then delete it.'
)


@api_view(['DELETE'])
@perm_classes([IsAuthenticated])
def delete_course_invite(request, course_code, invite_id):
    """Hard-delete one closed (accepted/revoked/expired) invite.

    Revoked rows are otherwise unbounded per (course, email): the unique
    constraint is conditional on `revoked_at IS NULL`, so every
    invite -> revoke -> re-invite cycle leaves another dead row on the roster
    forever. This is the only way to clear them.
    """
    course = get_object_or_404(Course, code=course_code)
    require_course_instructor(
        request.user, course,
        "Only the course instructor can manage invitations."
    )
    require_not_demo_course(course)

    # Scoped by course, not just by id: an invite belonging to someone else's
    # course must 404 here even for a real instructor.
    invite = get_object_or_404(CourseInvite, id=invite_id, course=course)
    if invite.status == 'pending':
        return Response(
            {'detail': PENDING_INVITE_DELETE_DETAIL},
            status=status.HTTP_400_BAD_REQUEST
        )

    invite.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['DELETE'])
@perm_classes([IsAuthenticated])
def delete_closed_course_invites(request, course_code):
    """Hard-delete every closed invite on the course; returns {'deleted': n}.

    "Closed" is expressed in SQL as "not in pending()" rather than by
    evaluating the `status` property row by row — the expiry half of the
    lifecycle is a timestamp comparison, and doing it in Python would both
    scan the table and open a race against invites expiring mid-loop.
    """
    course = get_object_or_404(Course, code=course_code)
    require_course_instructor(
        request.user, course,
        "Only the course instructor can manage invitations."
    )
    require_not_demo_course(course)

    deleted, _ = course.invites.exclude(
        pk__in=course.invites.pending().values('pk')
    ).delete()
    return Response({'deleted': deleted})


# ==================== Course join code (Phase 67) ====================

# One string for every failure mode of /join/. Distinguishing "no such code"
# from "that email has no invite" would turn this endpoint into an oracle for
# "is alice@district.edu invited to this course?" — answerable by anyone
# holding a code students are told to share freely.
JOIN_GENERIC_ERROR = "That code and email don't match an open invitation."


@api_view(['GET', 'POST', 'DELETE'])
@perm_classes([IsAuthenticated])
def course_join_code(request, course_code):
    """Read, generate/rotate, or turn off this course's join code.

    Instructor-only. POST both generates the first code and rotates an
    existing one — the previous code stops working the instant it is
    replaced. No expiry: off is off.

    No scoped throttle here on purpose. The tight `join_code` rate belongs on
    the public redemption endpoint where anonymous abuse lives; this one is
    instructor-only and already covered by the global per-user ceiling.
    """
    course = get_object_or_404(Course, code=course_code)
    require_course_instructor(
        request.user, course,
        "Only the course instructor can manage the join code."
    )
    # The shared public demo course must never become joinable: everyone who
    # clicks "Try the demo" is already the same account.
    require_not_demo_course(course)

    if request.method == 'GET':
        return Response({'join_code': course.join_code})

    if request.method == 'POST':
        course.join_code = generate_join_code()
    else:
        course.join_code = None
    course.save(update_fields=['join_code'])

    return Response({'join_code': course.join_code})


@api_view(['POST'])
@perm_classes([AllowAny])
# BOTH global ceilings are re-listed deliberately, unlike accept_invite.
# @throttle_classes replaces DEFAULT_THROTTLE_CLASSES wholesale, so listing
# only the scoped class would leave this endpoint COMPLETELY unlimited
# whenever THROTTLE_JOIN_CODE is unset — and unlike accept_invite, the caller
# here holds no secret token: the code is meant to be read out to a class.
# The user throttle matters as much as the anon one: AnonRateThrottle returns
# no cache key for an authenticated request, so without it any logged-in
# account — every enrolled student has one — could walk an email list against
# a shared code with no ceiling at all.
@throttle_classes([
    ClientIPAnonRateThrottle, ClientIPUserRateThrottle,
    ClientIPScopedRateThrottle,
])
def join_with_code(request):
    """Redeem a course join code for an invite token (Phase 67).

    A delivery channel, not an authorization: the code only *finds* an invite
    that already exists for that exact address. A leaked code enrolls nobody.
    This view creates no user, no session, and no enrollment — it hands back a
    token and the frontend continues into the existing /invite/<token> accept
    flow, so account creation stays in one place.
    """
    join_code = normalize_join_code(request.data.get('join_code'))
    email = str(request.data.get('email') or '').strip().lower()

    generic_failure = Response(
        {'detail': JOIN_GENERIC_ERROR}, status=status.HTTP_400_BAD_REQUEST)

    # An empty/absent code must never reach the lookup: courses with the
    # fallback turned off carry NULL, and a blank must not be treated as
    # "match whatever has no code".
    if not join_code or not email:
        return generic_failure

    course = Course.objects.select_related('instructor').filter(
        join_code=join_code).first()
    if course is None:
        return generic_failure
    require_not_demo_course(course)

    # Exact match, deliberately — do NOT "improve" this to `email__iexact`.
    # On Postgres iexact compiles to UPPER(col) = UPPER(value), and the
    # non-ICU UPPER() folds Turkish dotless i (U+0131) onto ASCII 'I'. An
    # invite for `ıid@example.com` would then be handed to whoever typed the
    # entirely different — and equally valid — address `iid@example.com`:
    # someone else's token, to someone who asked for their own address.
    # Case is already handled: both sides are lowercased, the input above and
    # the stored value in `course_invites`.
    invite = CourseInvite.objects.pending().filter(
        course=course, email=email).first()
    if invite is None:
        return generic_failure

    return Response({
        'token': invite.token,
        'course_title': course.title,
        'course_code': course.code,
    })


join_with_code.cls.throttle_scope = 'join_code'


@api_view(['GET'])
@perm_classes([AllowAny])
def invite_detail(request, token):
    """Public status lookup for the accept page. Never 500s on bad tokens."""
    invite = CourseInvite.objects.filter(
        token=token).select_related('course').first()
    if invite is None:
        return Response(
            {'status': 'invalid', 'course_title': None, 'course_code': None,
             'email_masked': None, 'account_exists': False},
            status=status.HTTP_404_NOT_FOUND
        )

    return Response({
        'course_title': invite.course.title,
        'course_code': invite.course.code,
        'email_masked': _mask_email(invite.email),
        'status': invite.status,
        'account_exists': User.objects.filter(email=invite.email).exists(),
    })


INVITE_DEAD_DETAILS = {
    'accepted': 'This invitation has already been used.',
    'revoked': 'This invitation has been revoked by the instructor.',
    'expired': 'This invitation has expired. Ask your instructor for a '
               'new one.',
}


# Phase 73: this listed only the scoped class, which replaces
# DEFAULT_THROTTLE_CLASSES outright — so an anonymous account-creation endpoint
# had exactly one ceiling, and that ceiling defaulted to unlimited. Re-list the
# globals, matching join_with_code above. The caller does hold a secret token
# here, but "holds a token" is not a rate limit.
@api_view(['POST'])
@perm_classes([AllowAny])
@throttle_classes([
    ClientIPAnonRateThrottle, ClientIPUserRateThrottle,
    ClientIPScopedRateThrottle,
])
def accept_invite(request, token):
    """Accept an invite: create-account path or existing-account path.

    New account: body {first_name, last_name, password, agree_terms}. The
    user is created with a verified email (they proved the address by
    clicking the link), enrolled, and handed a JWT pair so the frontend can
    log them straight in. Existing account: the request must be
    authenticated as the invited email; enrolls and returns the enrollment.
    Both paths are atomic.
    """
    invite = CourseInvite.objects.filter(
        token=token).select_related('course').first()
    if invite is None:
        return Response(
            {'detail': 'This invitation link is not valid.',
             'status': 'invalid'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if not invite.is_pending:
        return Response(
            {'detail': INVITE_DEAD_DETAILS[invite.status],
             'status': invite.status},
            status=status.HTTP_400_BAD_REQUEST
        )

    course = invite.course
    existing_user = User.objects.filter(email=invite.email).first()

    if existing_user is not None:
        if (not request.user.is_authenticated
                or request.user.email.lower() != invite.email):
            return Response(
                {'detail': f'This invitation is for {_mask_email(invite.email)}. '
                           'Log in with that account to join the course.',
                 'account_exists': True},
                status=status.HTTP_403_FORBIDDEN
            )
        if existing_user == course.instructor:
            return Response(
                {'detail': 'Instructors cannot enroll in their own courses.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        with transaction.atomic():
            enrollment = _activate_enrollment(existing_user, course)
            invite.accepted_at = timezone.now()
            invite.save(update_fields=['accepted_at'])
        return Response(EnrollmentSerializer(enrollment).data)

    # New-account path.
    first_name = str(request.data.get('first_name', '')).strip()
    last_name = str(request.data.get('last_name', '')).strip()
    password = request.data.get('password') or ''
    agree_terms = request.data.get('agree_terms') is True

    errors = {}
    if not first_name:
        errors['first_name'] = ['First name is required.']
    if not last_name:
        errors['last_name'] = ['Last name is required.']
    if not agree_terms:
        errors['agree_terms'] = [
            'You must agree to the Terms of Service and Privacy Policy.']
    try:
        validate_password(password)
    except DjangoValidationError as exc:
        errors['password'] = list(exc.messages)
    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        user = User.objects.create_user(
            email=invite.email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_instructor=False,
        )
        EmailAddress.objects.create(
            user=user, email=invite.email, verified=True, primary=True)
        _activate_enrollment(user, course)
        invite.accepted_at = timezone.now()
        invite.save(update_fields=['accepted_at'])

    refresh = RefreshToken.for_user(user)
    return Response(
        {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user, context={'request': request}).data,
        },
        status=status.HTTP_201_CREATED
    )


accept_invite.cls.throttle_scope = 'invite_accept'


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
        unit__course=course, unit__is_locked=False
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

    # Calculate participation (lesson completion) — locked units excluded
    total_lessons = Lesson.objects.filter(
        unit__course=course, unit__is_locked=False
    ).count()
    completed_lessons = LessonProgress.objects.filter(
        user=request.user,
        lesson__unit__course=course,
        lesson__unit__is_locked=False,
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
    lesson = get_object_or_404(
        Lesson.objects.select_related('unit__course'), pk=lesson_id)
    course = lesson.unit.course

    is_instructor = is_course_instructor(request.user, course)
    require_course_access(request.user, course, "You must be enrolled in this course.")
    require_unit_unlocked(request.user, lesson.unit)

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
    lesson = get_object_or_404(
        Lesson.objects.select_related('unit__course'), pk=lesson_id)
    question = get_object_or_404(LessonQuestion, pk=question_id, lesson=lesson)
    course = lesson.unit.course

    is_instructor = is_course_instructor(request.user, course)
    require_course_access(request.user, course, "You must be enrolled in this course.")
    require_unit_unlocked(request.user, lesson.unit)

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


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def lesson_questions_status(request, lesson_id):
    """
    Get the status of a student's progress on lesson questions.
    Returns total questions, answered count, correct count, and whether they can complete the lesson.
    """
    lesson = get_object_or_404(
        Lesson.objects.select_related('unit__course'), pk=lesson_id)
    course = lesson.unit.course

    require_course_access(request.user, course, "You must be enrolled in this course.")
    require_unit_unlocked(request.user, lesson.unit)

    total_questions = lesson.questions.count()

    if total_questions == 0:
        return Response({
            'total_questions': 0,
            'answered_questions': 0,
            'correct_answers': 0,
            'all_correct': True,
            'requires_quiz': False,
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

    # Phase 54: `can_complete_lesson` must agree with the real completion gate
    # (validate_completed): when `requires_quiz` is set, only a passing attempt
    # unlocks completion; otherwise the questions are optional and don't gate.
    gated = lesson.requires_quiz
    can_complete = has_passed if gated else True

    return Response({
        'total_questions': total_questions,
        'answered_questions': answered_count,
        'correct_answers': correct_count,
        'all_correct': all_correct,
        'requires_quiz': gated,
        'can_complete_lesson': can_complete,
        'attempt_count': attempt_count,
        'max_attempts': None,
        'attempts_remaining': None,
        'can_attempt': True,
        'has_passed': has_passed,
    })


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
    lesson = get_object_or_404(
        Lesson.objects.select_related('unit__course'), pk=lesson_id)
    require_enrollment(request.user, lesson.unit.course)
    require_unit_unlocked(request.user, lesson.unit)

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
    lesson = get_object_or_404(
        Lesson.objects.select_related('unit__course'), pk=lesson_id)
    require_enrollment(request.user, lesson.unit.course)
    require_unit_unlocked(request.user, lesson.unit)

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
    lesson = get_object_or_404(
        Lesson.objects.select_related('unit__course'), pk=lesson_id)
    require_enrollment(request.user, lesson.unit.course)
    require_unit_unlocked(request.user, lesson.unit)

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

# Phase 73: POST here was the one upload path with no scoped rate limit. Uses
# the write-only variant so the student-facing GET (every lesson view lists its
# attachments) is never throttled, and re-lists the globals because naming any
# throttle replaces DEFAULT_THROTTLE_CLASSES.
@api_view(['GET', 'POST'])
@perm_classes([IsAuthenticated])
@throttle_classes([ClientIPUserRateThrottle, ClientIPScopedWriteRateThrottle])
def lesson_attachments(request, lesson_id):
    """
    GET: List attachments for a lesson (students and instructors)
    POST: Upload attachment to a lesson (instructor only)
    """
    lesson = get_object_or_404(
        Lesson.objects.select_related('unit__course'), pk=lesson_id)
    course = lesson.unit.course

    require_course_access(request.user, course, "You must be enrolled in this course.")
    require_unit_unlocked(request.user, lesson.unit)

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
        # Phase 73: this endpoint was missing from the demo lockdown entirely,
        # so a visitor on the shared account could add files to a demo course
        # and every later visitor would see them.
        require_not_demo(request.user)

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

        # Phase 73: the per-file limit alone let one request carry ten
        # near-limit files, so the ceiling on a single request was really 10x
        # the number anyone had agreed to.
        total_bytes = sum(f.size for f in files)
        if total_bytes > settings.ATTACHMENT_MAX_REQUEST_BYTES:
            request_limit_mb = (
                settings.ATTACHMENT_MAX_REQUEST_BYTES // (1024 * 1024))
            return Response(
                {'error': f'Upload exceeds the {request_limit_mb}MB total '
                          f'limit for one request. Send fewer files at a time.'},
                status=status.HTTP_400_BAD_REQUEST
            )

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

            # Phase 73: extension and size are both client-supplied strings, so
            # confirm the bytes agree with the claimed type. The risk is not
            # server-side execution — attachments live in a private bucket on
            # another origin — it is that the filename is all a student sees
            # before opening it, which makes a disguised payload a phishing
            # primitive aimed at the class.
            content_error = verify_upload(f, file_ext)
            if content_error:
                return Response(
                    {'error': content_error},
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


# ScopedRateThrottle reads its scope off the generated view class. Without this
# the throttle is installed but has no rate to enforce.
lesson_attachments.cls.throttle_scope = 'attachment_upload'


@api_view(['DELETE'])
@perm_classes([IsAuthenticated])
def lesson_attachment_detail(request, lesson_id, attachment_id):
    """Delete an attachment (instructor only)."""
    lesson = get_object_or_404(
        Lesson.objects.select_related('unit__course'), pk=lesson_id)
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
    lesson = get_object_or_404(
        Lesson.objects.select_related('unit__course'), pk=lesson_id)
    course = lesson.unit.course

    require_course_access(request.user, course, "You must be enrolled in this course.")
    require_unit_unlocked(request.user, lesson.unit)

    if request.method == 'GET':
        sections = lesson.sections.all().order_by('order')
        serializer = LessonSectionSerializer(sections, many=True, context={'request': request})
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
                LessonSectionSerializer(section, context={'request': request}).data,
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
    lesson = get_object_or_404(
        Lesson.objects.select_related('unit__course'), pk=lesson_id)
    course = lesson.unit.course
    section = get_object_or_404(LessonSection, pk=section_id, lesson=lesson)

    require_course_access(request.user, course, "You must be enrolled in this course.")
    require_unit_unlocked(request.user, lesson.unit)

    if request.method == 'GET':
        serializer = LessonSectionSerializer(section, context={'request': request})
        return Response(serializer.data)

    elif request.method == 'PUT':
        require_course_instructor(
            request.user, course,
            "Only instructors can update sections."
        )

        serializer = LessonSectionCreateSerializer(section, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(LessonSectionSerializer(section, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        require_course_instructor(
            request.user, course,
            "Only instructors can delete sections."
        )

        deleted_order = section.order

        # Delete the slide image blob from storage before the row (same
        # pattern as lesson_attachment_detail).
        if section.image:
            section.image.delete(save=False)

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
    lesson = get_object_or_404(
        Lesson.objects.select_related('unit__course'), pk=lesson_id)
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
    serializer = LessonSectionSerializer(sections, many=True, context={'request': request})
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
    lesson = get_object_or_404(
        Lesson.objects.select_related('unit__course'), pk=lesson_id)
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
        LessonSectionSerializer(created, many=True, context={'request': request}).data,
        status=status.HTTP_201_CREATED
    )


# Extensions the slide-import endpoint accepts, mapped to the Pillow formats
# the bytes must actually decode as (same magic-byte rationale as
# accounts.views.upload_avatar: the allowlist bounds which Pillow decoders
# untrusted bytes can reach, and verify() alone accepts any decodable format).
SLIDE_IMAGE_EXTENSION_FORMATS = {
    'png': {'PNG'},
    'jpg': {'JPEG'},
    'jpeg': {'JPEG'},
    'webp': {'WEBP'},
}

# Hard ceiling on sections per lesson after a slide import: imports append one
# section per slide, so a runaway client could otherwise grow a lesson without
# bound (the player renders one dot per section).
MAX_SECTIONS_PER_LESSON = 200

# Cap on extracted alt text. The client truncates the PDF text layer to ~1000
# chars, but image_alt is a TextField, so without a server cap any client can
# store megabytes per section and bloat every lesson-detail response.
MAX_IMAGE_ALT_CHARS = 2000


@api_view(['POST'])
@perm_classes([IsAuthenticated])
# @throttle_classes REPLACES DEFAULT_THROTTLE_CLASSES, so the global
# per-user ceiling has to be re-listed here or this endpoint — which writes
# 5 MB objects to shared storage — would be the only unthrottled write in
# the app when THROTTLE_SLIDE_IMPORT is unset.
@throttle_classes([ClientIPUserRateThrottle, ClientIPScopedWriteRateThrottle])
def lesson_section_import_slide(request, lesson_id):
    """Create one slide section from a client-rasterized PDF page.

    Multipart fields: ``image`` (required file), ``title`` and ``image_alt``
    (optional text). The client loops pages, one request per slide — that is
    what makes keep-what-succeeded + retry-remaining possible. This endpoint
    is the ONLY writer of ``LessonSection.image`` (the normal section
    serializers exclude it so full-object editor PUTs can't wipe it).
    """
    lesson = get_object_or_404(
        Lesson.objects.select_related('unit__course'), pk=lesson_id)
    course = lesson.unit.course

    require_course_instructor(
        request.user, course,
        "Only instructors can import slides."
    )
    # Slide uploads write to shared media storage, which falls under the demo
    # policy's shared-surface rule even though ordinary section edits are
    # learning writes.
    require_not_demo(request.user)

    image_file = request.FILES.get('image')
    if image_file is None:
        return Response(
            {'error': 'No image file provided. Use the "image" field.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    file_ext = image_file.name.rsplit('.', 1)[-1].lower() if '.' in image_file.name else ''
    if file_ext not in SLIDE_IMAGE_EXTENSION_FORMATS:
        return Response(
            {'error': f'File type ".{file_ext}" is not allowed. Allowed types: '
                      f'{", ".join(sorted(SLIDE_IMAGE_EXTENSION_FORMATS))}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if image_file.size > settings.SLIDE_IMAGE_MAX_UPLOAD_BYTES:
        max_mb = settings.SLIDE_IMAGE_MAX_UPLOAD_BYTES // (1024 * 1024)
        return Response(
            {'error': f'Slide image exceeds the {max_mb} MB size limit.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Extension and content type are client-supplied; confirm the bytes really
    # are an image of the claimed format (see accounts.views.upload_avatar for
    # the full rationale — .format must be read BEFORE verify(), and verify()
    # consumes the file so it must be rewound afterwards).
    try:
        image = PILImage.open(image_file)
        detected_format = image.format
        image.verify()
    except Exception:
        return Response(
            {'error': 'Slide image is not a valid image file.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if detected_format not in SLIDE_IMAGE_EXTENSION_FORMATS[file_ext]:
        return Response(
            {'error': f'Slide image contents are {detected_format or "an unknown format"}, '
                      f'which does not match its ".{file_ext}" extension.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    image_file.seek(0)

    title = request.data.get('title', '')
    image_alt = request.data.get('image_alt', '')
    if not isinstance(title, str) or not isinstance(image_alt, str):
        return Response(
            {'error': 'title and image_alt must be text.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if len(title) > 200:
        return Response(
            {'error': 'title must be 200 characters or fewer.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if len(image_alt) > MAX_IMAGE_ALT_CHARS:
        return Response(
            {'error': f'image_alt must be {MAX_IMAGE_ALT_CHARS} characters or fewer.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    with transaction.atomic():
        # Serialize concurrent imports into the same lesson. The section-count
        # cap and the Max(order)+1 assignment below are both read-then-write:
        # without the lock, two overlapping imports pick the same order (500 on
        # the lesson+order unique constraint) and can both pass a 199-section
        # cap check. Locking the lesson row is enough — every writer of this
        # lesson's sections goes through it.
        Lesson.objects.select_for_update().get(pk=lesson.pk)

        if lesson.sections.count() >= MAX_SECTIONS_PER_LESSON:
            return Response(
                {'error': f'This lesson already has {MAX_SECTIONS_PER_LESSON} '
                          f'sections; cannot import more slides.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        max_order = lesson.sections.aggregate(Max('order'))['order__max']
        # Not `(max_order or -1) + 1`: a lone section at order 0 would make
        # that expression collide with it (0 is falsy).
        order = 0 if max_order is None else max_order + 1

        section = LessonSection.objects.create(
            lesson=lesson,
            title=title or f'Slide {order + 1}',
            layout='slide',
            image=image_file,
            image_alt=image_alt,
            order=order,
        )

    return Response(
        LessonSectionSerializer(section, context={'request': request}).data,
        status=status.HTTP_201_CREATED
    )


lesson_section_import_slide.cls.throttle_scope = 'slide_import'


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
    lesson = get_object_or_404(
        Lesson.objects.select_related('unit__course'), pk=lesson_id)
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
        # course_code/course_title on the serializer are FK traversals — without
        # this the list endpoint costs one query per reminder.
        return InstructorReminder.objects.filter(
            instructor=self.request.user).select_related('course')

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
    node is completed; `current` is the first unlocked-but-incomplete node.
    Everything else incomplete is locked.
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

    # The instructor sees their own course as if nothing were locked.
    viewer_is_instructor = is_course_instructor(request.user, course)

    # Flatten: for each unit (by order), lessons (by order) then quizzes
    # (by order) as boss nodes. Model Meta orderings apply to the prefetches.
    nodes = []
    unit_groups = []
    for unit in course.units.all():
        unit_start = len(nodes)
        unit_locked = unit.is_locked and not viewer_is_instructor
        for lesson in unit.lessons.all():
            nodes.append({
                'node_type': 'lesson',
                'obj': lesson,
                'completed': lesson.id in completed_lesson_ids,
                'unit_locked': unit_locked,
            })
        for quiz in unit.quizzes.all():
            nodes.append({
                'node_type': 'quiz',
                'obj': quiz,
                'completed': quiz.id in passed_quiz_ids,
                'unit_locked': unit_locked,
            })
        unit_groups.append((unit, nodes[unit_start:]))

    # Base unlock rule: first node, or previous node completed — computed over
    # the reachable nodes only. An instructor-locked unit is transparent to the
    # chain rather than a wall: locking unit 2 must not sequence-lock unit 3.
    open_nodes = [node for node in nodes if not node['unit_locked']]
    for node in nodes:
        node['unlocked'] = False
    for i, node in enumerate(open_nodes):
        node['unlocked'] = i == 0 or open_nodes[i - 1]['completed']

    # Current = first unlocked-but-incomplete node in the sequence.
    current_node_id = None
    for node in open_nodes:
        if node['unlocked'] and not node['completed']:
            node['current'] = True
            current_node_id = f"{node['node_type']}-{node['obj'].id}"
            break

    def node_payload(node):
        obj = node['obj']
        lock_reason = None
        if node['unit_locked']:
            # Locked by the instructor beats every other state — a completed
            # lesson in a since-locked unit still reads as locked.
            state = 'locked'
            lock_reason = 'instructor'
        elif node['completed']:
            state = 'completed'
        elif node.get('current'):
            state = 'current'
        elif node['unlocked']:
            state = 'unlocked'
        else:
            state = 'locked'
            lock_reason = 'sequence'
        payload = {
            'node_type': node['node_type'],
            'id': obj.id,
            # Withhold the real title inside an instructor-locked unit — the
            # rest of the phase hides lesson titles from students, and the map
            # would otherwise be the one surface that prints them.
            'title': (
                'Locked lesson' if node['node_type'] == 'lesson' else 'Locked quiz'
            ) if node['unit_locked'] else obj.title,
            'order': obj.order,
            'state': state,
            'lock_reason': lock_reason,
        }
        if node['node_type'] == 'quiz':
            # Scrubbed alongside the title for a locked unit: the passing bar
            # and the student's own best score both describe hidden content.
            payload['passing_score'] = (
                None if node['unit_locked'] else obj.passing_score
            )
            payload['best_score'] = (
                None if node['unit_locked'] else best_scores.get(obj.id)
            )
        return payload

    data = {
        'course_code': course.code,
        'course_title': course.title,
        # Totals count reachable nodes only, so the map's progress readout
        # agrees with the course progress endpoint.
        'total_nodes': len(open_nodes),
        'completed_nodes': sum(1 for node in open_nodes if node['completed']),
        'current_node_id': current_node_id,
        'units': [
            {
                'id': unit.id,
                'title': unit.title,
                'order': unit.order,
                'is_locked': unit.is_locked,
                'nodes': [node_payload(node) for node in group],
            }
            for unit, group in unit_groups
        ],
    }
    return Response(CourseMapSerializer(data).data)
