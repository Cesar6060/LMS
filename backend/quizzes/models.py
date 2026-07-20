from django.db import models
from django.conf import settings
from courses.models import Unit


class Quiz(models.Model):
    """A quiz belonging to a unit."""
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    passing_score = models.PositiveIntegerField(default=70, help_text="Minimum percentage to pass")
    points = models.PositiveIntegerField(default=10, help_text="Total points for gradebook")
    max_attempts = models.PositiveIntegerField(default=0, help_text="Maximum attempts allowed (0 = unlimited)")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name_plural = 'quizzes'

    def __str__(self):
        return f"{self.title} ({self.unit.course.code})"

    @property
    def question_count(self):
        return self.questions.count()


class Question(models.Model):
    """A multiple choice question in a quiz."""
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Q{self.order}: {self.text[:50]}..."


class Choice(models.Model):
    """A choice for a multiple choice question."""
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.text[:50]}{'...' if len(self.text) > 50 else ''} ({'correct' if self.is_correct else 'incorrect'})"


class QuizAttempt(models.Model):
    """
    A student's attempt at a quiz.

    Phase 32: attempts can be session-based (Duolingo flow). ``in_progress``
    rows exist while a session runs and are excluded from every score/attempt
    consumer; ``completed`` rows are the graded record. Legacy batch submits
    create rows directly as ``completed``.
    """
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_IN_PROGRESS, 'In progress'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_attempts')
    score = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage score")
    passed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_COMPLETED)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-completed_at']

    def __str__(self):
        return f"{self.student.email} - {self.quiz.title}: {self.score}%"

    @property
    def points_earned(self):
        """Calculate points earned based on percentage and quiz total points."""
        return round((float(self.score) / 100) * self.quiz.points, 2)


class AttemptAnswer(models.Model):
    """
    A student's answer to a question in an attempt.

    ``selected_choice``/``is_correct`` always record the FIRST try — they are
    the score record and are never overwritten by mastery retries.
    ``mastered_at`` is stamped when the question is eventually answered
    correctly (first try or a later re-queue pass).
    """
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choice = models.ForeignKey(Choice, on_delete=models.SET_NULL, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    mastered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['attempt', 'question']

    def __str__(self):
        return f"Answer to Q{self.question.order}: {'Correct' if self.is_correct else 'Incorrect'}"
