from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Assignment(models.Model):
    """
    An assignment within a course unit.
    Students submit work; instructors grade it.
    """
    LATE_PENALTY_INTERVAL_CHOICES = [
        ('day', 'Per Day'),
        ('hour', 'Per Hour'),
    ]

    unit = models.ForeignKey(
        'courses.Unit',
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(
        blank=True,
        help_text='Assignment instructions in Markdown format'
    )
    max_points = models.PositiveIntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(1000)]
    )
    due_date = models.DateTimeField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    allow_late = models.BooleanField(
        default=True,
        help_text='Allow submissions after due date'
    )

    # Availability window fields
    available_from = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Assignment becomes visible from this date'
    )
    available_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Submissions close after this date'
    )

    # Late penalty fields
    late_penalty_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Percentage deducted per day/hour late'
    )
    late_penalty_interval = models.CharField(
        max_length=10,
        choices=LATE_PENALTY_INTERVAL_CHOICES,
        default='day'
    )
    max_late_penalty = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Maximum percentage penalty cap'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assignments_assignment'
        ordering = ['order']

    def __str__(self):
        return f"{self.unit.course.code} - {self.title}"

    @property
    def course(self):
        return self.unit.course

    @property
    def is_available(self):
        """Check if the assignment is currently available (visible) to students."""
        from django.utils import timezone
        now = timezone.now()
        if self.available_from and now < self.available_from:
            return False
        return True

    @property
    def is_closed(self):
        """Check if the assignment is closed for submissions."""
        from django.utils import timezone
        if self.available_until and timezone.now() > self.available_until:
            return True
        return False


class Submission(models.Model):
    """
    A student's submission for an assignment.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('graded', 'Graded'),
    ]

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    content = models.TextField(
        blank=True,
        help_text='Submission text content'
    )
    file = models.FileField(
        upload_to='submissions/%Y/%m/',
        blank=True,
        null=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Late penalty tracking
    late_penalty_applied = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text='Points deducted for late submission'
    )

    class Meta:
        db_table = 'assignments_submission'
        unique_together = ['assignment', 'student']
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.student.email} - {self.assignment.title}"

    @property
    def is_late(self):
        if not self.assignment.due_date or not self.submitted_at:
            return False
        return self.submitted_at > self.assignment.due_date


class SubmissionHistory(models.Model):
    """
    Archive of past submissions when a student resubmits.
    """
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='history'
    )
    content = models.TextField(blank=True)
    files_info = models.JSONField(
        default=list,
        blank=True,
        help_text='JSON array of file names from the archived submission'
    )
    submitted_at = models.DateTimeField()
    grade_points = models.PositiveIntegerField(null=True, blank=True)
    grade_feedback = models.TextField(blank=True)
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'assignments_submissionhistory'
        ordering = ['-archived_at']

    def __str__(self):
        return f"History for {self.submission} at {self.archived_at}"


class SubmissionFile(models.Model):
    """
    A file attached to a submission. Max 3 files per submission.
    """
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='files'
    )
    file = models.FileField(upload_to='submissions/%Y/%m/')
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'assignments_submissionfile'
        ordering = ['uploaded_at']

    def __str__(self):
        return self.filename

    def save(self, *args, **kwargs):
        # Store original filename
        if self.file and not self.filename:
            self.filename = self.file.name.split('/')[-1]
        super().save(*args, **kwargs)


class Grade(models.Model):
    """
    Instructor's grade and feedback for a submission.
    """
    submission = models.OneToOneField(
        Submission,
        on_delete=models.CASCADE,
        related_name='grade'
    )
    grader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='grades_given'
    )
    points = models.PositiveIntegerField(
        validators=[MinValueValidator(0)]
    )
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assignments_grade'

    def __str__(self):
        return f"{self.submission.student.email} - {self.points}/{self.submission.assignment.max_points}"

    @property
    def percentage(self):
        max_pts = self.submission.assignment.max_points
        return round((self.points / max_pts) * 100, 1) if max_pts > 0 else 0
