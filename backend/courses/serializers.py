from django.core.validators import MaxLengthValidator
from rest_framework import serializers
from .models import (
    Course, Unit, Lesson, Enrollment, LessonProgress, Announcement, CourseGradingConfig,
    LessonQuestion, LessonQuestionChoice, LessonQuestionAnswer, LessonQuizAttempt,
    LessonAttachment, LessonSection, InstructorReminder, CourseInvite
)
from accounts.serializers import UserSerializer
from .video import extract_youtube_video_id


# A full YouTube share URL is accepted as input; validate() extracts the
# 11-char ID that is actually stored, so the model columns (50/100) never see
# the raw URL. Bounded so oversized junk is still rejected before extraction.
VIDEO_ID_INPUT_MAX_LENGTH = 255


class VideoFieldsValidationMixin:
    """Normalize/validate video_id against video_type on lessons and sections.

    On partial updates, fields absent from the payload fall back to the
    instance so a title-only PATCH can't bypass validation.
    """

    def get_fields(self):
        fields = super().get_fields()
        video_id = fields.get('video_id')
        if video_id is not None:
            # The model-derived field caps length at 50/100, and DRF runs that
            # MaxLengthValidator in to_internal_value() — before validate().
            # Without this, a valid long share URL (watch?v=ID&si=...) is
            # rejected for length before the extractor ever normalizes it.
            video_id.max_length = VIDEO_ID_INPUT_MAX_LENGTH
            video_id.validators = [
                v for v in video_id.validators
                if not isinstance(v, MaxLengthValidator)
            ]
            video_id.validators.append(
                MaxLengthValidator(VIDEO_ID_INPUT_MAX_LENGTH))
        return fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        video_type = attrs.get(
            'video_type', getattr(self.instance, 'video_type', 'none'))
        video_id = attrs.get(
            'video_id', getattr(self.instance, 'video_id', ''))

        if video_type == 'youtube':
            extracted = extract_youtube_video_id(video_id)
            if extracted is None:
                raise serializers.ValidationError({
                    'video_id': 'Could not extract a YouTube video ID from this value.'
                })
            attrs['video_id'] = extracted
        else:
            attrs['video_id'] = ''
        return attrs


class LessonQuizScopeMixin:
    """Constrain `required_quiz` to a quiz in the lesson's own course.

    `required_quiz` is a bare PrimaryKeyRelatedField over all quizzes, so without
    this an instructor could (via the API) gate a lesson on a quiz from another
    course. On update the course comes from the lesson instance; on create it
    comes from the unit id in the URL (UnitLessonsView).
    """

    def _resolve_lesson_course(self):
        if self.instance is not None:
            return self.instance.unit.course
        view = self.context.get('view')
        unit_id = getattr(view, 'kwargs', {}).get('unit_id') if view else None
        if unit_id:
            unit = Unit.objects.filter(pk=unit_id).select_related('course').first()
            return unit.course if unit else None
        return None

    def validate_required_quiz(self, value):
        if value is None:
            return value
        course = self._resolve_lesson_course()
        if course is not None and value.unit.course_id != course.id:
            raise serializers.ValidationError(
                'The required quiz must belong to the same course as the lesson.'
            )
        return value


class LessonAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for lesson attachments."""
    url = serializers.SerializerMethodField()

    class Meta:
        model = LessonAttachment
        fields = ['id', 'filename', 'file_type', 'file_size', 'url', 'uploaded_at']

    def get_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else None


class LessonSectionSerializer(VideoFieldsValidationMixin, serializers.ModelSerializer):
    """Serializer for lesson sections."""

    class Meta:
        model = LessonSection
        fields = ['id', 'title', 'content', 'video_type', 'video_id', 'order', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class LessonSectionCreateSerializer(VideoFieldsValidationMixin, serializers.ModelSerializer):
    """Serializer for creating/updating lesson sections (lesson set in view)."""

    class Meta:
        model = LessonSection
        fields = ['id', 'title', 'content', 'video_type', 'video_id', 'order']
        read_only_fields = ['id']


class LessonSectionBulkCreateSerializer(serializers.Serializer):
    """Wrapper for atomically creating many sections at once (paste-to-split).

    Incoming per-child ``order`` is ignored — the view assigns sequential order
    appended after any existing sections. Bounded to 50 sections per request.
    """
    sections = LessonSectionCreateSerializer(many=True, min_length=1, max_length=50)


class RequiredQuizSerializer(serializers.Serializer):
    """Lightweight serializer for required quiz info."""
    id = serializers.IntegerField()
    title = serializers.CharField()
    passing_score = serializers.IntegerField()


class LessonSerializer(LessonQuizScopeMixin, VideoFieldsValidationMixin, serializers.ModelSerializer):
    """Serializer for Lesson model."""
    required_quiz_info = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    attachments = LessonAttachmentSerializer(many=True, read_only=True)
    sections = LessonSectionSerializer(many=True, read_only=True)
    section_count = serializers.SerializerMethodField()
    has_video = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'unit', 'title', 'content', 'order',
            'video_type', 'video_id', 'required_quiz', 'required_quiz_info',
            'max_quiz_attempts', 'question_count', 'attachments',
            'sections', 'section_count', 'has_video',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_question_count(self, obj):
        return obj.questions.count()

    def get_section_count(self, obj):
        return obj.sections.count()

    def get_has_video(self, obj):
        # Phase 53: video lives in sections. True if any section has a YouTube video.
        return obj.sections.filter(video_type='youtube').exclude(video_id='').exists()

    def get_required_quiz_info(self, obj):
        if obj.required_quiz:
            return {
                'id': obj.required_quiz.id,
                'title': obj.required_quiz.title,
                'passing_score': obj.required_quiz.passing_score,
            }
        return None


class LessonCreateSerializer(LessonQuizScopeMixin, VideoFieldsValidationMixin, serializers.ModelSerializer):
    """Serializer for creating lessons (unit set in view)."""

    class Meta:
        model = Lesson
        fields = ['id', 'title', 'content', 'order', 'video_type', 'video_id', 'required_quiz', 'max_quiz_attempts']
        read_only_fields = ['id']


class LessonListSerializer(serializers.ModelSerializer):
    """Serializer for lesson lists (includes content and video_id for editing)."""
    required_quiz_info = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    attachment_count = serializers.SerializerMethodField()
    section_count = serializers.SerializerMethodField()
    has_video = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'order', 'video_type', 'video_id', 'content',
            'required_quiz', 'required_quiz_info', 'max_quiz_attempts', 'question_count',
            'attachment_count', 'section_count', 'has_video'
        ]

    def get_attachment_count(self, obj):
        return obj.attachments.count()

    def get_section_count(self, obj):
        return obj.sections.count()

    def get_has_video(self, obj):
        # Phase 53: video lives in sections, not on the lesson. True if any
        # section has a playable YouTube video.
        return obj.sections.filter(video_type='youtube').exclude(video_id='').exists()

    def get_required_quiz_info(self, obj):
        if obj.required_quiz:
            return {
                'id': obj.required_quiz.id,
                'title': obj.required_quiz.title,
                'passing_score': obj.required_quiz.passing_score,
            }
        return None

    def get_question_count(self, obj):
        return obj.questions.count()


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
    required_quiz_passed = serializers.SerializerMethodField()
    required_quiz_info = serializers.SerializerMethodField()
    lesson_questions_status = serializers.SerializerMethodField()

    class Meta:
        model = LessonProgress
        fields = [
            'id', 'lesson', 'completed', 'completed_at', 'video_position',
            'current_section', 'required_quiz_passed', 'required_quiz_info',
            'lesson_questions_status', 'updated_at'
        ]
        read_only_fields = ['id', 'completed_at', 'updated_at']

    def get_required_quiz_passed(self, obj):
        """Check if user has passed the required quiz for this lesson."""
        lesson = obj.lesson
        if not lesson.required_quiz:
            return None  # No quiz required

        from quizzes.models import QuizAttempt
        return QuizAttempt.objects.filter(
            quiz=lesson.required_quiz,
            student=obj.user,
            passed=True
        ).exists()

    def get_required_quiz_info(self, obj):
        """Get required quiz info if exists."""
        lesson = obj.lesson
        if lesson.required_quiz:
            return {
                'id': lesson.required_quiz.id,
                'title': lesson.required_quiz.title,
                'passing_score': lesson.required_quiz.passing_score,
            }
        return None

    def get_lesson_questions_status(self, obj):
        """Get status of lesson comprehension questions."""
        lesson = obj.lesson
        total_questions = lesson.questions.count()

        if total_questions == 0:
            return None  # No questions for this lesson

        # Get user's answers
        answers = LessonQuestionAnswer.objects.filter(
            user=obj.user,
            question__lesson=lesson
        )
        answered_count = answers.count()
        correct_count = answers.filter(is_correct=True).count()
        all_correct = correct_count == total_questions

        return {
            'total_questions': total_questions,
            'answered_questions': answered_count,
            'correct_answers': correct_count,
            'all_correct': all_correct,
            'can_complete_lesson': all_correct
        }


class LessonProgressUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating lesson progress."""

    class Meta:
        model = LessonProgress
        fields = ['completed', 'video_position', 'current_section']

    def validate_completed(self, value):
        """Check if required quiz and lesson questions are passed before allowing completion."""
        if value:  # Only check when marking as complete
            lesson = self.instance.lesson
            user = self.instance.user

            # Check lesson comprehension questions first
            total_questions = lesson.questions.count()
            if total_questions > 0:
                # Check if user has a passed quiz attempt
                has_passed = LessonQuizAttempt.objects.filter(
                    user=user,
                    lesson=lesson,
                    passed=True
                ).exists()

                if not has_passed:
                    raise serializers.ValidationError(
                        "You must pass the comprehension quiz before completing this lesson."
                    )

            # Also check standalone required quiz if set
            if lesson.required_quiz:
                from quizzes.models import QuizAttempt
                has_passed = QuizAttempt.objects.filter(
                    quiz=lesson.required_quiz,
                    student=user,
                    passed=True
                ).exists()

                if not has_passed:
                    raise serializers.ValidationError(
                        f"You must pass the quiz '{lesson.required_quiz.title}' before completing this lesson."
                    )
        return value

    def update(self, instance, validated_data):
        from django.utils import timezone

        # Flag the not-completed -> completed transition so the view can award
        # gamification XP. This is the single place a lesson "becomes done".
        just_completed = bool(validated_data.get('completed')) and not instance.completed

        # Set completed_at when marking as complete
        if just_completed:
            validated_data['completed_at'] = timezone.now()

        updated = super().update(instance, validated_data)
        updated._just_completed = just_completed
        return updated


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
        fields = ['quizzes_weight', 'participation_weight']

    def validate(self, data):
        # Get existing values for fields not being updated
        instance = self.instance
        quizzes = data.get('quizzes_weight', instance.quizzes_weight if instance else 50)
        participation = data.get('participation_weight', instance.participation_weight if instance else 50)

        total = float(quizzes) + float(participation)
        if total != 100:
            raise serializers.ValidationError(f'Weights must sum to 100%. Current total: {total}%')
        return data


