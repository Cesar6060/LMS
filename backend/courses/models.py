import secrets
from django.db import models
from django.conf import settings


def generate_enrollment_code():
    """Generate an 8-character alphanumeric enrollment code."""
    return secrets.token_urlsafe(6)[:8].upper()


class Course(models.Model):
    """
    A course created by an instructor.
    Contains units which contain lessons.
    """
    code = models.CharField(
        max_length=10,
        unique=True,
        help_text='Unique course code, e.g., "VGD101"'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='courses_teaching'
    )
    enrollment_code = models.CharField(
        max_length=8,
        unique=True,
        default=generate_enrollment_code,
        help_text='Code students use to enroll'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'courses_course'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code}: {self.title}"

    def regenerate_enrollment_code(self):
        """Generate a new enrollment code."""
        self.enrollment_code = generate_enrollment_code()
        self.save(update_fields=['enrollment_code'])
        return self.enrollment_code


class Unit(models.Model):
    """
    A unit/module within a course.
    Contains lessons and assignments.
    """
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='units'
    )
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'courses_unit'
        ordering = ['order']
        unique_together = ['course', 'order']

    def __str__(self):
        return f"{self.course.code} - Unit {self.order}: {self.title}"


class Lesson(models.Model):
    """
    A lesson within a unit.
    Contains markdown content and optional video.
    """
    VIDEO_TYPE_CHOICES = [
        ('none', 'No Video'),
        ('youtube', 'YouTube'),
        ('vimeo', 'Vimeo'),
    ]

    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name='lessons'
    )
    title = models.CharField(max_length=200)
    content = models.TextField(
        blank=True,
        help_text='Lesson content in Markdown format'
    )
    order = models.PositiveIntegerField(default=0)
    video_type = models.CharField(
        max_length=10,
        choices=VIDEO_TYPE_CHOICES,
        default='none'
    )
    video_id = models.CharField(
        max_length=50,
        blank=True,
        help_text='YouTube or Vimeo video ID'
    )
    required_quiz = models.ForeignKey(
        'quizzes.Quiz',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='required_for_lessons',
        help_text='Quiz that must be passed to complete this lesson'
    )
    max_quiz_attempts = models.PositiveIntegerField(
        default=0,
        help_text='Maximum attempts for comprehension quiz (0 = unlimited)'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'courses_lesson'
        ordering = ['order']
        unique_together = ['unit', 'order']

    def __str__(self):
        return f"{self.unit.course.code} - {self.title}"


class Enrollment(models.Model):
    """
    Represents a student's enrollment in a course.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Last time the student accessed the course'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='False means student was removed (soft delete)'
    )

    class Meta:
        db_table = 'courses_enrollment'
        unique_together = ['user', 'course']
        ordering = ['-enrolled_at']

    def __str__(self):
        return f"{self.user.email} enrolled in {self.course.code}"

    def update_activity(self):
        """Update last activity timestamp."""
        from django.utils import timezone
        self.last_activity_at = timezone.now()
        self.save(update_fields=['last_activity_at'])


class Announcement(models.Model):
    """
    Course-wide announcements from instructors.
    """
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='announcements'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='announcements_created'
    )
    title = models.CharField(max_length=200)
    content = models.TextField(help_text='Announcement content in Markdown format')
    is_pinned = models.BooleanField(default=False)
    send_email = models.BooleanField(
        default=True,
        help_text='Send email notification to enrolled students'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'courses_announcement'
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f"{self.course.code}: {self.title}"


class LessonProgress(models.Model):
    """
    Tracks a user's progress on a specific lesson.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lesson_progress'
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='progress'
    )
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    video_position = models.PositiveIntegerField(
        default=0,
        help_text='Video position in seconds'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'courses_lessonprogress'
        unique_together = ['user', 'lesson']
        verbose_name_plural = 'Lesson progress'

    def __str__(self):
        status = "completed" if self.completed else f"position {self.video_position}s"
        return f"{self.user.email} - {self.lesson.title}: {status}"


class CourseGradingConfig(models.Model):
    """Grading configuration for a course with category weights."""
    course = models.OneToOneField(
        'Course',
        on_delete=models.CASCADE,
        related_name='grading_config'
    )
    assignments_weight = models.DecimalField(
        max_digits=5, decimal_places=2, default=50,
        help_text='Weight percentage for assignments (0-100)'
    )
    quizzes_weight = models.DecimalField(
        max_digits=5, decimal_places=2, default=50,
        help_text='Weight percentage for quizzes (0-100)'
    )
    participation_weight = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Weight percentage for participation/lesson completion (0-100)'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'courses_gradingconfig'
        verbose_name = 'Grading Configuration'

    def __str__(self):
        return f"Grading config for {self.course.code}"

    def clean(self):
        from django.core.exceptions import ValidationError
        total = (self.assignments_weight or 0) + (self.quizzes_weight or 0) + (self.participation_weight or 0)
        if total != 100:
            raise ValidationError(f'Weights must sum to 100%. Current total: {total}%')


class LessonQuestion(models.Model):
    """
    A comprehension check question embedded in a lesson.
    These are mini-quizzes to verify students read the content.
    """
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    text = models.TextField(help_text='The question text')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'courses_lessonquestion'
        ordering = ['order']

    def __str__(self):
        return f"{self.lesson.title} - Q{self.order}: {self.text[:50]}"

    def clean(self):
        """Validate that exactly one choice is marked as correct."""
        from django.core.exceptions import ValidationError
        if self.pk:  # Only validate if question already exists (has choices)
            correct_count = self.choices.filter(is_correct=True).count()
            if correct_count == 0:
                raise ValidationError('Question must have at least one correct answer.')
            if correct_count > 1:
                raise ValidationError('Question can only have one correct answer.')


class LessonQuestionChoice(models.Model):
    """
    A choice/answer option for a lesson question.
    """
    question = models.ForeignKey(
        LessonQuestion,
        on_delete=models.CASCADE,
        related_name='choices'
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'courses_lessonquestionchoice'
        ordering = ['order']

    def __str__(self):
        correct_marker = " ✓" if self.is_correct else ""
        return f"{self.text}{correct_marker}"


class LessonQuestionAnswer(models.Model):
    """
    Tracks a student's answer to a lesson question.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lesson_question_answers'
    )
    question = models.ForeignKey(
        LessonQuestion,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    selected_choice = models.ForeignKey(
        LessonQuestionChoice,
        on_delete=models.SET_NULL,
        null=True,
        related_name='selections',
        help_text='Set to NULL if choice is deleted (e.g., when question is edited)'
    )
    is_correct = models.BooleanField()
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'courses_lessonquestionanswer'
        unique_together = ['user', 'question']

    def __str__(self):
        status = "correct" if self.is_correct else "incorrect"
        return f"{self.user.email} - {self.question.text[:30]}: {status}"

    def save(self, *args, **kwargs):
        # Automatically set is_correct based on the selected choice
        if self.selected_choice:
            self.is_correct = self.selected_choice.is_correct
        else:
            self.is_correct = False
        super().save(*args, **kwargs)


class LessonQuizAttempt(models.Model):
    """
    Tracks a student's attempt at a lesson's comprehension quiz.
    Each attempt represents submitting answers for all questions.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lesson_quiz_attempts'
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='quiz_attempts'
    )
    attempt_number = models.PositiveIntegerField(default=1)
    score = models.PositiveIntegerField(
        help_text='Number of correct answers'
    )
    total_questions = models.PositiveIntegerField()
    passed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'courses_lessonquizattempt'
        unique_together = ['user', 'lesson', 'attempt_number']
        ordering = ['-attempt_number']

    def __str__(self):
        return f"{self.user.email} - {self.lesson.title} - Attempt {self.attempt_number}: {self.score}/{self.total_questions}"

    @property
    def percentage(self):
        if self.total_questions == 0:
            return 0
        return round((self.score / self.total_questions) * 100)
