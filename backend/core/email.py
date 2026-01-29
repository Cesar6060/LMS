"""
Email utility functions for sending templated emails.
"""
import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_templated_email(
    subject: str,
    template_name: str,
    context: dict,
    recipient_list: list[str],
    fail_silently: bool = True
) -> bool:
    """
    Send an email using an HTML template with a plain text fallback.
    
    Args:
        subject: Email subject line
        template_name: Path to the HTML template (e.g., 'emails/announcement.html')
        context: Context dictionary for the template
        recipient_list: List of recipient email addresses
        fail_silently: If True, don't raise exceptions on failure
        
    Returns:
        True if email was sent successfully, False otherwise
    """
    try:
        # Add frontend_url to context if not present
        if 'frontend_url' not in context:
            context['frontend_url'] = settings.FRONTEND_URL
            
        # Render HTML content
        html_content = render_to_string(template_name, context)
        
        # Create plain text version by stripping HTML
        text_content = strip_tags(html_content)
        
        # Create email with both HTML and plain text
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list
        )
        email.attach_alternative(html_content, "text/html")
        
        email.send(fail_silently=fail_silently)
        logger.info(f"Email sent successfully to {recipient_list}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_list}: {str(e)}")
        if not fail_silently:
            raise
        return False


def send_course_invitation_email(
    recipient_email: str,
    course_title: str,
    instructor_name: str,
    enrollment_code: str
) -> bool:
    """Send a course invitation email."""
    return send_templated_email(
        subject=f"You're invited to join {course_title}",
        template_name='emails/course_invitation.html',
        context={
            'course_title': course_title,
            'instructor_name': instructor_name,
            'enrollment_code': enrollment_code,
        },
        recipient_list=[recipient_email]
    )


def send_announcement_email(
    recipient_email: str,
    course_title: str,
    announcement_title: str,
    announcement_content: str,
    announcement_url: str,
    instructor_name: str,
    posted_date: str
) -> bool:
    """Send an announcement notification email."""
    return send_templated_email(
        subject=f"New Announcement in {course_title}: {announcement_title}",
        template_name='emails/announcement.html',
        context={
            'course_title': course_title,
            'announcement_title': announcement_title,
            'announcement_content': announcement_content,
            'announcement_url': announcement_url,
            'instructor_name': instructor_name,
            'posted_date': posted_date,
        },
        recipient_list=[recipient_email]
    )


def send_grade_notification_email(
    recipient_email: str,
    course_title: str,
    assignment_title: str,
    points_earned: float,
    points_possible: int,
    percentage: float,
    feedback: str,
    assignment_url: str
) -> bool:
    """Send a grade notification email."""
    return send_templated_email(
        subject=f"Your assignment '{assignment_title}' has been graded",
        template_name='emails/grade_notification.html',
        context={
            'course_title': course_title,
            'assignment_title': assignment_title,
            'points_earned': points_earned,
            'points_possible': points_possible,
            'percentage': round(percentage, 1),
            'feedback': feedback,
            'assignment_url': assignment_url,
        },
        recipient_list=[recipient_email]
    )


def notify_student_of_grade(submission, grade, is_update: bool = False) -> bool:
    """
    Send grade notification email to student, respecting preferences.

    Args:
        submission: The Submission object
        grade: The Grade object
        is_update: If True, this is a grade update (not initial grading)

    Returns:
        True if email was sent, False otherwise
    """
    from accounts.models import UserPreferences
    from django.conf import settings

    # Check if student wants grade emails
    try:
        prefs = UserPreferences.objects.get(user=submission.student)
        if not prefs.email_grades:
            return False
    except UserPreferences.DoesNotExist:
        pass  # Send by default if no preferences

    # Skip update notifications if grade hasn't meaningfully changed
    # (This prevents spam when instructor makes minor adjustments)
    if is_update and hasattr(grade, '_original_points'):
        if grade._original_points == grade.points:
            return False

    assignment = submission.assignment
    course = assignment.unit.course
    points_possible = assignment.max_points
    percentage = (float(grade.points) / points_possible * 100) if points_possible > 0 else 0

    return send_grade_notification_email(
        recipient_email=submission.student.email,
        course_title=course.title,
        assignment_title=assignment.title,
        points_earned=float(grade.points),
        points_possible=points_possible,
        percentage=percentage,
        feedback=grade.feedback or '',
        assignment_url=f"{settings.FRONTEND_URL}/courses/{course.code}/assignments/{assignment.id}"
    )


def send_emails_async(email_tasks: list) -> None:
    """
    Send multiple emails in a background thread to avoid blocking.

    Args:
        email_tasks: List of tuples (function, args, kwargs)
    """
    import threading

    def send_all():
        for func, args, kwargs in email_tasks:
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Async email failed: {str(e)}")

    thread = threading.Thread(target=send_all, daemon=True)
    thread.start()
