from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q

from courses.models import Course, Unit
from courses.permissions import (
    is_course_instructor, require_course_instructor,
    require_course_access, require_enrollment,
)
from notifications.signals import notify_student_resubmission_allowed
from .models import Assignment, Submission, SubmissionFile, SubmissionHistory, Grade
from .serializers import (
    AssignmentListSerializer,
    AssignmentDetailSerializer,
    AssignmentCreateUpdateSerializer,
    SubmissionSerializer,
    SubmissionCreateUpdateSerializer,
    SubmissionSubmitSerializer,
    GradeSubmissionSerializer,
)
from .utils import calculate_late_penalty


class AssignmentListView(generics.ListAPIView):
    """List assignments for a course."""
    serializer_class = AssignmentListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        course_code = self.kwargs['course_code']
        course = get_object_or_404(Course, code=course_code)
        require_course_access(self.request.user, course)

        queryset = Assignment.objects.filter(
            unit__course=course
        ).select_related('unit', 'unit__course')

        # For students, filter out assignments that are not yet available
        if not is_course_instructor(self.request.user, course):
            now = timezone.now()
            queryset = queryset.filter(
                Q(available_from__isnull=True) | Q(available_from__lte=now)
            )

        return queryset


class UnitAssignmentListCreateView(generics.ListCreateAPIView):
    """List/create assignments for a specific unit."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AssignmentCreateUpdateSerializer
        return AssignmentListSerializer

    def get_queryset(self):
        unit = get_object_or_404(Unit, id=self.kwargs['unit_id'])
        require_course_access(self.request.user, unit.course)
        return Assignment.objects.filter(unit=unit)

    def perform_create(self, serializer):
        unit = get_object_or_404(Unit, id=self.kwargs['unit_id'])
        require_course_instructor(
            self.request.user, unit.course,
            "Only the course instructor can create assignments."
        )

        # Auto-set order if not provided
        if 'order' not in serializer.validated_data:
            max_order = Assignment.objects.filter(unit=unit).count()
            serializer.save(unit=unit, order=max_order + 1)
        else:
            serializer.save(unit=unit)


class AssignmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get/update/delete an assignment."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AssignmentCreateUpdateSerializer
        return AssignmentDetailSerializer

    def get_object(self):
        assignment = get_object_or_404(
            Assignment.objects.select_related('unit__course'),
            id=self.kwargs['pk']
        )
        course = assignment.unit.course
        require_course_access(self.request.user, course, "You must be enrolled in this course.")
        return assignment

    def perform_update(self, serializer):
        require_course_instructor(
            self.request.user, serializer.instance.course,
            "Only the course instructor can update assignments."
        )
        serializer.save()

    def perform_destroy(self, instance):
        require_course_instructor(
            self.request.user, instance.course,
            "Only the course instructor can delete assignments."
        )
        instance.delete()


class MySubmissionView(generics.RetrieveUpdateAPIView):
    """
    Get or update the current user's submission for an assignment.
    Creates a draft submission if none exists.
    Handles multiple file uploads (max 3).
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return SubmissionCreateUpdateSerializer
        return SubmissionSerializer

    def get_object(self):
        assignment = get_object_or_404(
            Assignment.objects.select_related('unit__course'),
            id=self.kwargs['assignment_id']
        )
        course = assignment.unit.course

        # Must be actively enrolled (not instructor)
        require_enrollment(
            self.request.user, course,
            "You must be enrolled in this course to submit."
        )

        # Check if assignment is available for students
        if not assignment.is_available:
            raise PermissionDenied("This assignment is not yet available.")

        submission, created = Submission.objects.get_or_create(
            assignment=assignment,
            student=self.request.user
        )
        return submission

    def update(self, request, *args, **kwargs):
        submission = self.get_object()

        # Check if submission can be modified
        if submission.status in ['submitted', 'graded']:
            return Response(
                {'error': 'Cannot modify a submission that has already been submitted.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Handle content update
        if 'content' in request.data:
            submission.content = request.data['content']
            submission.save()

        # Handle file uploads (max 3)
        files = request.FILES.getlist('files')
        if files:
            current_file_count = submission.files.count()
            if current_file_count + len(files) > 3:
                return Response(
                    {'error': f'Maximum 3 files allowed. You have {current_file_count} and are trying to add {len(files)}.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            for f in files:
                SubmissionFile.objects.create(
                    submission=submission,
                    file=f,
                    filename=f.name
                )

        # Handle file deletion
        delete_file_ids = request.data.getlist('delete_files') if hasattr(request.data, 'getlist') else request.data.get('delete_files', [])
        if delete_file_ids:
            if isinstance(delete_file_ids, str):
                delete_file_ids = [delete_file_ids]
            submission.files.filter(id__in=delete_file_ids).delete()

        return Response(SubmissionSerializer(submission, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def allow_resubmission(request, submission_id):
    """Allow a student to resubmit (instructor only). Archives current and resets to draft."""
    submission = get_object_or_404(
        Submission.objects.select_related('assignment__unit__course'),
        id=submission_id
    )

    # Only instructor can allow resubmission
    require_course_instructor(
        request.user, submission.assignment.course,
        "Only the course instructor can allow resubmission."
    )

    # Archive the current submission before resetting
    grade_points = None
    grade_feedback = ''
    if hasattr(submission, 'grade'):
        grade_points = submission.grade.points
        grade_feedback = submission.grade.feedback or ''

    # Get file names for archiving
    files_info = list(submission.files.values_list('filename', flat=True))

    if submission.submitted_at:  # Only archive if it was actually submitted
        SubmissionHistory.objects.create(
            submission=submission,
            content=submission.content,
            files_info=files_info,
            submitted_at=submission.submitted_at,
            grade_points=grade_points,
            grade_feedback=grade_feedback
        )

    # Reset to draft status
    submission.status = 'draft'
    submission.submitted_at = None
    submission.save()

    # Delete the grade if exists
    if hasattr(submission, 'grade'):
        submission.grade.delete()

    # Notify student that resubmission is allowed
    notify_student_resubmission_allowed(submission)

    return Response(SubmissionSerializer(submission, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_assignment(request, assignment_id):
    """Submit an assignment (change status from draft to submitted)."""
    assignment = get_object_or_404(
        Assignment.objects.select_related('unit__course'),
        id=assignment_id
    )
    course = assignment.unit.course
    require_enrollment(request.user, course, "You must be enrolled in this course.")

    # Check if assignment is closed for submissions
    if assignment.is_closed:
        return Response(
            {
                'error': 'This assignment is closed for submissions.',
                'available_until': assignment.available_until.isoformat() if assignment.available_until else None
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        submission = Submission.objects.get(
            assignment=assignment,
            student=request.user
        )
    except Submission.DoesNotExist:
        return Response(
            {'error': 'No submission found. Save a draft first.'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = SubmissionSubmitSerializer(instance=submission, data={})
    if serializer.is_valid():
        submission.status = 'submitted'
        submission.submitted_at = timezone.now()
        submission.save()

        # Calculate and apply late penalty
        late_penalty = calculate_late_penalty(submission, assignment)
        if late_penalty > 0:
            submission.late_penalty_applied = late_penalty
            submission.save()

        return Response(SubmissionSerializer(submission).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AssignmentSubmissionsView(generics.ListAPIView):
    """List all submissions for an assignment (instructor only)."""
    serializer_class = SubmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        assignment = get_object_or_404(
            Assignment.objects.select_related('unit__course'),
            id=self.kwargs['assignment_id']
        )

        require_course_instructor(
            self.request.user, assignment.course,
            "Only the course instructor can view submissions."
        )

        return Submission.objects.filter(
            assignment=assignment,
            status__in=['submitted', 'graded']
        ).select_related('student', 'grade')


class GradeSubmissionView(generics.CreateAPIView, generics.UpdateAPIView):
    """Grade a submission (instructor only)."""
    serializer_class = GradeSubmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_submission(self):
        submission = get_object_or_404(
            Submission.objects.select_related('assignment__unit__course'),
            id=self.kwargs['submission_id']
        )

        require_course_instructor(
            self.request.user, submission.assignment.course,
            "Only the course instructor can grade submissions."
        )

        if submission.status == 'draft':
            raise ValidationError("Cannot grade a draft submission.")

        return submission

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['submission'] = self.get_submission()
        return context

    def create(self, request, *args, **kwargs):
        submission = self.get_submission()

        # Check if grade already exists
        if hasattr(submission, 'grade'):
            return self.update(request, *args, **kwargs)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        grade = Grade.objects.create(
            submission=submission,
            grader=request.user,
            **serializer.validated_data
        )
        submission.status = 'graded'
        submission.save()

        # Send grade notification email
        from core.email import notify_student_of_grade
        notify_student_of_grade(submission, grade, is_update=False)

        return Response(
            SubmissionSerializer(submission).data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        submission = self.get_submission()

        if not hasattr(submission, 'grade'):
            return self.create(request, *args, **kwargs)

        grade = submission.grade
        original_points = grade.points  # Track for change detection

        serializer = self.get_serializer(grade, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(grader=request.user)

        # Send grade notification email only if points changed
        if grade.points != original_points:
            from core.email import notify_student_of_grade
            notify_student_of_grade(submission, grade, is_update=True)

        return Response(SubmissionSerializer(submission).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quick_grade(request, assignment_id, student_id):
    """
    Quick grade endpoint for gradebook inline editing.
    Creates submission and grade if they don't exist.
    """
    from courses.models import Enrollment, Course

    assignment = get_object_or_404(
        Assignment.objects.select_related('unit__course'),
        id=assignment_id
    )
    course = assignment.unit.course

    # Only instructor can use quick grade
    require_course_instructor(
        request.user, course,
        "Only the course instructor can grade."
    )

    # Verify student is enrolled
    enrollment = Enrollment.objects.filter(
        user_id=student_id,
        course=course,
        is_active=True
    ).first()

    if not enrollment:
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
        points = int(points)
    except (ValueError, TypeError):
        return Response(
            {'error': 'Points must be a number.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if points < 0 or points > assignment.max_points:
        return Response(
            {'error': f'Points must be between 0 and {assignment.max_points}.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get or create submission
    submission, created = Submission.objects.get_or_create(
        assignment=assignment,
        student_id=student_id,
        defaults={
            'status': 'submitted',
            'submitted_at': timezone.now(),
            'content': '[Graded directly by instructor]',
        }
    )

    # Update submission status if it was draft
    if submission.status == 'draft':
        submission.status = 'submitted'
        submission.submitted_at = timezone.now()
        submission.save()

    # Create or update grade
    is_new_grade = not (hasattr(submission, 'grade') and submission.grade)
    if hasattr(submission, 'grade') and submission.grade:
        submission.grade.points = points
        submission.grade.grader = request.user
        submission.grade.save()
        grade = submission.grade
    else:
        grade = Grade.objects.create(
            submission=submission,
            grader=request.user,
            points=points,
            feedback='',
        )

    submission.status = 'graded'
    submission.save()

    # Send grade notification email for new grades only
    if is_new_grade:
        from core.email import notify_student_of_grade
        notify_student_of_grade(submission, grade, is_update=False)

    return Response({
        'success': True,
        'assignment_id': assignment_id,
        'student_id': student_id,
        'points': points,
        'max_points': assignment.max_points,
    })
