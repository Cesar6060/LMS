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
        raise RuntimeError('connection refused')

    monkeypatch.setattr(connection, 'cursor', boom)

    response = client.get('/api/health/?deep=1')

    assert response.status_code == 503
    body = response.json()
    assert body['status'] == 'error'
    assert 'connection refused' in body['database']


def test_health_requires_no_auth():
    # DRF's global IsAuthenticated default would 403 this if health were a DRF
    # view; it is a plain Django view precisely so monitors can reach it.
    response = APIClient().get('/api/health/')

    assert response.status_code == 200


def test_health_url_name_resolves():
    assert reverse('health') == '/api/health/'


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


def test_whitenoise_middleware_follows_security_middleware():
    security = settings.MIDDLEWARE.index(
        'django.middleware.security.SecurityMiddleware')
    whitenoise = settings.MIDDLEWARE.index(
        'whitenoise.middleware.WhiteNoiseMiddleware')

    assert whitenoise == security + 1
