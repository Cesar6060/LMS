from django.db.models.signals import post_save
from django.dispatch import receiver

from courses.models import Enrollment, Lesson
from assignments.models import Assignment, Submission, Grade
from .models import Notification


@receiver(post_save, sender=Enrollment)
def notify_instructor_on_enrollment(sender, instance, created, **kwargs):
    """Notify instructor when a student enrolls in their course."""
    if created:
        course = instance.course
        student = instance.user
        Notification.objects.create(
            recipient=course.instructor,
            type='enrollment',
            title=f'New enrollment in {course.code}',
            message=f'{student.first_name} {student.last_name} ({student.email}) has enrolled in {course.title}.',
            related_url=f'/instructor/courses/{course.code}/manage'
        )


@receiver(post_save, sender=Lesson)
def notify_students_on_new_lesson(sender, instance, created, **kwargs):
    """Notify enrolled students when a new lesson is added."""
    if created:
        course = instance.unit.course
        # Get all actively enrolled students
        enrollments = Enrollment.objects.filter(course=course, is_active=True).select_related('user')

        notifications = [
            Notification(
                recipient=enrollment.user,
                type='new_lesson',
                title=f'New lesson in {course.code}',
                message=f'A new lesson "{instance.title}" has been added to {course.title}.',
                related_url=f'/courses/{course.code}/lessons/{instance.id}'
            )
            for enrollment in enrollments
        ]
        Notification.objects.bulk_create(notifications)


@receiver(post_save, sender=Assignment)
def notify_students_on_new_assignment(sender, instance, created, **kwargs):
    """Notify enrolled students when a new assignment is added (only if available)."""
    if created:
        # Don't notify if assignment is not yet available (available_from is in future)
        if not instance.is_available:
            return

        course = instance.unit.course
        # Get all actively enrolled students
        enrollments = Enrollment.objects.filter(course=course, is_active=True).select_related('user')

        due_text = ""
        if instance.due_date:
            due_text = f" Due: {instance.due_date.strftime('%b %d, %Y')}."

        notifications = [
            Notification(
                recipient=enrollment.user,
                type='new_assignment',
                title=f'New assignment in {course.code}',
                message=f'A new assignment "{instance.title}" has been posted.{due_text}',
                related_url=f'/assignments/{instance.id}'
            )
            for enrollment in enrollments
        ]
        Notification.objects.bulk_create(notifications)


@receiver(post_save, sender=Submission)
def notify_instructor_on_submission(sender, instance, **kwargs):
    """Notify instructor when a student submits an assignment."""
    # Only notify when status changes to 'submitted'
    if instance.status == 'submitted' and instance.submitted_at:
        assignment = instance.assignment
        course = assignment.course
        student = instance.student

        # Check if notification already exists for this submission
        # (to avoid duplicates on save)
        existing = Notification.objects.filter(
            recipient=course.instructor,
            type='submission',
            related_url=f'/instructor/assignments/{assignment.id}/grade'
        ).filter(
            message__contains=student.email
        ).exists()

        if not existing:
            Notification.objects.create(
                recipient=course.instructor,
                type='submission',
                title=f'New submission for {assignment.title}',
                message=f'{student.first_name} {student.last_name} ({student.email}) submitted {assignment.title}.',
                related_url=f'/instructor/assignments/{assignment.id}/grade'
            )


@receiver(post_save, sender=Grade)
def notify_student_on_grade(sender, instance, created, **kwargs):
    """Notify student when their assignment is graded."""
    submission = instance.submission
    assignment = submission.assignment
    student = submission.student

    # Notify on both create and update of grade
    Notification.objects.create(
        recipient=student,
        type='grade',
        title=f'{assignment.title} has been graded',
        message=f'You received {instance.points}/{assignment.max_points} points on {assignment.title}.',
        related_url=f'/assignments/{assignment.id}'
    )


def notify_student_resubmission_allowed(submission):
    """
    Notify student when instructor allows resubmission.
    Called from the allow_resubmission view.
    """
    assignment = submission.assignment
    student = submission.student

    Notification.objects.create(
        recipient=student,
        type='resubmission',
        title=f'Resubmission allowed for {assignment.title}',
        message=f'Your instructor has allowed you to resubmit {assignment.title}.',
        related_url=f'/assignments/{assignment.id}'
    )
