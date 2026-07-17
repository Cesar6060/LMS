from rest_framework import serializers
from django.utils import timezone
from .models import Assignment, Submission, SubmissionFile, SubmissionHistory, Grade


class GradeSerializer(serializers.ModelSerializer):
    grader_name = serializers.SerializerMethodField()
    percentage = serializers.ReadOnlyField()

    class Meta:
        model = Grade
        fields = [
            'id', 'points', 'feedback', 'grader', 'grader_name',
            'percentage', 'graded_at', 'updated_at'
        ]
        read_only_fields = ['grader', 'grader_name', 'graded_at']

    def get_grader_name(self, obj):
        if obj.grader:
            return f"{obj.grader.first_name} {obj.grader.last_name}"
        return None


class SubmissionFileSerializer(serializers.ModelSerializer):
    """Serializer for submission files."""
    url = serializers.SerializerMethodField()

    class Meta:
        model = SubmissionFile
        fields = ['id', 'filename', 'url', 'uploaded_at']

    def get_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else None


class SubmissionHistorySerializer(serializers.ModelSerializer):
    """Serializer for submission history (past submissions)."""

    class Meta:
        model = SubmissionHistory
        fields = ['id', 'content', 'files_info', 'submitted_at', 'grade_points', 'grade_feedback', 'archived_at']


class SubmissionSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_email = serializers.SerializerMethodField()
    is_late = serializers.ReadOnlyField()
    grade = GradeSerializer(read_only=True)
    files = SubmissionFileSerializer(many=True, read_only=True)
    history = SubmissionHistorySerializer(many=True, read_only=True)
    final_grade = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            'id', 'assignment', 'student', 'student_name', 'student_email',
            'content', 'file', 'files', 'status', 'is_late',
            'submitted_at', 'created_at', 'updated_at', 'grade', 'history',
            'late_penalty_applied', 'final_grade'
        ]
        read_only_fields = ['student', 'submitted_at', 'status', 'late_penalty_applied']

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"

    def get_student_email(self, obj):
        return obj.student.email

    def get_final_grade(self, obj):
        """Calculate final grade (earned points - late penalty)."""
        if hasattr(obj, 'grade') and obj.grade:
            from decimal import Decimal
            earned = Decimal(str(obj.grade.points))
            penalty = Decimal(str(obj.late_penalty_applied or 0))
            final = max(earned - penalty, Decimal('0'))
            return float(final)
        return None


class SubmissionCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating submissions by students."""

    class Meta:
        model = Submission
        fields = ['id', 'content']

    def update(self, instance, validated_data):
        # Don't allow updates to submitted/graded submissions
        if instance.status in ['submitted', 'graded']:
            raise serializers.ValidationError(
                "Cannot modify a submission that has already been submitted."
            )
        return super().update(instance, validated_data)


class SubmissionSubmitSerializer(serializers.Serializer):
    """Serializer for the submit action."""

    def validate(self, attrs):
        submission = self.instance
        has_files = submission.files.exists()
        if not submission.content and not submission.file and not has_files:
            raise serializers.ValidationError(
                "Submission must have content or at least one file."
            )
        if submission.status in ['submitted', 'graded']:
            raise serializers.ValidationError(
                "This submission has already been submitted."
            )

        assignment = submission.assignment

        # Check if assignment is closed (available_until has passed)
        if assignment.is_closed:
            raise serializers.ValidationError(
                "This assignment is closed for submissions."
            )

        # Check allow_late for due date
        if assignment.due_date and timezone.now() > assignment.due_date:
            if not assignment.allow_late:
                raise serializers.ValidationError(
                    "This assignment no longer accepts submissions."
                )
        return attrs


class AssignmentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing assignments."""
    course_code = serializers.CharField(source='unit.course.code', read_only=True)
    unit_title = serializers.CharField(source='unit.title', read_only=True)
    submission_status = serializers.SerializerMethodField()
    is_available = serializers.ReadOnlyField()
    is_closed = serializers.ReadOnlyField()

    class Meta:
        model = Assignment
        fields = [
            'id', 'title', 'max_points', 'due_date', 'order',
            'unit', 'course_code', 'unit_title', 'submission_status',
            'available_from', 'available_until', 'is_available', 'is_closed'
        ]

    def get_submission_status(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        try:
            submission = obj.submissions.get(student=request.user)
            grade = None
            if hasattr(submission, 'grade'):
                # Apply late penalty to get final grade
                raw_points = submission.grade.points
                late_penalty = float(submission.late_penalty_applied or 0)
                grade = max(0, raw_points - late_penalty)
            return {
                'status': submission.status,
                'grade': grade
            }
        except Submission.DoesNotExist:
            return None


class AssignmentDetailSerializer(serializers.ModelSerializer):
    """Full serializer for assignment details."""
    course_code = serializers.CharField(source='unit.course.code', read_only=True)
    unit_title = serializers.CharField(source='unit.title', read_only=True)
    my_submission = serializers.SerializerMethodField()
    submission_count = serializers.SerializerMethodField()
    graded_count = serializers.SerializerMethodField()
    is_instructor = serializers.SerializerMethodField()
    is_available = serializers.ReadOnlyField()
    is_closed = serializers.ReadOnlyField()

    class Meta:
        model = Assignment
        fields = [
            'id', 'title', 'description', 'max_points', 'due_date',
            'order', 'allow_late', 'course_code', 'unit_title',
            'my_submission', 'submission_count', 'graded_count',
            'is_instructor', 'created_at', 'updated_at',
            'available_from', 'available_until', 'is_available', 'is_closed',
            'late_penalty_percent', 'late_penalty_interval', 'max_late_penalty'
        ]

    def get_my_submission(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        try:
            submission = obj.submissions.get(student=request.user)
            return SubmissionSerializer(submission).data
        except Submission.DoesNotExist:
            return None

    def get_submission_count(self, obj):
        # Only instructors see this
        request = self.context.get('request')
        if request and request.user == obj.course.instructor:
            return obj.submissions.filter(status='submitted').count()
        return None

    def get_graded_count(self, obj):
        request = self.context.get('request')
        if request and request.user == obj.course.instructor:
            return obj.submissions.filter(status='graded').count()
        return None

    def get_is_instructor(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return request.user == obj.course.instructor
        return False


class EmptyStringToNullDateTimeField(serializers.DateTimeField):
    """DateTimeField that converts empty strings to None."""
    def to_internal_value(self, value):
        if value == '' or value is None:
            return None
        return super().to_internal_value(value)


class AssignmentCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for instructors creating/updating assignments."""
    due_date = EmptyStringToNullDateTimeField(required=False, allow_null=True)
    available_from = EmptyStringToNullDateTimeField(required=False, allow_null=True)
    available_until = EmptyStringToNullDateTimeField(required=False, allow_null=True)

    class Meta:
        model = Assignment
        fields = [
            'id', 'title', 'description', 'max_points',
            'due_date', 'order', 'allow_late',
            'available_from', 'available_until',
            'late_penalty_percent', 'late_penalty_interval', 'max_late_penalty'
        ]

    def validate_late_penalty_percent(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Late penalty percent must be non-negative.")
        if value is not None and value > 100:
            raise serializers.ValidationError("Late penalty percent cannot exceed 100.")
        return value

    def validate_max_late_penalty(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Max late penalty must be non-negative.")
        if value is not None and value > 100:
            raise serializers.ValidationError("Max late penalty cannot exceed 100.")
        return value

    def validate(self, data):
        # Validate available_from is before available_until
        available_from = data.get('available_from')
        available_until = data.get('available_until')
        due_date = data.get('due_date')

        if available_from and available_until and available_from >= available_until:
            raise serializers.ValidationError({
                'available_until': "Available until must be after available from."
            })

        if available_from and due_date and available_from >= due_date:
            raise serializers.ValidationError({
                'available_from': "Available from must be before due date."
            })

        return data


class GradeSubmissionSerializer(serializers.ModelSerializer):
    """Serializer for instructors grading submissions."""

    class Meta:
        model = Grade
        fields = ['points', 'feedback']

    def validate_points(self, value):
        submission = self.context.get('submission')
        if submission and value > submission.assignment.max_points:
            raise serializers.ValidationError(
                f"Points cannot exceed {submission.assignment.max_points}."
            )
        return value
