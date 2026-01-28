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
