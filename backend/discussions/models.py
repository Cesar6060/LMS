from django.db import models
from django.conf import settings

from courses.models import Course


class Thread(models.Model):
    """A course-level discussion thread (title + markdown body)."""
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='threads'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='threads_created'
    )
    title = models.CharField(max_length=200)
    content = models.TextField(help_text='Markdown supported')
    is_pinned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f"{self.course.code}: {self.title}"


class Reply(models.Model):
    """A flat (non-nested) reply to a discussion thread."""
    thread = models.ForeignKey(
        Thread,
        on_delete=models.CASCADE,
        related_name='replies'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='replies_created'
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Reply by {self.author.email} on {self.thread.title}"
