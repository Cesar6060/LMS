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
    fail_silently: bool = True,
    triggered_by=None,
) -> bool:
    """
    Send an email using an HTML template with a plain text fallback.

    Args:
        subject: Email subject line
        template_name: Path to the HTML template (e.g., 'emails/announcement.html')
        context: Context dictionary for the template
        recipient_list: List of recipient email addresses
        fail_silently: If True, don't raise exceptions on failure
        triggered_by: The user whose action caused this email, if any

    Returns:
        True if email was sent successfully, False otherwise
    """
    # Defense-in-depth (Phase 47): the shared public demo account must never
    # cause outbound email. Today it's a student and can't reach the
    # instructor-only invite/announcement endpoints, but this holds even if a
    # demo instructor is ever added.
    if (
        triggered_by is not None
        and triggered_by.email == settings.DEMO_ACCOUNT_EMAIL
    ):
        logger.warning(
            f"Refusing to send email to {recipient_list}: "
            "triggered by the demo account."
        )
        return False

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


def send_course_invite_link_email(
    recipient_email: str,
    course_title: str,
    instructor_name: str,
    invite_url: str,
    triggered_by=None,
) -> bool:
    """Send a tokenized course invite link (Phase 51)."""
    return send_templated_email(
        subject=f"You're invited to join {course_title}",
        template_name='emails/course_invite_link.html',
        context={
            'course_title': course_title,
            'instructor_name': instructor_name,
            'invite_url': invite_url,
        },
        recipient_list=[recipient_email],
        triggered_by=triggered_by,
    )


def send_announcement_email(
    recipient_email: str,
    course_title: str,
    announcement_title: str,
    announcement_content: str,
    announcement_url: str,
    instructor_name: str,
    posted_date: str,
    triggered_by=None,
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
        recipient_list=[recipient_email],
        triggered_by=triggered_by,
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
