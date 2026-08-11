"""
Guard tests for the production-readiness settings added in Phase 37.

The through-line is "inert unless its env var is set": every production
behaviour (HTTPS hardening, DATABASE_URL, manifest static storage) must stay
off in dev and CI, and the health endpoint must answer without auth so a
deploy gate can reach it.
"""

import dj_database_url
import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIClient


def test_health_shallow_ok(client):
    response = client.get('/api/health/')

    assert response.status_code == 200
    body = response.json()
    assert body == {'status': 'ok'}
    # No DB key: the shallow path must never touch the database, so a cold
    # Neon branch can't fail a Render deploy gate.
    assert 'database' not in body


@pytest.mark.django_db
def test_health_deep_ok(client):
    response = client.get('/api/health/?deep=1')

    assert response.status_code == 200
    assert response.json() == {
        'status': 'ok', 'database': 'ok', 'content': 'ok'}


@pytest.mark.django_db
def test_health_deep_reports_content_ok(client):
    """Phase 68: SELECT 1 proves the connection, not the schema. During the
    phase-65 outage a missing column returned 200 through a total content
    failure, so ?deep=1 now also reads named columns through the ORM."""
    response = client.get('/api/health/?deep=1')
    body = response.json()

    assert response.status_code == 200
    assert body['content'] == 'ok'
    # UptimeRobot monitor 803564235 keyword-matches this EXACT text. A
    # reshaped body is a silent monitoring outage, not an alert.
    assert '"database": "ok"' in response.content.decode()


@pytest.mark.django_db
def test_health_deep_503_when_content_read_fails(client, monkeypatch):
    from django.db.utils import ProgrammingError

    import config.health as health_module

    def boom():
        raise ProgrammingError(
            'column "content_key" does not exist on db.neon.tech user secret')

    monkeypatch.setattr(health_module, '_content_probe', boom)

    response = client.get('/api/health/?deep=1')
    body = response.json()

    assert response.status_code == 503
    assert body['status'] == 'error'
    assert body['content'] == 'unavailable'
    # No "database": "ok" anywhere, or the keyword monitor stays green
    # through a schema outage — the exact blindness this replaces.
    assert '"database": "ok"' not in response.content.decode()
    assert 'neon.tech' not in str(body)
    assert 'secret' not in str(body)


@pytest.mark.django_db
def test_health_deep_ok_on_empty_database(client):
    """Tolerating zero rows is the contract: a missing column raises
    ProgrammingError on an empty table too, while requiring rows would fail
    every fresh database and prove nothing extra."""
    from courses.models import Course, Lesson

    assert not Course.objects.exists()
    assert not Lesson.objects.exists()

    response = client.get('/api/health/?deep=1')

    assert response.status_code == 200
    assert response.json()['content'] == 'ok'


