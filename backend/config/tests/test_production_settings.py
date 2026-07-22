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
    assert response.json() == {'status': 'ok', 'database': 'ok'}


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
    monkeypatch.setenv('SENTRY_DEBUG_ENDPOINT', 'true')

    with pytest.raises(ZeroDivisionError):
        client.get('/api/sentry-debug/')


def test_sentry_debug_requires_no_auth(monkeypatch):
    # Plain Django view like health: an anonymous curl must reach the crash
    # (not a DRF 401/403), since the prod smoke test is an unauthenticated curl.
    monkeypatch.setenv('SENTRY_DEBUG_ENDPOINT', 'true')

    with pytest.raises(ZeroDivisionError):
        APIClient().get('/api/sentry-debug/')


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


def test_whitenoise_middleware_follows_security_middleware():
    security = settings.MIDDLEWARE.index(
        'django.middleware.security.SecurityMiddleware')
    whitenoise = settings.MIDDLEWARE.index(
        'whitenoise.middleware.WhiteNoiseMiddleware')

    assert whitenoise == security + 1
