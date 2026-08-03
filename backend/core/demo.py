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
# core.tests.test_demo_lockdown.TestDemoBlockedWrites
# .test_body_shape_is_the_frontend_contract.
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
    if not isinstance(email, str) or not settings.DEMO_ACCOUNT_EMAIL:
        # An empty DEMO_ACCOUNT_EMAIL must match nothing, not every blank
        # address — otherwise misconfiguration silently locks real users out.
        return False
    return email.strip().lower() == settings.DEMO_ACCOUNT_EMAIL.strip().lower()


def is_demo_user(user) -> bool:
    """True when this is the shared public demo account."""
    return (
        user is not None
        and getattr(user, 'is_authenticated', False)
        and is_demo_email(user.email)
    )


def is_demo_course(course) -> bool:
    """True when this is the shared public demo course (Phase 67).

    Derived, not hardcoded: the demo course is whichever course the shared
    demo account is enrolled in — clone_course_for_demo + seed_demo_account
    guarantee exactly one, and re-pointing the demo at a different course must
    not require editing a literal 'DEMO101' scattered across guards. A course
    the demo account *teaches* counts too, so the check still holds if a demo
    instructor is ever added.

    Deliberately a query rather than a cached flag: this runs on
    instructor-only management endpoints and one throttled public endpoint,
    never in a content hot path.
    """
    if course is None or not settings.DEMO_ACCOUNT_EMAIL:
        return False
    if is_demo_email(getattr(getattr(course, 'instructor', None), 'email', None)):
        return True

    # Deliberately NOT filtered on is_active: a soft-deleted demo enrollment
    # does not stop this being the demo course, and filtering on it would let
    # the guard silently switch off the moment someone unenrolled the demo
    # account. A guard that quietly stops guarding is worse than none.
    from courses.models import Enrollment
    return Enrollment.objects.filter(
        course=course,
        user__email__iexact=settings.DEMO_ACCOUNT_EMAIL,
    ).exists()


def require_not_demo_course(course):
    """Raise the standard demo 403 for a write aimed at the demo course."""
    if is_demo_course(course):
        raise PermissionDenied(DEMO_BLOCKED_BODY)


def require_not_demo(user):
    """Raise the standard demo 403 when the demo account attempts a write.

    Learning writes (lesson progress, quiz attempts, notification
    read-marks) stay open to the demo account so the demo works; identity
    and shared-surface writes (profile, settings, avatars, enrollments,
    discussion posts) call this first.
    """
    if is_demo_user(user):
        raise PermissionDenied(DEMO_BLOCKED_BODY)
