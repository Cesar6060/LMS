from rest_framework import serializers
from .models import Course, Unit, Lesson, Enrollment, LessonProgress, Announcement, CourseGradingConfig
from accounts.serializers import UserSerializer


class LessonSerializer(serializers.ModelSerializer):
    """Serializer for Lesson model."""

    class Meta:
        model = Lesson
        fields = [
            'id', 'unit', 'title', 'content', 'order',
            'video_type', 'video_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LessonCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating lessons (unit set in view)."""

    class Meta:
        model = Lesson
        fields = ['id', 'title', 'content', 'order', 'video_type', 'video_id']
        read_only_fields = ['id']


class LessonListSerializer(serializers.ModelSerializer):
    """Serializer for lesson lists (includes content and video_id for editing)."""

    class Meta:
        model = Lesson
        fields = ['id', 'title', 'order', 'video_type', 'video_id', 'content']


class UnitSerializer(serializers.ModelSerializer):
    """Serializer for Unit model with nested lessons."""
    lessons = LessonListSerializer(many=True, read_only=True)

    class Meta:
        model = Unit
        fields = ['id', 'course', 'title', 'order', 'lessons', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class UnitCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating units."""

    class Meta:
        model = Unit
        fields = ['id', 'title', 'order']
        read_only_fields = ['id']


class CourseSerializer(serializers.ModelSerializer):
    """Full course serializer with nested units."""
    instructor = UserSerializer(read_only=True)
    units = UnitSerializer(many=True, read_only=True)
    student_count = serializers.SerializerMethodField()
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'code', 'title', 'description', 'instructor',
            'enrollment_code', 'is_active', 'units', 'student_count',
            'is_enrolled', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'enrollment_code', 'created_at', 'updated_at']

    def get_student_count(self, obj):
        return obj.enrollments.filter(is_active=True).count()

    def get_is_enrolled(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.enrollments.filter(user=request.user, is_active=True).exists()
        return False

    def to_representation(self, instance):
        """Hide enrollment_code from non-instructors."""
        data = super().to_representation(instance)
        request = self.context.get('request')

        # Only show enrollment_code to the course instructor
        if request and request.user != instance.instructor:
            data.pop('enrollment_code', None)

        return data


class CourseListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for course lists."""
    instructor_name = serializers.SerializerMethodField()
    student_count = serializers.SerializerMethodField()
    unit_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'code', 'title', 'description', 'instructor_name',
            'is_active', 'student_count', 'unit_count', 'created_at'
        ]

    def get_instructor_name(self, obj):
        return obj.instructor.get_full_name() or obj.instructor.email

    def get_student_count(self, obj):
        return obj.enrollments.filter(is_active=True).count()

    def get_unit_count(self, obj):
        return obj.units.count()


class CourseCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating courses."""

    class Meta:
        model = Course
        fields = ['id', 'code', 'title', 'description', 'is_active']
        read_only_fields = ['id']

    def create(self, validated_data):
        validated_data['instructor'] = self.context['request'].user
        return super().create(validated_data)


class InstructorCourseSerializer(serializers.ModelSerializer):
    """Course serializer for instructors (includes enrollment_code)."""
    units = UnitSerializer(many=True, read_only=True)
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'code', 'title', 'description', 'enrollment_code',
            'is_active', 'units', 'student_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'enrollment_code', 'created_at', 'updated_at']

    def get_student_count(self, obj):
        return obj.enrollments.filter(is_active=True).count()


class EnrollmentCourseSerializer(serializers.ModelSerializer):
    """Course serializer for enrollment (includes instructor details)."""
    instructor = UserSerializer(read_only=True)

    class Meta:
        model = Course
        fields = ['id', 'code', 'title', 'description', 'instructor', 'is_active']


class EnrollmentSerializer(serializers.ModelSerializer):
    """Serializer for enrollment records."""
    course = EnrollmentCourseSerializer(read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = Enrollment
        fields = ['id', 'user', 'course', 'enrolled_at']
        read_only_fields = ['id', 'enrolled_at']


class EnrollmentCreateSerializer(serializers.Serializer):
    """Serializer for enrolling in a course."""
    enrollment_code = serializers.CharField(max_length=8)

    def validate_enrollment_code(self, value):
        try:
            course = Course.objects.get(enrollment_code=value.upper(), is_active=True)
        except Course.DoesNotExist:
            raise serializers.ValidationError("Invalid enrollment code.")

        user = self.context['request'].user

        # Check if already actively enrolled
        existing = Enrollment.objects.filter(user=user, course=course).first()
        if existing and existing.is_active:
            raise serializers.ValidationError("You are already enrolled in this course.")

        # Check if user is the instructor
        if course.instructor == user:
            raise serializers.ValidationError("Instructors cannot enroll in their own courses.")

        self.course = course
        self.existing_enrollment = existing  # May be None or inactive enrollment
        return value.upper()

    def create(self, validated_data):
        # Re-activate existing enrollment if previously removed
        if self.existing_enrollment:
            self.existing_enrollment.is_active = True
            self.existing_enrollment.save(update_fields=['is_active'])
            return self.existing_enrollment

        return Enrollment.objects.create(
            user=self.context['request'].user,
            course=self.course
        )


class LessonProgressSerializer(serializers.ModelSerializer):
    """Serializer for lesson progress."""

    class Meta:
        model = LessonProgress
        fields = ['id', 'lesson', 'completed', 'completed_at', 'video_position', 'updated_at']
        read_only_fields = ['id', 'completed_at', 'updated_at']


class LessonProgressUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating lesson progress."""

    class Meta:
        model = LessonProgress
        fields = ['completed', 'video_position']

    def update(self, instance, validated_data):
        from django.utils import timezone

        # Set completed_at when marking as complete
        if validated_data.get('completed') and not instance.completed:
            validated_data['completed_at'] = timezone.now()

        return super().update(instance, validated_data)


class AnnouncementSerializer(serializers.ModelSerializer):
    """Serializer for Announcement model."""
    author = UserSerializer(read_only=True)
    course_code = serializers.CharField(source='course.code', read_only=True)

    class Meta:
        model = Announcement
        fields = [
            'id', 'course', 'course_code', 'author', 'title', 'content',
            'is_pinned', 'send_email', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author', 'created_at', 'updated_at']


class AnnouncementListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for announcement lists."""
    author_name = serializers.SerializerMethodField()
    course_code = serializers.CharField(source='course.code', read_only=True)

    class Meta:
        model = Announcement
        fields = [
            'id', 'course_code', 'author_name', 'title', 'is_pinned', 'created_at'
        ]

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.email


class AnnouncementCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating announcements."""

    class Meta:
        model = Announcement
        fields = ['id', 'title', 'content', 'is_pinned', 'send_email']
        read_only_fields = ['id']


class StudentRosterSerializer(serializers.ModelSerializer):
    """Serializer for student roster (instructor view)."""
    student_id = serializers.IntegerField(source='user.id')
    email = serializers.EmailField(source='user.email')
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    progress_percentage = serializers.SerializerMethodField()
    is_inactive = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = [
            'id', 'student_id', 'email', 'first_name', 'last_name',
            'enrolled_at', 'last_activity_at', 'is_active',
            'progress_percentage', 'is_inactive'
        ]

    def get_progress_percentage(self, obj):
        """Calculate course progress for this student."""
        total_lessons = Lesson.objects.filter(unit__course=obj.course).count()
        if total_lessons == 0:
            return 0

        completed = LessonProgress.objects.filter(
            user=obj.user,
            lesson__unit__course=obj.course,
            completed=True
        ).count()

        return round((completed / total_lessons) * 100, 1)

    def get_is_inactive(self, obj):
        """Check if student hasn't been active in 7+ days."""
        from django.utils import timezone
        from datetime import timedelta

        if not obj.last_activity_at:
            # If never active, check enrolled date
            return (timezone.now() - obj.enrolled_at) > timedelta(days=7)

        return (timezone.now() - obj.last_activity_at) > timedelta(days=7)


class GradingConfigSerializer(serializers.ModelSerializer):
    """Serializer for CourseGradingConfig model."""

    class Meta:
        model = CourseGradingConfig
        fields = ['assignments_weight', 'quizzes_weight', 'participation_weight']

    def validate(self, data):
        # Get existing values for fields not being updated
        instance = self.instance
        assignments = data.get('assignments_weight', instance.assignments_weight if instance else 50)
        quizzes = data.get('quizzes_weight', instance.quizzes_weight if instance else 50)
        participation = data.get('participation_weight', instance.participation_weight if instance else 0)

        total = float(assignments) + float(quizzes) + float(participation)
        if total != 100:
            raise serializers.ValidationError(f'Weights must sum to 100%. Current total: {total}%')
        return data