# ============================================
# Lesson Questions (Mini Comprehension Quizzes)
# ============================================

class LessonQuestionChoiceSerializer(serializers.ModelSerializer):
    """Serializer for lesson question choices."""

    class Meta:
        model = LessonQuestionChoice
        fields = ['id', 'text', 'is_correct', 'order']


class LessonQuestionChoiceStudentSerializer(serializers.ModelSerializer):
    """Serializer for students - hides is_correct field."""

    class Meta:
        model = LessonQuestionChoice
        fields = ['id', 'text', 'order']


class LessonQuestionSerializer(serializers.ModelSerializer):
    """Serializer for lesson questions (instructor view with answers)."""
    choices = LessonQuestionChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = LessonQuestion
        fields = ['id', 'lesson', 'text', 'order', 'choices', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class LessonQuestionStudentSerializer(serializers.ModelSerializer):
    """Serializer for students - hides correct answer info."""
    choices = LessonQuestionChoiceStudentSerializer(many=True, read_only=True)

    class Meta:
        model = LessonQuestion
        fields = ['id', 'text', 'order', 'choices']


class LessonQuestionCreateSerializer(serializers.Serializer):
    """Serializer for creating/updating a lesson question with choices."""
    text = serializers.CharField()
    order = serializers.IntegerField(default=0)
    choices = serializers.ListField(
        child=serializers.DictField(),
        min_length=2,
        max_length=6,
        help_text='List of choices with text, is_correct, and order'
    )

    def validate_choices(self, value):
        # Ensure exactly one choice is marked correct
        correct_count = sum(1 for choice in value if choice.get('is_correct', False))
        if correct_count == 0:
            raise serializers.ValidationError("Exactly one choice must be marked as correct.")
        if correct_count > 1:
            raise serializers.ValidationError("Only one choice can be marked as correct.")

        # Ensure each choice has text
        for i, choice in enumerate(value):
            if not choice.get('text', '').strip():
                raise serializers.ValidationError(f"Choice {i+1} must have text.")

        return value


class LessonQuestionAnswerSerializer(serializers.ModelSerializer):
    """Serializer for student answers to lesson questions."""
    question_text = serializers.CharField(source='question.text', read_only=True)
    selected_choice_text = serializers.CharField(source='selected_choice.text', read_only=True)

    class Meta:
        model = LessonQuestionAnswer
        fields = ['id', 'question', 'question_text', 'selected_choice', 'selected_choice_text', 'is_correct', 'answered_at']
        read_only_fields = ['id', 'is_correct', 'answered_at']


class AnswerQuestionSerializer(serializers.Serializer):
    """Serializer for answering a lesson question."""
    question_id = serializers.IntegerField()
    choice_id = serializers.IntegerField()

    def validate(self, data):
        question_id = data['question_id']
        choice_id = data['choice_id']

        try:
            question = LessonQuestion.objects.get(id=question_id)
        except LessonQuestion.DoesNotExist:
            raise serializers.ValidationError({'question_id': 'Question not found.'})

        try:
            choice = LessonQuestionChoice.objects.get(id=choice_id, question=question)
        except LessonQuestionChoice.DoesNotExist:
            raise serializers.ValidationError({'choice_id': 'Choice not found for this question.'})

        data['question'] = question
        data['choice'] = choice
        return data


class LessonQuestionsStatusSerializer(serializers.Serializer):
    """Serializer for lesson questions completion status."""
    total_questions = serializers.IntegerField()
    answered_questions = serializers.IntegerField()
    correct_answers = serializers.IntegerField()
    all_correct = serializers.BooleanField()
    can_complete_lesson = serializers.BooleanField()



class InstructorReminderSerializer(serializers.ModelSerializer):
    """Serializer for instructor calendar reminders."""
    course_code = serializers.SerializerMethodField()
    course_title = serializers.SerializerMethodField()

    class Meta:
        model = InstructorReminder
        fields = [
            "id", "course", "course_code", "course_title", "title",
            "description", "date", "time", "end_time", "color", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_course_code(self, obj):
        return obj.course.code if obj.course else None

    def get_course_title(self, obj):
        return obj.course.title if obj.course else None


class InstructorReminderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating reminders (instructor set in view)."""

    class Meta:
        model = InstructorReminder
        fields = ["id", "course", "title", "description", "date", "time", "end_time", "color"]
        read_only_fields = ["id"]

    def validate_course(self, value):
        """Ensure instructor owns the course if specified."""
        if value:
            request = self.context.get("request")
            if request and value.instructor != request.user:
                raise serializers.ValidationError("You can only add reminders to your own courses.")
        return value

    def validate(self, data):
        """Validate that end_time is after time if both are provided."""
        time = data.get('time') or (self.instance.time if self.instance else None)
        end_time = data.get('end_time')

        if time and end_time and end_time <= time:
            raise serializers.ValidationError({
                'end_time': 'End time must be after start time.'
            })

        # If no start time, clear end time
        if not time and end_time:
            data['end_time'] = None

        return data



# ==================== Course Map (Phase 35) ====================
# Read-only serializers for the Duolingo-style course map. Node states are
# computed in the view (course_map); these only shape the payload.

class CourseMapLessonNodeSerializer(serializers.Serializer):
    """A lesson node on the course map."""
    node_type = serializers.CharField()
    id = serializers.IntegerField()
    title = serializers.CharField()
    order = serializers.IntegerField()
    state = serializers.ChoiceField(
        choices=['completed', 'current', 'unlocked', 'locked']
    )


class CourseMapQuizNodeSerializer(CourseMapLessonNodeSerializer):
    """A quiz ("boss") node — additionally carries scores."""
    passing_score = serializers.IntegerField()
    best_score = serializers.FloatField(allow_null=True)


class CourseMapUnitSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    order = serializers.IntegerField()
    nodes = serializers.SerializerMethodField()

    def get_nodes(self, obj):
        return [
            (CourseMapQuizNodeSerializer if node['node_type'] == 'quiz'
             else CourseMapLessonNodeSerializer)(node).data
            for node in obj['nodes']
        ]


class CourseMapSerializer(serializers.Serializer):
    course_code = serializers.CharField()
    course_title = serializers.CharField()
    total_nodes = serializers.IntegerField()
    completed_nodes = serializers.IntegerField()
    # Composite "<node_type>-<id>" key (lesson and quiz ids can collide).
    current_node_id = serializers.CharField(allow_null=True)
    units = CourseMapUnitSerializer(many=True)


class CourseInviteSerializer(serializers.ModelSerializer):
    status = serializers.ReadOnlyField()

    class Meta:
        model = CourseInvite
        fields = ['id', 'email', 'status', 'created_at', 'expires_at']
