"""Phase 67: the deliverability properties of every outbound message.

Each test here pins one thing a district mail filter scores us on. The
originals were all defects found on 2026-08-02, when an invite to a school
address vanished without a trace:

- the text/plain part was ~70 lines of raw CSS, because `strip_tags` removes
  `<style>` tags but keeps their contents;
- Message-ID carried a Render container hostname, not our From domain;
- nothing set Reply-To, so a student who hit Reply bounced off noreply@;
- announcements (the one recurring mailing) had no List-Unsubscribe.
"""

import threading

import pytest
from django.conf import settings
from django.core import mail
from django.test import override_settings

from core.email import (
    _html_to_text,
    send_announcement_email,
    send_course_invite_link_email,
    send_templated_email,
)

locmem_email = override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
)

# Apostrophe and ampersand on purpose. Django's autoescape is per-engine, not
# per-file extension, so a `.txt` template escapes its variables unless it
# opts out — which would put `O&#x27;Brien` in the plain-text part, worse than
# the `_html_to_text` fallback it is supposed to improve on.
INVITE_CONTEXT = {
    'course_title': 'Robotics & Design',
    'instructor_name': "Mr. O'Brien",
    'invite_url': 'https://stemquests.com/invite/token123',
}


@pytest.fixture(autouse=True)
def clear_outbox():
    mail.outbox.clear()
    yield
    mail.outbox.clear()


# --- the plain-text part -------------------------------------------------


@locmem_email
def test_plaintext_part_contains_no_css():
    send_course_invite_link_email(
        recipient_email='student@test.com',
        course_title=INVITE_CONTEXT['course_title'],
        instructor_name=INVITE_CONTEXT['instructor_name'],
        invite_url=INVITE_CONTEXT['invite_url'],
    )

    body = mail.outbox[0].body
    assert 'font-family' not in body
    assert 'background-color' not in body
    assert '{' not in body and '}' not in body
    # ...and it is a real message, not just an empty one that passes the above.
    assert INVITE_CONTEXT['invite_url'] in body
    assert INVITE_CONTEXT['course_title'] in body
    assert INVITE_CONTEXT['instructor_name'] in body
    # Real punctuation, not HTML entities.
    assert '&#x27;' not in body and '&amp;' not in body


@locmem_email
def test_plaintext_falls_back_cleanly_without_txt_template():
    """base.html has no `.txt` partner, so this exercises the safety net.

    Every future template gets this for free — a hand-written text part is
    better, but forgetting one must not put a stylesheet back on the wire.
    """
    send_templated_email(
        subject='No text partner',
        template_name='emails/base.html',
        context={},
        recipient_list=['student@test.com'],
    )

    body = mail.outbox[0].body
    assert 'font-family' not in body
    assert 'background-color' not in body
    assert '.button' not in body


def test_html_to_text_drops_style_and_script_contents():
    text = _html_to_text(
        '<html><head><title>T</title><style>body { color: red; }</style>'
        '</head><body><script>alert(1)</script><p>Hello</p></body></html>'
    )

    assert text == 'Hello'


def test_html_to_text_unescapes_entities_and_collapses_blank_lines():
    text = _html_to_text(
        '<p>Ben &amp; Jerry&#39;s</p>\n\n\n\n<p>Next</p>')

    assert text == "Ben & Jerry's\n\nNext"


def test_html_to_text_keeps_line_structure():
    text = _html_to_text('<p>One<br>Two</p><p>Three</p>')

    assert text.splitlines() == ['One', 'Two', '', 'Three']


# --- headers -------------------------------------------------------------


@locmem_email
@override_settings(DEFAULT_FROM_EMAIL='STEM Quest <noreply@stemquests.com>')
def test_message_id_domain_matches_from_domain():
    """Django derives Message-ID from socket.getfqdn(), which in production is
    a Render container hostname unrelated to the From domain — a mismatch
    receivers score against us."""
    send_course_invite_link_email(
        recipient_email='student@test.com',
        course_title='Intro to Game Dev',
        instructor_name='Test Instructor',
        invite_url='https://stemquests.com/invite/token123',
    )

    message_id = mail.outbox[0].extra_headers['Message-ID']
    assert message_id.endswith('@stemquests.com>')


