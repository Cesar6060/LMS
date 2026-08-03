"""
Email utility functions for sending templated emails.
"""
import html as html_lib
import logging
import re
from email.utils import make_msgid, parseaddr

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from core.demo import is_demo_user

logger = logging.getLogger(__name__)


# <head>, <style> and <script> must go *with their contents*. strip_tags()
# alone removes the tags and keeps the CSS, which is how every plain-text part
# we have ever sent opened with `body { font-family: ... }` — a textbook
# spam-filter trigger (phase 67).
_DROP_BLOCKS_RE = re.compile(
    r'<\s*(head|style|script)\b[^>]*>.*?<\s*/\s*\1\s*>',
    re.IGNORECASE | re.DOTALL,
)
_BR_RE = re.compile(r'<\s*br\s*/?\s*>', re.IGNORECASE)
_BLOCK_END_RE = re.compile(
    r'<\s*/\s*(p|div|h[1-6]|li|ul|ol|tr|table|section|blockquote)\s*>',
    re.IGNORECASE,
)


def _html_to_text(html: str) -> str:
    """Render an HTML email body as a readable plain-text part.

    The safety net for templates with no hand-written `.txt` partner: block
    elements become line breaks, `<head>/<style>/<script>` are dropped whole,
    entities are unescaped, and runs of blank lines collapse.
    """
    text = _DROP_BLOCKS_RE.sub('', html)
    text = _BR_RE.sub('\n', text)
    text = _BLOCK_END_RE.sub('\n\n', text)
    text = strip_tags(text)
    # strip_tags leaves entities intact (its parser is built with
    # convert_charrefs=False), so unescape after stripping, not before.
    text = html_lib.unescape(text)
    text = '\n'.join(line.strip() for line in text.splitlines())
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _text_template_for(template_name: str) -> str:
    """`emails/x.html` -> `emails/x.txt` (registration/*.txt is the precedent)."""
    return re.sub(r'\.html$', '.txt', template_name)


def _from_domain() -> str | None:
    """The domain of DEFAULT_FROM_EMAIL, or None when it has no parseable one."""
    _, address = parseaddr(settings.DEFAULT_FROM_EMAIL or '')
    # rpartition returns the whole string as the tail when the separator is
    # absent, so check the separator rather than trusting the tail.
    _, at, domain = address.rpartition('@')
    return domain.strip() if at else None


def _transactional_headers() -> dict:
    """Headers every outbound message gets.

    Django derives Message-ID from `socket.getfqdn()`, so production stamps a
    Render container hostname that has nothing to do with the From domain —
    a mismatch receivers score against us. Stamp the From domain instead.
    Falls back to Django's own default (no header set here) when
    DEFAULT_FROM_EMAIL has no parseable domain.
    """
    domain = _from_domain()
    if not domain:
        return {}
    return {'Message-ID': make_msgid(domain=domain)}


def send_templated_email(
    subject: str,
    template_name: str,
    context: dict,
    recipient_list: list[str],
    fail_silently: bool = True,
    triggered_by=None,
    reply_to: list[str] | None = None,
    headers: dict | None = None,
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
        reply_to: Addresses for the Reply-To header, if any
        headers: Extra headers merged over the transactional defaults

    Returns:
        True if email was sent successfully, False otherwise
    """
    # Defense-in-depth (Phase 47): the shared public demo account must never
    # cause outbound email. Today it's a student and can't reach the
    # instructor-only invite/announcement endpoints, but this holds even if a
    # demo instructor is ever added.
    if is_demo_user(triggered_by):
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

        # Prefer a hand-authored text part; fall back to converting the HTML.
        try:
            text_content = render_to_string(
                _text_template_for(template_name), context)
        except TemplateDoesNotExist:
            text_content = _html_to_text(html_content)

        extra_headers = _transactional_headers()
        if headers:
            extra_headers.update(headers)

        # Create email with both HTML and plain text
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
            reply_to=reply_to or None,
            headers=extra_headers,
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
    reply_to: list[str] | None = None,
    fail_silently: bool = True,
) -> bool:
    """Send a tokenized course invite link (Phase 51).

    Transactional — deliberately no List-Unsubscribe header: an invite is a
    one-off message to someone who has no account to unsubscribe from.
    """
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
        reply_to=reply_to,
        fail_silently=fail_silently,
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
    reply_to: list[str] | None = None,
) -> bool:
    """Send an announcement notification email.

    Announcements are the opt-in recurring mailing
    (`UserPreferences.email_announcements`), so they carry List-Unsubscribe
    pointing at the settings page that owns that toggle.
    """
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
        reply_to=reply_to,
        headers={
            'List-Unsubscribe': f'<{settings.FRONTEND_URL}/settings>',
            'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
        },
    )


def send_emails_async(email_tasks: list) -> None:
    """
    Send multiple emails in a background thread to avoid blocking.

    Args:
        email_tasks: List of tuples (function, args, kwargs)
    """
    import threading

    from django.db import connection

    def send_all():
        for func, args, kwargs in email_tasks:
            recipient = (
                kwargs.get('recipient_email')
                or kwargs.get('recipient_list')
                or 'unknown recipient'
            )
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Async email to {recipient} failed: {str(e)}")
            finally:
                # These tasks write delivery state, so the thread opens its own
                # DB connection. Django only closes connections at the end of a
                # *request*, and this thread has none — leaving it open leaks a
                # Neon connection per invite batch.
                connection.close()

    thread = threading.Thread(target=send_all, daemon=True)
    thread.start()
