"""Tests for the HIBP breached-password validator (phase 73, task E4).

**No test here may touch the network.** The module-level ``no_network`` fixture
enforces that: it replaces ``core.password_validation.requests.get`` with a
double that fails the test if called, so a test that forgets to mock errors out
instead of quietly reaching api.pwnedpasswords.com. Tests that want a response
patch over it.

The two properties worth protecting are the ones a future edit could break
without any test noticing otherwise:

* only the 5-character hash prefix is ever transmitted (k-anonymity); and
* every failure path allows the password through, because a HIBP outage must
  never block a password reset.
"""

import hashlib
import logging
from unittest import mock

import pytest
import requests
from django.contrib.auth.password_validation import (
    get_default_password_validators, validate_password,
)
from django.core.exceptions import ValidationError
from django.test import override_settings

from core import password_validation as pv
from core.password_validation import PwnedPasswordValidator

# The published SHA-1 of "password". Hardcoded rather than computed so the test
# also pins the digest algorithm and the uppercase-hex form the HIBP protocol
# requires — computing it with the same code under test would prove nothing.
PASSWORD_SHA1 = '5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8'
PASSWORD_PREFIX = '5BAA6'
PASSWORD_SUFFIX = '1E4C9B93F3F0682250B6CF8331B7EE68FD8'


# Screening defaults to OFF under pytest (see HIBP_ENABLED), so any test that
# goes through Django's registered validator has to switch it back on.
ENABLED_IN_SETTINGS = override_settings(AUTH_PASSWORD_VALIDATORS=[
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'core.password_validation.PwnedPasswordValidator',
     'OPTIONS': {'enabled': True}},
])


def sha1_suffix(password: str) -> str:
    return hashlib.sha1(password.encode('utf-8')).hexdigest().upper()[5:]


def hibp_body(*entries: tuple[str, int]) -> str:
    """Build a range-API body: one ``SUFFIX:COUNT`` line per entry, CRLF."""
    return '\r\n'.join(f'{suffix}:{count}' for suffix, count in entries)


def fake_response(status_code=200, text=''):
    response = mock.Mock(spec=['status_code', 'text'])
    response.status_code = status_code
    response.text = text
    return response


@pytest.fixture(autouse=True)
def no_network():
    """Hard stop against a real HIBP call from anywhere in this module."""
    def explode(*args, **kwargs):
        raise AssertionError(
            f'test made an unmocked HTTP call: {args} {kwargs}')

    with mock.patch.object(pv.requests, 'get', side_effect=explode):
        yield


@pytest.fixture
def validator():
    # enabled=True so the suite does not depend on the HIBP_ENABLED env var.
    return PwnedPasswordValidator(enabled=True)


class TestBreachDetection:
    """(a)/(b): breached passwords rejected, clean ones accepted."""

    def test_breached_password_is_rejected(self, validator):
        body = hibp_body((PASSWORD_SUFFIX, 24_230_577))

        with mock.patch.object(pv.requests, 'get',
                               return_value=fake_response(text=body)):
            with pytest.raises(ValidationError) as exc_info:
                validator.validate('password')

        assert exc_info.value.error_list[0].code == 'password_pwned'
        # The count is surfaced so the message explains itself to the user.
        assert '24,230,577' in exc_info.value.messages[0]

    def test_clean_password_is_accepted(self, validator):
        # A body full of same-prefix hashes, none of them ours.
        body = hibp_body(('0' * 35, 12), ('A' * 35, 5), ('F' * 35, 99))

        with mock.patch.object(pv.requests, 'get',
                               return_value=fake_response(text=body)):
            assert validator.validate('a-perfectly-fine-passphrase') is None

    def test_suffix_match_is_case_insensitive(self, validator):
        """HIBP returns uppercase, but a lowercase body must still match.

        Guards the comparison itself: if the response casing ever changed and
        the match were case-sensitive, every password would silently pass.
        """
        body = hibp_body((PASSWORD_SUFFIX.lower(), 7))

        with mock.patch.object(pv.requests, 'get',
                               return_value=fake_response(text=body)):
            with pytest.raises(ValidationError):
                validator.validate('password')

    def test_zero_count_padding_entry_is_not_a_breach(self, validator):
        """Add-Padding injects decoy entries with count 0; they are not hits."""
        body = hibp_body((PASSWORD_SUFFIX, 0), ('B' * 35, 0))

        with mock.patch.object(pv.requests, 'get',
                               return_value=fake_response(text=body)):
            assert validator.validate('password') is None