@locmem_email
@override_settings(DEFAULT_FROM_EMAIL='noreply-with-no-domain')
def test_message_id_falls_back_to_django_default_without_a_from_domain():
    send_course_invite_link_email(
        recipient_email='student@test.com',
        course_title='Intro to Game Dev',
        instructor_name='Test Instructor',
        invite_url='https://stemquests.com/invite/token123',
    )

    # No header of our own: Django stamps its own Message-ID at send time.
    assert 'Message-ID' not in mail.outbox[0].extra_headers


@locmem_email
def test_invite_email_sets_reply_to_when_given():
    send_course_invite_link_email(
        recipient_email='student@test.com',
        course_title='Intro to Game Dev',
        instructor_name='Test Instructor',
        invite_url='https://stemquests.com/invite/token123',
        reply_to=['teacher@school.edu'],
    )

    assert mail.outbox[0].reply_to == ['teacher@school.edu']


@locmem_email
def test_invite_email_has_no_reply_to_by_default():
    send_course_invite_link_email(
        recipient_email='student@test.com',
        course_title='Intro to Game Dev',
        instructor_name='Test Instructor',
        invite_url='https://stemquests.com/invite/token123',
    )

    assert mail.outbox[0].reply_to == []


@locmem_email
def test_announcement_sets_list_unsubscribe_headers():
    send_announcement_email(
        recipient_email='student@test.com',
        course_title='Intro to Game Dev',
        announcement_title='Class cancelled',
        announcement_content='No class today.',
        announcement_url='https://stemquests.com/announcements/1',
        instructor_name='Test Instructor',
        posted_date='2026-08-02',
    )

    headers = mail.outbox[0].extra_headers
    assert headers['List-Unsubscribe'] == f'<{settings.FRONTEND_URL}/settings>'
    assert headers['List-Unsubscribe-Post'] == 'List-Unsubscribe=One-Click'


@locmem_email
def test_invite_email_has_no_list_unsubscribe():
    """Invites are transactional: the recipient has no account and nothing to
    unsubscribe from, and an unsubscribe header on a one-off invitation reads
    as bulk mail."""
    send_course_invite_link_email(
        recipient_email='student@test.com',
        course_title='Intro to Game Dev',
        instructor_name='Test Instructor',
        invite_url='https://stemquests.com/invite/token123',
    )

    assert 'List-Unsubscribe' not in mail.outbox[0].extra_headers


@locmem_email
def test_announcement_plaintext_is_readable():
    send_announcement_email(
        recipient_email='student@test.com',
        course_title='Robotics & Design',
        announcement_title="Don't forget your kit",
        announcement_content="Bring your kit & don't be late.",
        announcement_url='https://stemquests.com/announcements/1',
        instructor_name="Mr. O'Brien",
        posted_date='2026-08-02',
    )

    body = mail.outbox[0].body
    assert 'font-family' not in body
    assert "Don't forget your kit" in body
    assert "Bring your kit & don't be late." in body
    assert 'https://stemquests.com/announcements/1' in body
    assert '&#x27;' not in body and '&amp;' not in body


# --- the async sender's cleanup ------------------------------------------


def test_send_emails_async_closes_the_db_connection_per_task():
    """The queued tasks write delivery state, so this thread opens its own DB
    connection. Django only closes connections at the end of a *request* and
    this thread has none — without the `finally`, every invite batch leaks a
    Neon connection. Exercised through the real threaded function, because
    the fixture the endpoint tests use replaces it wholesale."""
    from unittest import mock

    from core.email import send_emails_async

    def boom(recipient_email):
        raise OSError('relay refused')

    # Patched on the class, not on `django.db.connection`: that proxy resolves
    # to a per-thread connection object, so patching it here would never reach
    # the one the daemon thread actually opens — which is the connection this
    # test exists to prove gets closed.
    with mock.patch(
        'django.db.backends.base.base.BaseDatabaseWrapper.close') as close:
        before = set(threading.enumerate())
        send_emails_async([
            (boom, (), {'recipient_email': 'a@test.com'}),
            (boom, (), {'recipient_email': 'b@test.com'}),
        ])
        # Join only the thread this call started. Joining every daemon thread
        # would block on unrelated ones and would let their closes inflate
        # the count below.
        for thread in set(threading.enumerate()) - before:
            thread.join(timeout=5)

        assert close.call_count == 2, (
            'the connection must be closed once per task, even when the task '
            'raised'
        )
