"""Breached-password screening against Have I Been Pwned (phase 73, task E).

Django's four stock validators catch structural weakness — too short, too
similar to the username, all digits, in a 20k-entry common-password list. None
of them catch a password that is structurally fine but has already appeared in
a public credential dump, which is exactly what credential-stuffing attacks
reuse. This validator closes that gap.

**The password never leaves the server.** HIBP's range API is a k-anonymity
protocol: we SHA-1 the candidate, send only the first 5 hex characters of the
digest, and HIBP returns every known-breached hash sharing that prefix (~800
entries) as ``SUFFIX:COUNT`` lines. The remaining 35 characters are matched
locally. HIBP therefore learns a bucket that a few hundred million hashes fall
into, never the password, the hash, or who asked.

SHA-1 is not a security choice here — it is the protocol HIBP defines. It is a
lookup key against a public corpus, not a stored credential, so its collision
weakness is irrelevant: a collision would at worst reject a good password.

**Fail open.** Every failure path — DNS, TLS, timeout, 429, 5xx, a malformed
body — allows the password through with a warning log. Failing closed would
mean a HIBP outage blocks password *reset*, and reset is most needed by someone
who is already locked out or actively being attacked. A brief window where new
passwords are only checked against Django's stock validators is strictly less
harmful than a lockout, so the outage degrades screening rather than access.
Operationally the warning is the signal: a burst of them means screening is
silently off, not that users are affected.
"""

import hashlib
import logging
import os

import requests
from decouple import config
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

HIBP_RANGE_URL = 'https://api.pwnedpasswords.com/range/'

# Short by design. This call sits inline in registration, password change and
# reset-confirm, so its timeout is added latency on every one of them; two
# seconds is long enough for a healthy round trip and short enough that a
# hanging HIBP does not make password endpoints look broken.
HIBP_TIMEOUT_SECONDS = 2.0


def _running_under_pytest() -> bool:
    """True inside a pytest session, from environment variables pytest sets.

    Deliberately environment-based rather than ``'pytest' in sys.modules``: a
    production process that happened to import pytest transitively must not be
    able to switch breach screening off.
    """
    return 'PYTEST_VERSION' in os.environ or 'PYTEST_CURRENT_TEST' in os.environ


# Read at import in the style of config/settings.py. Off switch for offline dev
# and for CI.
#
# The default is *off* under pytest. Existing tests across accounts/ and
# courses/ post real passwords to password-change, reset-confirm and
# invite-signup; measured with the HTTP layer instrumented, screening left on
# produced seven live calls to api.pwnedpasswords.com from a single suite run.
# That is unacceptable regardless of whether the tests still pass:
# it sends test-fixture password hashes to a third party, makes the suite depend
# on someone else's uptime, and adds a network round trip to unrelated tests.
# Nothing is lost by defaulting off, because fail-open means those tests would
# behave identically either way — the validator's own behaviour is covered by
# core/tests/test_password_validation.py with the HTTP layer mocked.
#
# Set HIBP_ENABLED=true to force it on inside a test run anyway.
HIBP_ENABLED = config(
    'HIBP_ENABLED', default=not _running_under_pytest(), cast=bool)


class PwnedPasswordValidator:
    """Reject passwords that appear in the Have I Been Pwned corpus.

    Registered in ``AUTH_PASSWORD_VALIDATORS``, so it applies anywhere Django's
    ``validate_password`` runs: registration, password change, reset-confirm,
    and the invite-signup path in ``courses/views.py``.

    ``timeout`` and ``enabled`` can be overridden per registration via the
    validator's ``OPTIONS`` dict, and are what tests instantiate against.
    """

    def __init__(self, timeout: float = HIBP_TIMEOUT_SECONDS, enabled=None):
        self.timeout = timeout
        # Deliberately not resolved to a bool here: None means "defer to the
        # module flag", read at validate() time so a test can flip
        # HIBP_ENABLED without rebuilding Django's cached validator list.
        self._enabled_override = enabled

    @property
    def enabled(self) -> bool:
        if self._enabled_override is None:
            return HIBP_ENABLED
        return bool(self._enabled_override)

    def validate(self, password, user=None):
        if not self.enabled or not password:
            return

        digest = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
        prefix, suffix = digest[:5], digest[5:]

        breach_count = self._breach_count(prefix, suffix)
        if breach_count:
            raise ValidationError(
                'This password has appeared in a known data breach '
                '(seen %(count)s times) and is unsafe to use. '
                'Please choose a different password.',
                code='password_pwned',
                params={'count': f'{breach_count:,}'},
            )

    def get_help_text(self):
        return (
            'Your password can’t be one that has appeared in a known data '
            'breach.'
        )

    def _breach_count(self, prefix: str, suffix: str) -> int:
        """Times this hash appears in the HIBP corpus; 0 when unknown.

        Returns 0 — "allow" — for every failure, which is what makes the
        validator fail open. The bare ``except Exception`` is intentional and
        is the point of the method: a screening enhancement must not be able to
        raise anything that reaches a user mid password reset, and that
        includes surprises from the HTTP stack and from parsing a body we do
        not control.
        """
        try:
            response = requests.get(
                f'{HIBP_RANGE_URL}{prefix}',
                headers={
                    # HIBP pads the response with random zero-count entries, so
                    # its size no longer reveals how many real hits the prefix
                    # had. Without it an observer of the encrypted stream can
                    # infer something about the password from response length.
                    'Add-Padding': 'true',
                    'User-Agent': 'STEM-Quest-breach-check',
                },
                timeout=self.timeout,
            )
        except Exception as exc:
            logger.warning(
                'HIBP range lookup failed (%s: %s); allowing password '
                'without a breach check.', type(exc).__name__, exc,
            )
            return 0

        if response.status_code != 200:
            logger.warning(
                'HIBP range lookup returned HTTP %s; allowing password '
                'without a breach check.', response.status_code,
            )
            return 0

        try:
            return self._count_for_suffix(response.text, suffix)
        except Exception as exc:
            logger.warning(
                'HIBP range response could not be parsed (%s: %s); allowing '
                'password without a breach check.', type(exc).__name__, exc,
            )
            return 0

    @staticmethod
    def _count_for_suffix(body: str, suffix: str) -> int:
        """Find ``suffix`` in a ``SUFFIX:COUNT`` per line response body.

        Padding entries carry a count of 0 and are otherwise indistinguishable
        from real ones, so a match is only a breach when the count is positive
        — treating any match as a hit would reject arbitrary good passwords
        whenever padding happened to collide.
        """
        for line in body.splitlines():
            line_suffix, _, line_count = line.strip().partition(':')
            if line_suffix.upper() != suffix:
                continue
            count = int(line_count.replace(',', '') or 0)
            if count > 0:
                return count
        return 0