def test_health_shallow_still_touches_no_db(client, monkeypatch):
    """render.yaml uses the SHALLOW path as the deploy gate. A DB touch there
    makes a cold Neon branch fail a deploy."""
    import config.health as health_module

    def fail(*args, **kwargs):
        raise AssertionError('the shallow health path must not touch the DB')

    monkeypatch.setattr(connection, 'cursor', fail)
    monkeypatch.setattr(health_module, '_content_probe', fail)

    response = client.get('/api/health/')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_health_deep_returns_503_when_db_down(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError('connection refused to host db.neon.tech user secret')

    monkeypatch.setattr(connection, 'cursor', boom)

    response = client.get('/api/health/?deep=1')

    assert response.status_code == 503
    body = response.json()
    assert body['status'] == 'error'
    # The raw exception (host/user/SSL detail) must never reach an anonymous
    # caller — only a generic marker.
    assert body['database'] == 'unavailable'
    assert 'neon.tech' not in str(body)
    assert 'secret' not in str(body)


def test_health_requires_no_auth():
    # DRF's global IsAuthenticated default would 403 this if health were a DRF
    # view; it is a plain Django view precisely so monitors can reach it.
    response = APIClient().get('/api/health/')

    assert response.status_code == 200


def test_health_url_name_resolves():
    assert reverse('health') == '/api/health/'


def test_sentry_debug_404_when_flag_unset(client):
    # Inert unless its env var is set: without SENTRY_DEBUG_ENDPOINT the
    # endpoint must be indistinguishable from a missing route.
    response = client.get('/api/sentry-debug/')

    assert response.status_code == 404


def test_sentry_debug_raises_when_flag_set(client, monkeypatch):
    # Phase 73: the flag is read at import, so setting the env var here would
    # no longer reach the view — patch the resolved constant instead.
    monkeypatch.setattr('config.health.SENTRY_DEBUG_ENDPOINT_ENABLED', True)

    with pytest.raises(ZeroDivisionError):
        client.get('/api/sentry-debug/')


def test_sentry_debug_requires_no_auth(monkeypatch):
    # Plain Django view like health: an anonymous curl must reach the crash
    # (not a DRF 401/403), since the prod smoke test is an unauthenticated curl.
    monkeypatch.setattr('config.health.SENTRY_DEBUG_ENDPOINT_ENABLED', True)

    with pytest.raises(ZeroDivisionError):
        APIClient().get('/api/sentry-debug/')


def test_sentry_debug_flag_cannot_be_flipped_without_a_restart(monkeypatch):
    """Phase 73: enabling the crash route must leave a trace.

    Read per-request, SENTRY_DEBUG_ENDPOINT could be switched on from the
    Render dashboard with no deploy and no diff — an unauthenticated route
    whose whole job is to raise, turned on invisibly. Setting the environment
    variable now does nothing until the process restarts.
    """
    monkeypatch.setenv('SENTRY_DEBUG_ENDPOINT', 'true')

    response = APIClient().get('/api/sentry-debug/')

    assert response.status_code == 404


def test_sentry_debug_url_name_resolves():
    assert reverse('sentry-debug') == '/api/sentry-debug/'


def test_database_url_overrides_db_settings():
    parsed = dj_database_url.parse(
        'postgres://neon_user:secret@ep-example.aws.neon.tech/neondb',
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=True,
    )

    assert parsed['ENGINE'] == 'django.db.backends.postgresql'
    assert parsed['NAME'] == 'neondb'
    assert parsed['OPTIONS']['sslmode'] == 'require'


def test_secure_settings_absent_by_default():
    # Regression test for "inert without env vars": the SECURE_* block is
    # gated on USE_HTTPS, not on `not DEBUG`, so it stays off here even though
    # CI runs the suite with DEBUG=False.
    assert not getattr(settings, 'SECURE_SSL_REDIRECT', False)
    assert not getattr(settings, 'SESSION_COOKIE_SECURE', False)
    assert not getattr(settings, 'CSRF_COOKIE_SECURE', False)


def test_csp_header_on_every_response(client):
    # django-csp is always-on (not gated on USE_HTTPS): the API host serves
    # only JSON and the admin, so the strict policy is safe in every env.
    response = client.get('/api/health/')

    csp = response.headers['Content-Security-Policy']
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    # The admin allowances.
    assert "script-src 'self'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp


def test_permissions_policy_header_on_every_response(client):
    response = client.get('/api/health/')

    assert response.headers['Permissions-Policy'] == (
        'camera=(), microphone=(), geolocation=()')


def test_use_https_enables_hsts_preload(monkeypatch):
    # Same reload idiom as test_storage_settings: the flag lives inside the
    # USE_HTTPS block, which is off in this test environment.
    import importlib
    import config.settings as settings_module

    monkeypatch.setenv('USE_HTTPS', 'true')
    try:
        module = importlib.reload(settings_module)
        assert module.SECURE_HSTS_PRELOAD is True
        assert module.SECURE_HSTS_SECONDS == 31536000
    finally:
        monkeypatch.undo()
        importlib.reload(settings_module)


def test_hsts_preload_absent_by_default():
    # "Inert unless its env var is set" — no preload flag without USE_HTTPS.
    assert not getattr(settings, 'SECURE_HSTS_PRELOAD', False)


def test_debug_off_without_https_refuses_to_boot(monkeypatch):
    """Phase 73: transport security must not hang off an unverified variable.

    SSL redirect, HSTS, the proxy header and both Secure cookie flags all sit
    behind USE_HTTPS, and nothing asserted it was set. Unlike a missing
    SECRET_KEY, the failure was silent — the site kept serving, over plain HTTP
    with cookies not marked Secure.
    """
    import importlib

    import config.settings as settings_module

    monkeypatch.setenv('DEBUG', 'false')
    monkeypatch.setenv('SECRET_KEY', 'a-real-secret-for-this-test')
    monkeypatch.setenv('ALLOWED_HOSTS', 'example.com')
    monkeypatch.delenv('USE_HTTPS', raising=False)
    monkeypatch.delenv('ALLOW_INSECURE_NON_DEBUG', raising=False)
    try:
        with pytest.raises(ImproperlyConfigured, match='USE_HTTPS'):
            importlib.reload(settings_module)
    finally:
        monkeypatch.undo()
        importlib.reload(settings_module)


def test_ci_escape_hatch_allows_debug_off_without_https(monkeypatch):
    """CI genuinely runs DEBUG=False without TLS; that must stay possible, but
    only when asked for explicitly rather than by omission."""
    import importlib

    import config.settings as settings_module

    monkeypatch.setenv('DEBUG', 'false')
    monkeypatch.setenv('SECRET_KEY', 'a-real-secret-for-this-test')
    monkeypatch.setenv('ALLOWED_HOSTS', 'example.com')
    monkeypatch.delenv('USE_HTTPS', raising=False)
    monkeypatch.setenv('ALLOW_INSECURE_NON_DEBUG', 'true')
    try:
        module = importlib.reload(settings_module)
        assert module.DEBUG is False
        assert module.USE_HTTPS is False
    finally:
        monkeypatch.undo()
        importlib.reload(settings_module)


def test_whitenoise_middleware_follows_security_middleware():
    security = settings.MIDDLEWARE.index(
        'django.middleware.security.SecurityMiddleware')
    whitenoise = settings.MIDDLEWARE.index(
        'whitenoise.middleware.WhiteNoiseMiddleware')

    assert whitenoise == security + 1


def test_cors_middleware_precedes_security_middleware():
    # SECURE_SSL_REDIRECT 301s are generated by SecurityMiddleware; CORS
    # headers only reach them if CorsMiddleware sits above it.
    cors = settings.MIDDLEWARE.index(
        'corsheaders.middleware.CorsMiddleware')
    security = settings.MIDDLEWARE.index(
        'django.middleware.security.SecurityMiddleware')

    assert cors < security


def test_https_redirect_carries_cors_header_for_allowed_origin(client):
    # The behavioral contract behind the ordering test above: a filtered
    # network seeing our SSL redirect must still get CORS headers, or the
    # browser reports an opaque CORS failure instead of following it.
    with override_settings(SECURE_SSL_REDIRECT=True,
                           CORS_ALLOWED_ORIGINS=['https://stemquests.com']):
        response = client.get('/api/health/',
                              HTTP_ORIGIN='https://stemquests.com')

    assert response.status_code == 301
    assert response['Access-Control-Allow-Origin'] == 'https://stemquests.com'


def test_https_redirect_no_cors_header_for_evil_origin(client):
    with override_settings(SECURE_SSL_REDIRECT=True,
                           CORS_ALLOWED_ORIGINS=['https://stemquests.com']):
        response = client.get('/api/health/',
                              HTTP_ORIGIN='https://evil.example')

    assert response.status_code == 301
    assert 'Access-Control-Allow-Origin' not in response
