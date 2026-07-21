"""
Guard tests for the Phase 39 R2 media storage swap.

Same through-line as test_production_settings: "inert unless its env var is
set". USE_R2 must leave local dev and CI on FileSystemStorage, and turning it
on with an incomplete R2_* set must fail at boot, not at first upload.

These tests re-execute config.settings under a patched environment (the
module, not django.conf.settings, which is immutable after setup).
"""

import importlib

import pytest
from decouple import UndefinedValueError
from django.conf import settings

R2_ENV = {
    'USE_R2': 'true',
    'R2_ACCESS_KEY_ID': 'test-key-id',
    'R2_SECRET_ACCESS_KEY': 'test-secret',
    'R2_ACCOUNT_ID': 'abc123def456',
    'R2_BUCKET_NAME': 'stemquest-media',
    'R2_PUBLIC_HOST': 'pub-test.r2.dev',
}


@pytest.fixture
def reload_settings(monkeypatch):
    """Reload config.settings with extra env vars; restore it afterwards."""
    import config.settings as settings_module

    def _reload(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return importlib.reload(settings_module)

    yield _reload

    # Undo the env patches before the final reload, so the module is restored
    # from the real environment (monkeypatch's own teardown runs too late).
    monkeypatch.undo()
    importlib.reload(settings_module)


def test_default_storage_is_filesystem():
    # The environment CI and dev run under must never point uploads at R2.
    assert settings.STORAGES['default']['BACKEND'] == (
        'django.core.files.storage.FileSystemStorage')
    assert 'OPTIONS' not in settings.STORAGES['default']


def test_use_r2_swaps_default_storage(reload_settings):
    module = reload_settings(**R2_ENV)

    default = module.STORAGES['default']
    assert default['BACKEND'] == 'storages.backends.s3.S3Storage'

    options = default['OPTIONS']
    assert options['access_key'] == 'test-key-id'
    assert options['secret_key'] == 'test-secret'
    assert options['bucket_name'] == 'stemquest-media'
    assert options['endpoint_url'] == (
        'https://abc123def456.r2.cloudflarestorage.com')
    # custom_domain is what turns .url into an absolute public r2.dev URL.
    assert options['custom_domain'] == 'pub-test.r2.dev'
    # Public bucket: no signed query strings, no ACL header (R2 rejects ACLs).
    assert options['querystring_auth'] is False
    assert options['default_acl'] is None
    assert options['file_overwrite'] is False


def test_use_r2_leaves_staticfiles_on_whitenoise(reload_settings):
    # R2 is media-only; static stays on WhiteNoise regardless of USE_R2.
    module = reload_settings(**R2_ENV)

    assert 'whitenoise' in module.STORAGES['staticfiles']['BACKEND'] or \
        'staticfiles' in module.STORAGES['staticfiles']['BACKEND']


@pytest.mark.parametrize('missing', [
    'R2_ACCESS_KEY_ID',
    'R2_SECRET_ACCESS_KEY',
    'R2_ACCOUNT_ID',
    'R2_BUCKET_NAME',
    'R2_PUBLIC_HOST',
])
def test_use_r2_missing_var_fails_fast(reload_settings, monkeypatch, missing):
    env = {k: v for k, v in R2_ENV.items() if k != missing}
    monkeypatch.delenv(missing, raising=False)

    with pytest.raises(UndefinedValueError):
        reload_settings(**env)