class TestKAnonymity:
    """(e): the password, and even its full hash, must never be transmitted."""

    def test_only_the_five_character_prefix_is_sent(self, validator):
        with mock.patch.object(pv.requests, 'get',
                               return_value=fake_response(text='')) as get:
            validator.validate('password')

        url = get.call_args.args[0]
        assert url == f'https://api.pwnedpasswords.com/range/{PASSWORD_PREFIX}'
        # Belt and braces: no query string smuggling the rest of the digest.
        assert '?' not in url
        assert PASSWORD_SUFFIX not in repr(get.call_args)
        assert PASSWORD_SHA1 not in repr(get.call_args)

    def test_the_password_itself_never_appears_in_the_request(self, validator):
        """A distinctive plaintext, so a leak anywhere in the call is visible."""
        secret = 'zorblatt-quinceberry-9182'

        with mock.patch.object(pv.requests, 'get',
                               return_value=fake_response(text='')) as get:
            validator.validate(secret)

        serialised = repr(get.call_args)
        assert secret not in serialised
        for fragment in ('zorblatt', 'quinceberry', '9182'):
            assert fragment not in serialised
        assert sha1_suffix(secret) not in serialised

    def test_add_padding_header_is_sent(self, validator):
        """Response length would otherwise hint at how many hits the prefix had."""
        with mock.patch.object(pv.requests, 'get',
                               return_value=fake_response(text='')) as get:
            validator.validate('password')

        assert get.call_args.kwargs['headers']['Add-Padding'] == 'true'

    def test_request_uses_a_short_timeout(self, validator):
        with mock.patch.object(pv.requests, 'get',
                               return_value=fake_response(text='')) as get:
            validator.validate('password')

        assert 0 < get.call_args.kwargs['timeout'] <= 2.0


class TestFailsOpen:
    """(c)/(d): no HIBP failure may ever block a password change."""

    @pytest.mark.parametrize('exc', [
        requests.Timeout('timed out'),
        requests.ConnectionError('dns failure'),
        requests.RequestException('boom'),
        ValueError('something unexpected from the http stack'),
    ])
    def test_network_failure_allows_the_password_and_logs(
            self, validator, caplog, exc):
        caplog.set_level(logging.WARNING, logger=pv.__name__)

        with mock.patch.object(pv.requests, 'get', side_effect=exc):
            assert validator.validate('password') is None

        assert any(
            record.levelno == logging.WARNING
            and 'HIBP' in record.getMessage()
            for record in caplog.records
        ), caplog.records

    @pytest.mark.parametrize('status', [429, 500, 502, 503, 403, 404])
    def test_non_200_response_allows_the_password_and_logs(
            self, validator, caplog, status):
        caplog.set_level(logging.WARNING, logger=pv.__name__)

        # A body that *would* match, to prove the status check short-circuits
        # before the body is ever consulted.
        response = fake_response(status_code=status,
                                 text=hibp_body((PASSWORD_SUFFIX, 999)))
        with mock.patch.object(pv.requests, 'get', return_value=response):
            assert validator.validate('password') is None

        assert any(str(status) in record.getMessage()
                   for record in caplog.records), caplog.records

    def test_malformed_body_allows_the_password_and_logs(
            self, validator, caplog):
        caplog.set_level(logging.WARNING, logger=pv.__name__)

        body = f'{PASSWORD_SUFFIX}:not-a-number'
        with mock.patch.object(pv.requests, 'get',
                               return_value=fake_response(text=body)):
            assert validator.validate('password') is None

        assert caplog.records


