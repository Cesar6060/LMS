"""Guard tests for core.email — the demo-account outbound-mail block.

`send_templated_email` is the single funnel every platform email passes
through (course invites, announcements), so the Phase 47 demo-account check
inside it is the whole defence: the shared public demo login must never be
able to make the platform send mail to a third party.

The guard keys on *who triggered* the send (`triggered_by`), not on who
receives it. These tests pin that direction down explicitly, because the
asymmetry is easy to misread from the call sites.
"""

import pytest
from django.conf import settings
from django.core import mail
from django.template import TemplateDoesNotExist
from django.test import override_settings

from accounts.models import User
from core.email import (
    send_announcement_email,
    send_course_invite_link_email,
    send_templated_email,
)

# Real rendering + a real (in-memory) backend rather than mocks: the point of
# these tests is that a message either does or does not reach the outbox.
locmem_email = override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
)

TEMPLATE = 'emails/course_invite_link.html'
CONTEXT = {
    'course_title': 'Intro to Game Dev',
    'instructor_name': 'Test Instructor',
    'invite_url': 'https://stemquests.com/invite/token123',
}


@pytest.fixture(autouse=True)
def clear_outbox():
    mail.outbox.clear()
    yield
    mail.outbox.clear()


@pytest.fixture
def instructor():
    return User.objects.create_user(
        email='instructor@test.com',
        password='testpass123',
        first_name='Test',
        last_name='Instructor',
        is_instructor=True,
    )


@pytest.fixture
def demo_user():
    return User.objects.create_user(
        email=settings.DEMO_ACCOUNT_EMAIL,
        password='testpass123',
        first_name='Jane',
        last_name='Doe',
    )


# --- ordinary mail still works ------------------------------------------


@pytest.mark.django_db
@locmem_email
def test_ordinary_email_sends(instructor):
    sent = send_templated_email(
        subject='You are invited',
        template_name=TEMPLATE,
        context=dict(CONTEXT),
        recipient_list=['student@test.com'],
        triggered_by=instructor,
    )

    assert sent is True
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.subject == 'You are invited'
    assert message.to == ['student@test.com']
    assert message.from_email == settings.DEFAULT_FROM_EMAIL
    # Plain-text body is the stripped HTML; the HTML rides as an alternative.
    assert CONTEXT['invite_url'] in message.body
    html, content_type = message.alternatives[0]
    assert content_type == 'text/html'
    assert '<html' in html.lower()
    assert CONTEXT['course_title'] in html


@locmem_email
def test_email_without_triggered_by_sends():
    # System-generated mail (no triggering user) must not be caught by the
    # demo guard — `triggered_by=None` is the default for most call sites.
    sent = send_templated_email(
        subject='System notice',
        template_name=TEMPLATE,
        context=dict(CONTEXT),
        recipient_list=['student@test.com'],
    )

    assert sent is True
    assert len(mail.outbox) == 1


@locmem_email
def test_multiple_recipients_are_all_addressed():
    send_templated_email(
        subject='You are invited',
        template_name=TEMPLATE,
        context=dict(CONTEXT),
        recipient_list=['a@test.com', 'b@test.com'],
    )

    assert mail.outbox[0].to == ['a@test.com', 'b@test.com']


# --- the demo-account block ---------------------------------------------


@pytest.mark.django_db
@locmem_email
def test_demo_account_trigger_is_refused(demo_user):
    sent = send_templated_email(
        subject='You are invited',
        template_name=TEMPLATE,
        context=dict(CONTEXT),
        recipient_list=['victim@example.com'],
        triggered_by=demo_user,
    )

    assert sent is False
    assert mail.outbox == []


@pytest.mark.django_db
@locmem_email
def test_demo_account_block_runs_before_rendering(demo_user):
    # The guard is the first statement in the function, so it holds even for
    # a send that would otherwise blow up — nothing about the payload can
    # route around it.
    sent = send_templated_email(
        subject='You are invited',
        template_name='emails/does_not_exist.html',
        context={},
        recipient_list=['victim@example.com'],
        fail_silently=False,
        triggered_by=demo_user,
    )

    assert sent is False
    assert mail.outbox == []


@pytest.mark.django_db
@locmem_email
def test_course_invite_link_email_refused_for_demo_account(demo_user):
    # Phase 51 invite path — the one that can address an arbitrary stranger.
    sent = send_course_invite_link_email(
        recipient_email='victim@example.com',
        course_title='Intro to Game Dev',
        instructor_name='Jane Doe',
        invite_url='https://stemquests.com/invite/token123',
        triggered_by=demo_user,
    )

    assert sent is False
    assert mail.outbox == []


