from django.db.models.signals import post_save
from django.dispatch import receiver

from courses.models import Enrollment, Lesson
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
                related_url=f'/courses/{course.code}/learn/{instance.id}'
            )
            for enrollment in enrollments
        ]
        Notification.objects.bulk_create(notifications)