class TestToggle:
    """The env-var off switch, for offline dev and tests."""

    def test_disabled_validator_makes_no_request(self):
        # The autouse no_network fixture is the assertion: if the disabled
        # validator called out, this test would fail.
        assert PwnedPasswordValidator(enabled=False).validate('password') is None

    def test_module_flag_is_consulted_when_no_override_is_given(
            self, monkeypatch):
        monkeypatch.setattr(pv, 'HIBP_ENABLED', False)
        assert PwnedPasswordValidator().validate('password') is None

        monkeypatch.setattr(pv, 'HIBP_ENABLED', True)
        assert PwnedPasswordValidator().enabled is True

    def test_explicit_option_wins_over_the_module_flag(self, monkeypatch):
        monkeypatch.setattr(pv, 'HIBP_ENABLED', False)
        assert PwnedPasswordValidator(enabled=True).enabled is True

    def test_screening_is_off_by_default_under_pytest(self):
        """The guarantee that no test anywhere reaches api.pwnedpasswords.com.

        Existing tests in accounts/ and courses/ exercise password change,
        reset-confirm and invite-signup with real strings; without this default
        each would make a live HIBP request. If this assertion ever fails, the
        whole suite has quietly started calling out to a third party.
        """
        assert pv.HIBP_ENABLED is False
        assert pv._running_under_pytest() is True

    def test_it_is_on_by_default_outside_a_test_run(self, monkeypatch):
        """...and production is unaffected: no pytest env vars, screening on."""
        monkeypatch.delenv('PYTEST_VERSION', raising=False)
        monkeypatch.delenv('PYTEST_CURRENT_TEST', raising=False)
        monkeypatch.delenv('HIBP_ENABLED', raising=False)

        assert pv._running_under_pytest() is False
        assert pv.config('HIBP_ENABLED',
                         default=not pv._running_under_pytest(),
                         cast=bool) is True


class TestRegistration:
    """(f): registered in settings, and reached by validate_password()."""

    def test_validator_is_registered_in_settings(self, settings):
        names = [v['NAME'] for v in settings.AUTH_PASSWORD_VALIDATORS]
        assert 'core.password_validation.PwnedPasswordValidator' in names

    def test_stock_validators_and_the_eight_char_minimum_are_kept(
            self, settings):
        """The minimum length stays at 8 by explicit decision (spec, task E)."""
        names = [v['NAME'] for v in settings.AUTH_PASSWORD_VALIDATORS]
        stock = 'django.contrib.auth.password_validation.'
        for validator in ('UserAttributeSimilarityValidator',
                          'MinimumLengthValidator',
                          'CommonPasswordValidator',
                          'NumericPasswordValidator'):
            assert stock + validator in names

        minimum = next(v for v in get_default_password_validators()
                       if type(v).__name__ == 'MinimumLengthValidator')
        assert minimum.min_length == 8

    def test_django_instantiates_it(self):
        assert any(isinstance(v, PwnedPasswordValidator)
                   for v in get_default_password_validators())

    @ENABLED_IN_SETTINGS
    def test_validate_password_rejects_a_breached_password(self):
        """End to end through Django's entry point.

        This is the path registration, password change, reset-confirm and the
        invite-signup flow in courses/views.py all funnel through, so proving
        it here covers all four.
        """
        # Long, mixed, non-numeric: passes every stock validator, so a failure
        # can only come from the HIBP check.
        candidate = 'Tr0ub4dor-and-3-horses'
        body = hibp_body((sha1_suffix(candidate), 1_337))

        with mock.patch.object(pv.requests, 'get',
                               return_value=fake_response(text=body)):
            with pytest.raises(ValidationError) as exc_info:
                validate_password(candidate)

        assert any(e.code == 'password_pwned' for e in exc_info.value.error_list)

    @ENABLED_IN_SETTINGS
    def test_validate_password_accepts_a_clean_password(self):
        candidate = 'Tr0ub4dor-and-3-horses'
        with mock.patch.object(pv.requests, 'get',
                               return_value=fake_response(text='')):
            validate_password(candidate)

    def test_help_text_is_available(self, validator):
        assert 'breach' in validator.get_help_text().lower()


@override_settings(AUTH_PASSWORD_VALIDATORS=[
    {'NAME': 'core.password_validation.PwnedPasswordValidator',
     'OPTIONS': {'timeout': 0.5, 'enabled': False}},
])
def test_options_are_passed_through_from_settings():
    """Registration OPTIONS reach __init__, so the check is tunable per env."""
    validator = next(v for v in get_default_password_validators()
                     if isinstance(v, PwnedPasswordValidator))
    assert validator.timeout == 0.5
    assert validator.enabled is False
