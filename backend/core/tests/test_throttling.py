"""Guard tests for core.throttling — the CF-Connecting-IP trust boundary.

Cloudflare overwrites CF-Connecting-IP at its edge, so on the Render service
it is the real client address and the right throttle key. Anywhere else the
header is just client input: honouring it would let a caller mint a fresh
throttle bucket per request by varying one header, which would silently
disable the anonymous brute-force guard on login/registration/password-reset.

The trust is therefore gated on settings.TRUST_CF_HEADERS (default: on
wherever DEBUG is off). These tests pin both sides of that gate, and that it
fails closed when the setting is missing entirely.

`get_ident` is exercised directly rather than through a live request cycle so
the assertions hold regardless of which throttle rates are configured (they
are all unset outside production).
"""

import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from core.throttling import (
    ClientIPAnonRateThrottle,
    ClientIPScopedRateThrottle,
    ClientIPScopedWriteRateThrottle,
    ClientIPUserRateThrottle,
)

CF_IP = '203.0.113.9'
OTHER_CF_IP = '203.0.113.77'
REMOTE_ADDR = '198.51.100.7'

ALL_THROTTLES = [
    ClientIPAnonRateThrottle,
    ClientIPUserRateThrottle,
    ClientIPScopedRateThrottle,
    ClientIPScopedWriteRateThrottle,
]


@pytest.fixture
def factory():
    return APIRequestFactory()


def make_request(factory, **extra):
    return factory.get('/api/health/', REMOTE_ADDR=REMOTE_ADDR, **extra)


# --- trust on: the header is authoritative ------------------------------


@override_settings(TRUST_CF_HEADERS=True)
def test_cf_header_is_the_ident_when_trusted(factory):
    request = make_request(factory, HTTP_CF_CONNECTING_IP=CF_IP)

    assert ClientIPAnonRateThrottle().get_ident(request) == CF_IP


@override_settings(TRUST_CF_HEADERS=True)
def test_falls_back_to_default_ident_when_header_absent(factory):
    # Local dev, tests and any non-Cloudflare host send no such header; the
    # throttle must still key on something (DRF's default = REMOTE_ADDR here).
    request = make_request(factory)

    assert ClientIPAnonRateThrottle().get_ident(request) == REMOTE_ADDR


@override_settings(TRUST_CF_HEADERS=True)
def test_blank_cf_header_falls_back_to_default_ident(factory):
    # A whitespace-only header must not become the bucket key — that would be
    # one shared bucket for every client that sends it.
    request = make_request(factory, HTTP_CF_CONNECTING_IP='   ')

    assert ClientIPAnonRateThrottle().get_ident(request) == REMOTE_ADDR


@override_settings(TRUST_CF_HEADERS=True)
def test_cf_header_is_stripped_before_use(factory):
    request = make_request(factory, HTTP_CF_CONNECTING_IP=f'  {CF_IP}  ')

    assert ClientIPAnonRateThrottle().get_ident(request) == CF_IP


@override_settings(TRUST_CF_HEADERS=True)
def test_cf_header_wins_over_forwarded_for_when_trusted(factory):
    # The whole point of the subclass: behind Cloudflare, X-Forwarded-For ends
    # in a rotating edge IP, so DRF's default ident would bucket per request.
    request = make_request(
        factory,
        HTTP_CF_CONNECTING_IP=CF_IP,
        HTTP_X_FORWARDED_FOR='70.41.3.18, 172.68.1.1',
    )

    assert ClientIPAnonRateThrottle().get_ident(request) == CF_IP


# --- trust off: the header is ignored -----------------------------------


@override_settings(TRUST_CF_HEADERS=False)
def test_cf_header_ignored_when_not_trusted(factory):
    request = make_request(factory, HTTP_CF_CONNECTING_IP=CF_IP)

    ident = ClientIPAnonRateThrottle().get_ident(request)

    assert ident == REMOTE_ADDR
    assert CF_IP not in ident


@override_settings(TRUST_CF_HEADERS=False)
def test_varying_cf_header_cannot_split_the_bucket(factory):
    # The attack this gate exists to stop: same client, different header per
    # request, therefore a fresh throttle bucket each time. Both requests must
    # land on the same ident.
    throttle = ClientIPAnonRateThrottle()
    first = throttle.get_ident(
        make_request(factory, HTTP_CF_CONNECTING_IP=CF_IP))
    second = throttle.get_ident(
        make_request(factory, HTTP_CF_CONNECTING_IP=OTHER_CF_IP))

    assert first == second == REMOTE_ADDR


@override_settings(TRUST_CF_HEADERS=False)
def test_default_ident_still_uses_forwarded_for_when_not_trusted(factory):
    # Untrusted only means "ignore CF-Connecting-IP"; DRF's own ident logic is
    # otherwise untouched.
    request = make_request(
        factory,
        HTTP_CF_CONNECTING_IP=CF_IP,
        HTTP_X_FORWARDED_FOR='70.41.3.18, 172.68.1.1',
    )

    ident = ClientIPAnonRateThrottle().get_ident(request)

    assert CF_IP not in ident
    assert '70.41.3.18' in ident


def test_ident_fails_closed_when_setting_is_missing(factory, monkeypatch):
    # getattr(..., False): if the setting is ever dropped from settings.py the
    # header must stop being honoured, not start being honoured.
    class SettingsWithoutFlag:
        pass

    monkeypatch.setattr('core.throttling.settings', SettingsWithoutFlag())
    request = make_request(factory, HTTP_CF_CONNECTING_IP=CF_IP)

    assert ClientIPAnonRateThrottle().get_ident(request) == REMOTE_ADDR


# --- every throttle class in the module shares the gate -----------------


@pytest.mark.parametrize('throttle_class', ALL_THROTTLES)
def test_all_client_ip_throttles_honour_the_gate(factory, throttle_class):
    request = make_request(factory, HTTP_CF_CONNECTING_IP=CF_IP)

    with override_settings(TRUST_CF_HEADERS=True):
        assert throttle_class().get_ident(request) == CF_IP
    with override_settings(TRUST_CF_HEADERS=False):
        assert throttle_class().get_ident(request) == REMOTE_ADDR


def test_trust_cf_headers_setting_is_a_bool():
    # cast=bool in settings.py — a stray 'false' string would be truthy and
    # silently re-enable the header everywhere.
    assert isinstance(settings.TRUST_CF_HEADERS, bool)


# --- the read/write split on the scoped write throttle ------------------


class ExplodingScopeView:
    """A view whose throttle_scope lookup fails loudly.

    Lets the safe-method exemption be asserted as a genuine short-circuit
    rather than an accidental pass through an unconfigured rate.
    """

    @property
    def throttle_scope(self):
        raise AssertionError('scope must not be consulted for safe methods')


@pytest.mark.parametrize('method', ['get', 'head', 'options'])
def test_scoped_write_throttle_exempts_safe_methods(factory, method):
    # Invites share one view: POST sends email and is rate limited, GET just
    # lists invites for the roster page and must never be throttled.
    request = getattr(factory, method)('/api/courses/TEST101/invites/')

    allowed = ClientIPScopedWriteRateThrottle().allow_request(
        request, ExplodingScopeView())

    assert allowed is True


def test_scoped_write_throttle_defers_to_super_for_writes(factory):
    request = factory.post('/api/courses/TEST101/invites/', {})

    with pytest.raises(AssertionError, match='must not be consulted'):
        ClientIPScopedWriteRateThrottle().allow_request(
            request, ExplodingScopeView())