@pytest.mark.django_db
@locmem_email
def test_announcement_email_refused_for_demo_account(demo_user):
    sent = send_announcement_email(
        recipient_email='student@test.com',
        course_title='Intro to Game Dev',
        announcement_title='Class cancelled',
        announcement_content='No class today.',
        announcement_url='https://stemquests.com/announcements/1',
        instructor_name='Jane Doe',
        posted_date='2026-07-24',
        triggered_by=demo_user,
    )

    assert sent is False
    assert mail.outbox == []


@pytest.mark.django_db
@locmem_email
def test_course_invite_link_email_sends_for_real_instructor(instructor):
    sent = send_course_invite_link_email(
        recipient_email='student@test.com',
        course_title='Intro to Game Dev',
        instructor_name='Test Instructor',
        invite_url='https://stemquests.com/invite/token123',
        triggered_by=instructor,
    )

    assert sent is True
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "You're invited to join Intro to Game Dev"
    assert mail.outbox[0].to == ['student@test.com']


@pytest.mark.django_db
@locmem_email
def test_demo_account_as_recipient_is_not_blocked(instructor):
    # Documents the actual (trigger-side only) semantics: mail *addressed to*
    # the demo account still sends. Only mail the demo account causes is
    # refused. Nothing in the product mails the demo address today, but if
    # that ever needs blocking it is a separate change, not a regression here.
    sent = send_templated_email(
        subject='You are invited',
        template_name=TEMPLATE,
        context=dict(CONTEXT),
        recipient_list=[settings.DEMO_ACCOUNT_EMAIL],
        triggered_by=instructor,
    )

    assert sent is True
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [settings.DEMO_ACCOUNT_EMAIL]


@pytest.mark.django_db
@locmem_email
@override_settings(DEMO_ACCOUNT_EMAIL='swapped-demo@example.com')
def test_block_follows_the_demo_account_email_setting():
    # The guard reads settings.DEMO_ACCOUNT_EMAIL at call time, so pointing
    # the setting at a different account moves the block with it.
    swapped = User.objects.create_user(
        email='swapped-demo@example.com', password='testpass123')
    old_default = User.objects.create_user(
        email='jdoe@demo.com', password='testpass123')

    refused = send_templated_email(
        subject='Blocked', template_name=TEMPLATE, context=dict(CONTEXT),
        recipient_list=['victim@example.com'], triggered_by=swapped,
    )
    allowed = send_templated_email(
        subject='Allowed', template_name=TEMPLATE, context=dict(CONTEXT),
        recipient_list=['student@test.com'], triggered_by=old_default,
    )

    assert refused is False
    assert allowed is True
    assert [m.subject for m in mail.outbox] == ['Allowed']


@pytest.mark.django_db
@locmem_email
def test_block_is_an_exact_email_match():
    # Documented limitation, not an endorsement: the comparison is a plain
    # `==`, so an account differing only in case would not be blocked. Safe
    # today because the email column is unique and the demo account is
    # provisioned with exactly settings.DEMO_ACCOUNT_EMAIL — but any future
    # move to case-insensitive logins must revisit this check.
    local, _, domain = settings.DEMO_ACCOUNT_EMAIL.partition('@')
    lookalike_email = f'{local.swapcase()}@{domain}'
    assert lookalike_email != settings.DEMO_ACCOUNT_EMAIL
    lookalike = User.objects.create_user(
        email=lookalike_email, password='testpass123')

    sent = send_templated_email(
        subject='You are invited',
        template_name=TEMPLATE,
        context=dict(CONTEXT),
        recipient_list=['student@test.com'],
        triggered_by=lookalike,
    )

    assert sent is True
    assert len(mail.outbox) == 1


# --- context and failure handling ---------------------------------------


@locmem_email
def test_frontend_url_is_injected_when_absent():
    context = dict(CONTEXT)

    send_templated_email(
        subject='You are invited',
        template_name=TEMPLATE,
        context=context,
        recipient_list=['student@test.com'],
    )

    assert context['frontend_url'] == settings.FRONTEND_URL


@locmem_email
def test_explicit_frontend_url_is_preserved():
    context = dict(CONTEXT, frontend_url='https://custom.example.com')

    send_templated_email(
        subject='You are invited',
        template_name=TEMPLATE,
        context=context,
        recipient_list=['student@test.com'],
    )

    assert context['frontend_url'] == 'https://custom.example.com'


@locmem_email
def test_render_failure_returns_false_when_failing_silently():
    # fail_silently defaults to True: a broken template must degrade to "no
    # email" rather than 500 the request that triggered it.
    sent = send_templated_email(
        subject='You are invited',
        template_name='emails/does_not_exist.html',
        context={},
        recipient_list=['student@test.com'],
    )

    assert sent is False
    assert mail.outbox == []


@locmem_email
def test_render_failure_raises_when_not_failing_silently():
    with pytest.raises(TemplateDoesNotExist):
        send_templated_email(
            subject='You are invited',
            template_name='emails/does_not_exist.html',
            context={},
            recipient_list=['student@test.com'],
            fail_silently=False,
        )

    assert mail.outbox == []
