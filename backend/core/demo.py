"""Single source of truth for identifying the shared public demo account.

The live site is a public demo where every visitor logs in as the same
student (settings.DEMO_ACCOUNT_EMAIL). There is deliberately no is_demo
column: one account, and the email comparison is the identity every
existing guard already used. Import these helpers instead of comparing
emails inline — grep for is_demo_user to find every enforcement point.
"""

from django.conf import settings

from rest_framework.exceptions import PermissionDenied

# The 'code' key is a contract with the frontend: its API error handling
# detects demo_blocked on any 403 and shows a friendly "not available in
# the demo" message instead of the raw detail. Pinned by
# accounts.tests.TestDemoLockdown.test_demo_blocked_body_shape.
DEMO_BLOCKED_BODY = {
    'detail': 'This action is not available in the shared demo.',
    'code': 'demo_blocked',
}


def is_demo_email(email) -> bool:
    """True when the address is the shared public demo account's.

    Case-insensitive: allauth treats email login case-insensitively, so a
    caller that compares a request-supplied address must not be able to slip
    past the guard with a different case. Normalizing here rather than at
    each call site means no future caller has to remember to.
    """
    if not isinstance(email, str):
        return False
    return email.strip().lower() == (settings.DEMO_ACCOUNT_EMAIL or '').lower()


def is_demo_user(user) -> bool:
    """True when this is the shared public demo account."""
    return (
        user is not None
        and getattr(user, 'is_authenticated', False)
        and is_demo_email(user.email)
    )


def require_not_demo(user):
    """Raise the standard demo 403 when the demo account attempts a write.

    Learning writes (lesson progress, quiz attempts, notification
    read-marks) stay open to the demo account so the demo works; identity
    and shared-surface writes (profile, settings, avatars, enrollments,
    discussion posts) call this first.
    """
    if is_demo_user(user):
        raise PermissionDenied(DEMO_BLOCKED_BODY)
