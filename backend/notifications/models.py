from django.db import models
from django.conf import settings


class Notification(models.Model):
    """
    User notifications for course events.
    """
    TYPE_CHOICES = [
        ('enrollment', 'New Enrollment'),
        ('submission', 'New Submission'),
        ('grade', 'Assignment Graded'),
        ('new_lesson', 'New Lesson'),
        ('new_assignment', 'New Assignment'),
        ('resubmission', 'Resubmission Allowed'),
        ('announcement', 'New Announcement'),
        ('reply', 'New Reply'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    related_url = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications_notification'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipient.email}: {self.title}"
