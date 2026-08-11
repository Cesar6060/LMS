"""Session-wide pytest configuration.

Phase 73: throttle rates in config/settings.py now carry real defaults instead
of None, so that a scope whose env var is missing in production fails safe
rather than silently unthrottled. That is correct for the deployment and wrong
for the test suite — plenty of tests issue far more than 120 authenticated
requests a minute, and they would start failing on 429 for reasons that have
nothing to do with what they assert.

So throttling is off by default under pytest and opted back into per test with
``@pytest.mark.throttled``. The opt-in tests are the ones that assert throttling
behaviour, and they set the exact rate they need themselves.
"""

import pytest
from django.core.cache import caches
from rest_framework.throttling import SimpleRateThrottle


@pytest.fixture(autouse=True)
def neutralise_throttles(request, monkeypatch):
    """Disable rate limiting unless the test asks for it.

    ``SimpleRateThrottle.THROTTLE_RATES`` is bound to
    ``api_settings.DEFAULT_THROTTLE_RATES`` at class-definition time, so
    ``override_settings(REST_FRAMEWORK=...)`` does not reach it — the class
    attribute is what has to be replaced. Patching it on ``SimpleRateThrottle``
    reaches every throttle in the project, since all of them inherit from it and
    none of them redeclare the attribute.

    Every scope keeps its key with a value of None: DRF raises
    ImproperlyConfigured on a *missing* scope key but treats a None rate as
    "no limit", so preserving the keys keeps scoped throttles resolvable.

    Tests that patch ``THROTTLE_RATES`` on a subclass (the existing phase 51
    throttle tests patch ``ScopedRateThrottle``) still win over this, because a
    subclass attribute shadows the one set here.
    """
    if 'throttled' in request.keywords:
        # Counters live in a file-backed alias, so history outlives the process
        # and would leak between runs of the opt-in tests.
        caches['throttle'].clear()
        yield
        caches['throttle'].clear()
        return

    disabled = dict.fromkeys(SimpleRateThrottle.THROTTLE_RATES)
    monkeypatch.setattr(SimpleRateThrottle, 'THROTTLE_RATES', disabled)
    yield
