import re
from io import BytesIO
from pathlib import Path

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient
from .models import User, UserPreferences


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(
        email='student@test.com',
        password='testpass123',
        first_name='Test',
        last_name='Student'
    )


@pytest.fixture
def instructor():
    return User.objects.create_user(
        email='instructor@test.com',
        password='testpass123',
        first_name='Test',
        last_name='Instructor',
        is_instructor=True
    )


@pytest.mark.django_db
class TestUserModel:
    def test_create_user(self):
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        assert user.email == 'test@example.com'
        assert user.check_password('testpass123')
        assert not user.is_instructor
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_instructor(self):
        user = User.objects.create_user(
            email='instructor@example.com',
            password='testpass123',
            is_instructor=True
        )
        assert user.is_instructor

    def test_create_superuser(self):
        user = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )
        assert user.is_staff
        assert user.is_superuser

    def test_user_str(self):
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        assert str(user) == 'test@example.com'

    def test_get_full_name(self):
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        assert user.get_full_name() == 'John Doe'

    def test_get_short_name(self):
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='John'
        )
        assert user.get_short_name() == 'John'


@pytest.mark.django_db
class TestAuthEndpoints:
    def test_login(self, api_client, user):
        response = api_client.post('/api/auth/login/', {
            'email': 'student@test.com',
            'password': 'testpass123'
        })
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_login_invalid_credentials(self, api_client, user):
        response = api_client.post('/api/auth/login/', {
            'email': 'student@test.com',
            'password': 'wrongpassword'
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout(self, api_client, user):
        login = api_client.post('/api/auth/login/', {
            'email': 'student@test.com',
            'password': 'testpass123'
        })
        api_client.force_authenticate(user=user)

        # Under JWT, logout needs the refresh token so it can blacklist it.
        response = api_client.post(
            '/api/auth/logout/', {'refresh': login.data['refresh']})
        assert response.status_code == status.HTTP_200_OK

    def test_get_user_profile(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.get('/api/auth/profile/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == 'student@test.com'

    def test_update_user_profile(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.patch('/api/auth/profile/', {
            'first_name': 'Updated'
        })
        assert response.status_code == status.HTTP_200_OK
        assert response.data['first_name'] == 'Updated'

    def test_profile_update_cannot_self_promote_to_instructor(self, api_client, user):
        """A student cannot flip is_instructor via the profile endpoint — the
        field is read-only, so the write is silently ignored, not honored."""
        assert user.is_instructor is False
        api_client.force_authenticate(user=user)
        response = api_client.patch('/api/auth/profile/', {
            'is_instructor': True,
        })
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_instructor'] is False
        user.refresh_from_db()
        assert user.is_instructor is False

    def test_unauthenticated_profile_access(self, api_client):
        response = api_client.get('/api/auth/profile/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_demo_account_password_change_blocked(self, api_client, settings):
        """The published shared demo account cannot have its password changed,
        so one visitor can't lock out the rest."""
        settings.DEMO_ACCOUNT_EMAIL = 'demo@test.com'
        demo = User.objects.create_user(email='demo@test.com', password='testpass123')
        api_client.force_authenticate(user=demo)
        response = api_client.post('/api/auth/password/change/', {
            'new_password1': 'BrandNewPass!123',
            'new_password2': 'BrandNewPass!123',
        })
        # Phase 56 unified the denial onto the demo_blocked 403 contract
        # (was a 400 validation error) so the frontend shows the same
        # friendly message here as on every other blocked demo write.
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()['code'] == 'demo_blocked'
        demo.refresh_from_db()
        assert demo.check_password('testpass123')

    def test_regular_user_password_change_allowed(self, api_client, user, settings):
        """Non-demo users change their password normally."""
        settings.DEMO_ACCOUNT_EMAIL = 'demo@test.com'
        api_client.force_authenticate(user=user)
        response = api_client.post('/api/auth/password/change/', {
            'new_password1': 'BrandNewPass!123',
            'new_password2': 'BrandNewPass!123',
        })
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.check_password('BrandNewPass!123')

    def test_registration_disabled_by_default(self, api_client):
        """With ALLOW_REGISTRATION off (the demo default), signup is refused and
        no account is created regardless of payload."""
        response = api_client.post('/api/auth/registration/', {
            'email': 'attacker@test.com',
            'password1': 'S3curePass!123',
            'password2': 'S3curePass!123',
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not User.objects.filter(email='attacker@test.com').exists()

    def test_registration_cannot_grant_instructor(self, api_client):
        """Even the disabled endpoint never honors an is_instructor payload."""
        response = api_client.post('/api/auth/registration/', {
            'email': 'attacker2@test.com',
            'password1': 'S3curePass!123',
            'password2': 'S3curePass!123',
            'is_instructor': True,
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not User.objects.filter(email='attacker2@test.com').exists()


@pytest.mark.django_db
class TestJWTAuth:
    """Phase 43: the JWT lifecycle — pair issuance, Bearer auth, refresh
    rotation, logout blacklisting, and expiry. These replace the old
    non-expiring DRF token scheme, so the tests also pin down that the old
    `Token <key>` header and `key` response field are gone."""

    def login(self, api_client):
        return api_client.post('/api/auth/login/', {
            'email': 'student@test.com',
            'password': 'testpass123',
        })

    def test_login_returns_jwt_pair_and_user_not_key(self, api_client, user):
        response = self.login(api_client)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['access']
        assert response.data['refresh']
        assert 'key' not in response.data
        assert response.data['user']['email'] == 'student@test.com'

    def test_bearer_access_token_authenticates(self, api_client, user):
        access = self.login(api_client).data['access']

        response = api_client.get(
            '/api/auth/profile/', HTTP_AUTHORIZATION=f'Bearer {access}')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == 'student@test.com'

    def test_old_drf_token_header_rejected(self, api_client, user):
        # The authtoken app is gone; a legacy `Token <key>` header must never
        # authenticate anyone again.
        response = api_client.get(
            '/api/auth/profile/',
            HTTP_AUTHORIZATION='Token 0123456789abcdef0123456789abcdef01234567')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_issues_new_rotated_pair(self, api_client, user):
        refresh = self.login(api_client).data['refresh']

        response = api_client.post(
            '/api/auth/token/refresh/', {'refresh': refresh})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['access']
        # ROTATE_REFRESH_TOKENS: the response carries a fresh refresh token.
        assert response.data['refresh'] != refresh

    def test_used_refresh_token_is_blacklisted_after_rotation(
            self, api_client, user):
        refresh = self.login(api_client).data['refresh']
        api_client.post('/api/auth/token/refresh/', {'refresh': refresh})

        reuse = api_client.post(
            '/api/auth/token/refresh/', {'refresh': refresh})

        assert reuse.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_blacklists_refresh_token(self, api_client, user):
        data = self.login(api_client).data

        response = api_client.post(
            '/api/auth/logout/',
            {'refresh': data['refresh']},
            HTTP_AUTHORIZATION=f"Bearer {data['access']}")
        assert response.status_code == status.HTTP_200_OK

        reuse = api_client.post(
            '/api/auth/token/refresh/', {'refresh': data['refresh']})
        assert reuse.status_code == status.HTTP_401_UNAUTHORIZED

    def test_expired_access_token_rejected(self, api_client, user):
        from datetime import timedelta
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken.for_user(user)
        token.set_exp(lifetime=-timedelta(minutes=1))

        response = api_client.get(
            '/api/auth/profile/', HTTP_AUTHORIZATION=f'Bearer {token}')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.fixture
def demo_user(settings):
    """The shared demo student, wired up as settings.DEMO_ACCOUNT_EMAIL."""
    settings.DEMO_ACCOUNT_EMAIL = 'demo@test.com'
    return User.objects.create_user(
        email='demo@test.com',
        password='not-used-by-demo-login',
        first_name='Jordan',
        last_name='Doe',
    )


@pytest.mark.django_db
class TestDemoLogin:
    """Phase 44: POST /api/auth/demo-login/ issues a JWT pair for the shared
    demo student server-side — no password ever crosses the wire — with the
    same response shape as dj-rest-auth login."""

    def test_returns_jwt_pair_and_demo_user(self, api_client, demo_user):
        response = api_client.post('/api/auth/demo-login/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['access']
        assert response.data['refresh']
        assert response.data['user']['email'] == 'demo@test.com'

        # The issued access token authenticates the standard user endpoint.
        me = api_client.get(
            '/api/auth/user/',
            HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        assert me.status_code == status.HTTP_200_OK
        assert me.data['email'] == 'demo@test.com'

    def test_demo_user_is_student(self, api_client, demo_user):
        response = api_client.post('/api/auth/demo-login/')

        assert response.data['user']['is_instructor'] is False

    def test_404_when_demo_user_missing(self, api_client, settings):
        settings.DEMO_ACCOUNT_EMAIL = 'demo@test.com'

        response = api_client.post('/api/auth/demo-login/')

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'access' not in response.data

    def test_404_when_demo_user_inactive(self, api_client, demo_user):
        demo_user.is_active = False
        demo_user.save(update_fields=['is_active'])

        response = api_client.post('/api/auth/demo-login/')

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'access' not in response.data

    def test_get_not_allowed(self, api_client, demo_user):
        response = api_client.get('/api/auth/demo-login/')

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_requests_over_rate_throttled(
            self, api_client, demo_user, monkeypatch):
        from django.core.cache import caches
        from rest_framework.throttling import ScopedRateThrottle

        # DRF snapshots DEFAULT_THROTTLE_RATES onto the throttle class at
        # import, so override_settings(REST_FRAMEWORK=...) can't reach it —
        # patch the class attribute instead (equivalent to booting with
        # THROTTLE_DEMO_LOGIN=3/min).
        monkeypatch.setattr(
            ScopedRateThrottle, 'THROTTLE_RATES', {'demo_login': '3/min'})
        # Phase 63: the 'throttle' alias, not the default cache. Throttle
        # counters moved to their own file-backed cache so both gunicorn
        # workers share them; clearing the default cache no longer reaches
        # them, and because that cache is on disk, history would otherwise
        # survive not just other tests but entire pytest sessions.
        caches['throttle'].clear()
        try:
            for _ in range(3):
                ok = api_client.post('/api/auth/demo-login/')
                assert ok.status_code == status.HTTP_200_OK

            throttled = api_client.post('/api/auth/demo-login/')
            assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        finally:
            # Don't leak throttle history into other tests.
            caches['throttle'].clear()


def make_png(name='avatar.png'):
    # The payload must be a real PNG because upload_avatar runs an explicit
    # Pillow verify() (phase 55, A3) — NOT because of ImageField, whose
    # validation never runs: save() skips full_clean().
    buf = BytesIO()
    Image.new('RGB', (1, 1), 'red').save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


@pytest.mark.django_db
class TestAvatarEndpoints:
    """Upload/delete coverage added in Phase 39, when media moved to R2 and
    these endpoints became load-bearing. Tests run against FileSystemStorage
    in a temp MEDIA_ROOT — the R2 swap itself is covered by the settings
    tests in config/tests/test_storage_settings.py."""

    @pytest.fixture(autouse=True)
    def media_tmp(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path

    def test_upload_avatar(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            '/api/auth/settings/avatar/',
            {'avatar': make_png()},
            format='multipart',
        )

        assert response.status_code == status.HTTP_200_OK
        # Serializer must return an absolute URL (prod: the r2.dev host).
        assert response.data['avatar_url'].startswith('http://testserver/')
        assert '/avatars/' in response.data['avatar_url']

    def test_replace_avatar_deletes_old_file(self, api_client, user):
        api_client.force_authenticate(user=user)

        api_client.post(
            '/api/auth/settings/avatar/',
            {'avatar': make_png('first.png')},
            format='multipart',
        )
        old_path = Path(
            UserPreferences.objects.get(user=user).avatar.path)
        assert old_path.exists()

        response = api_client.post(
            '/api/auth/settings/avatar/',
            {'avatar': make_png('second.png')},
            format='multipart',
        )

        assert response.status_code == status.HTTP_200_OK
        assert not old_path.exists()
        new_path = Path(
            UserPreferences.objects.get(user=user).avatar.path)
        assert new_path.exists()

    def test_upload_without_file_400(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            '/api/auth/settings/avatar/', {}, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_oversized_avatar_rejected(self, api_client, user, settings):
        """An avatar over the size cap is refused before it's stored, so a
        visitor can't push huge files into media storage."""
        settings.AVATAR_MAX_UPLOAD_BYTES = 1024  # 1 KB cap for the test
        api_client.force_authenticate(user=user)
        big = SimpleUploadedFile(
            'big.png', b'\x89PNG\r\n' + b'0' * 4096, content_type='image/png')

        response = api_client.post(
            '/api/auth/settings/avatar/',
            {'avatar': big},
            format='multipart',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not UserPreferences.objects.get(user=user).avatar

    def test_valid_png_avatar_accepted(self, api_client, user):
        """The hardening below must not block real images: a genuine PNG still
        uploads and is stored."""
        api_client.force_authenticate(user=user)

        response = api_client.post(
            '/api/auth/settings/avatar/',
            {'avatar': make_png('portrait.png')},
            format='multipart',
        )

        assert response.status_code == status.HTTP_200_OK
        stored = UserPreferences.objects.get(user=user).avatar
        assert stored
        assert Path(stored.path).exists()

    def test_svg_avatar_rejected(self, api_client, user):
        """SVG can carry inline <script>, and media is same-origin under DEBUG,
        so it must never reach storage — extension allowlist excludes it."""
        api_client.force_authenticate(user=user)
        svg = SimpleUploadedFile(
            'avatar.svg',
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            content_type='image/svg+xml',
        )

        response = api_client.post(
            '/api/auth/settings/avatar/',
            {'avatar': svg},
            format='multipart',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not UserPreferences.objects.get(user=user).avatar

    def test_html_disguised_as_png_rejected(self, api_client, user):
        """An HTML payload renamed to .png passes the extension and content-type
        checks, so the Pillow verify() pass is what has to catch it."""
        api_client.force_authenticate(user=user)
        disguised = SimpleUploadedFile(
            'avatar.png',
            b'<html><body><script>alert(document.cookie)</script></body></html>',
            content_type='image/png',
        )

        response = api_client.post(
            '/api/auth/settings/avatar/',
            {'avatar': disguised},
            format='multipart',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not UserPreferences.objects.get(user=user).avatar

    # -- Phase 55 review: format confusion -----------------------------------
    # Found by the adversarial-tester. `Image.open(...).verify()` accepts
    # ANYTHING Pillow can decode, so before the format pin these all uploaded
    # successfully despite the extension allowlist. The allowlist exists to
    # bound which Pillow decoders untrusted bytes reach — the less-common
    # codecs are where most of the CVEs behind this phase's Pillow bump live —
    # so "it's a valid image of some kind" is not the bar.

    @pytest.mark.parametrize('pillow_format', ['TIFF', 'BMP', 'PPM'])
    def test_other_image_format_disguised_as_png_rejected(
        self, api_client, user, pillow_format
    ):
        api_client.force_authenticate(user=user)
        buf = BytesIO()
        Image.new('RGB', (4, 4), 'blue').save(buf, format=pillow_format)
        disguised = SimpleUploadedFile(
            'avatar.png', buf.getvalue(), content_type='image/png',
        )

        response = api_client.post(
            '/api/auth/settings/avatar/',
            {'avatar': disguised},
            format='multipart',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not UserPreferences.objects.get(user=user).avatar

    def test_real_jpeg_named_png_rejected(self, api_client, user):
        """Even an allowed *format* must match its declared extension."""
        api_client.force_authenticate(user=user)
        buf = BytesIO()
        Image.new('RGB', (4, 4), 'green').save(buf, format='JPEG')
        mismatched = SimpleUploadedFile(
            'avatar.png', buf.getvalue(), content_type='image/png',
        )

        response = api_client.post(
            '/api/auth/settings/avatar/',
            {'avatar': mismatched},
            format='multipart',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_real_jpeg_named_jpg_accepted(self, api_client, user):
        """...and the matching pair still works, so the pin isn't over-tight."""
        api_client.force_authenticate(user=user)
        buf = BytesIO()
        Image.new('RGB', (4, 4), 'green').save(buf, format='JPEG')
        good = SimpleUploadedFile(
            'avatar.jpg', buf.getvalue(), content_type='image/jpeg',
        )

        response = api_client.post(
            '/api/auth/settings/avatar/',
            {'avatar': good},
            format='multipart',
        )

        assert response.status_code == status.HTTP_200_OK
        assert UserPreferences.objects.get(user=user).avatar

    @pytest.mark.parametrize('hostile_name', [
        '../../../evil.png',
        '....//....//evil.png',
        '/etc/evil.png',
    ])
    def test_path_traversal_filename_is_sanitized(
        self, api_client, user, hostile_name
    ):
        """Django's storage layer strips the path; pin it so a future custom
        upload_to or storage backend can't quietly reintroduce an escape."""
        api_client.force_authenticate(user=user)
        buf = BytesIO()
        Image.new('RGB', (1, 1), 'red').save(buf, format='PNG')
        traversal = SimpleUploadedFile(
            hostile_name, buf.getvalue(), content_type='image/png',
        )

        response = api_client.post(
            '/api/auth/settings/avatar/',
            {'avatar': traversal},
            format='multipart',
        )

        assert response.status_code == status.HTTP_200_OK
        stored = UserPreferences.objects.get(user=user).avatar.name
        assert '..' not in stored
        assert stored.startswith('avatars/')

    def test_delete_avatar(self, api_client, user):
        api_client.force_authenticate(user=user)
        api_client.post(
            '/api/auth/settings/avatar/',
            {'avatar': make_png()},
            format='multipart',
        )
        stored = Path(
            UserPreferences.objects.get(user=user).avatar.path)

        response = api_client.delete('/api/auth/settings/avatar/delete/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['avatar_url'] is None
        assert not stored.exists()

    def test_upload_unauthenticated_401(self, api_client):
        response = api_client.post(
            '/api/auth/settings/avatar/',
            {'avatar': make_png()},
            format='multipart',
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPasswordResetEmail:
    """First mail.outbox coverage in the repo (Phase 47). The reset email must
    link to the frontend's /reset-password page with allauth-compatible
    uid/token — exactly what /api/auth/password/reset/confirm/ decodes."""

    RESET_URL = '/api/auth/password/reset/'

    def test_reset_request_sends_branded_email(self, api_client, user, settings):
        response = api_client.post(self.RESET_URL, {'email': user.email})

        assert response.status_code == status.HTTP_200_OK
        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == [user.email]
        assert message.subject == 'Reset your STEM Quest password'
        assert f'{settings.FRONTEND_URL}/reset-password?uid=' in message.body
        assert 'token=' in message.body

    def test_reset_round_trip(self, api_client, user):
        api_client.post(self.RESET_URL, {'email': user.email})

        match = re.search(
            r'/reset-password\?uid=([^&\s]+)&token=([^\s]+)',
            mail.outbox[0].body)
        assert match, 'reset link not found in email body'
        uid, token = match.groups()

        confirm = api_client.post('/api/auth/password/reset/confirm/', {
            'uid': uid,
            'token': token,
            'new_password1': 'fresh-Pass-9021',
            'new_password2': 'fresh-Pass-9021',
        })
        assert confirm.status_code == status.HTTP_200_OK

        login = api_client.post('/api/auth/login/', {
            'email': user.email, 'password': 'fresh-Pass-9021'})
        assert login.status_code == status.HTTP_200_OK
        assert 'access' in login.data

    def test_unknown_email_200_and_no_email(self, api_client):
        response = api_client.post(
            self.RESET_URL, {'email': 'nobody@test.com'})

        # 200 with an empty outbox: no account enumeration.
        assert response.status_code == status.HTTP_200_OK
        assert len(mail.outbox) == 0

    def test_demo_account_never_gets_reset_email(self, api_client, demo_user):
        response = api_client.post(self.RESET_URL, {'email': demo_user.email})

        # Same 200 as the unknown-email case, but nothing is sent — the demo
        # mailbox isn't ours and the password is operator-managed.
        assert response.status_code == status.HTTP_200_OK
        assert len(mail.outbox) == 0

    def test_requests_over_rate_throttled(self, api_client, user, monkeypatch):
        from django.core.cache import caches
        from rest_framework.throttling import ScopedRateThrottle

        # Same pattern as the demo_login throttle test: DRF snapshots
        # DEFAULT_THROTTLE_RATES onto the class at import, so patch the class
        # attribute (equivalent to booting with THROTTLE_PASSWORD_RESET=3/min).
        monkeypatch.setattr(
            ScopedRateThrottle, 'THROTTLE_RATES', {'password_reset': '3/min'})
        caches['throttle'].clear()
        try:
            for _ in range(3):
                ok = api_client.post(self.RESET_URL, {'email': user.email})
                assert ok.status_code == status.HTTP_200_OK

            throttled = api_client.post(self.RESET_URL, {'email': user.email})
            assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        finally:
            caches['throttle'].clear()

    def test_throttle_keys_on_cf_connecting_ip(
            self, api_client, user, monkeypatch, settings):
        """Cloudflare's rotating edge IP must not defeat the throttle.

        Production sits behind Cloudflare, which appends a per-request edge
        IP to X-Forwarded-For — under DRF's default ident every request got
        a fresh bucket and no rate limit ever fired. The fix keys the bucket
        on CF-Connecting-IP, so requests from one client throttle together
        no matter what the rest of the chain looks like.

        Phase 55 (A5) gated that behind TRUST_CF_HEADERS, which defaults off
        in dev/tests — this test is asserting the *production* configuration,
        so it opts in explicitly. The off case is covered in
        core/tests/test_throttling.py.
        """
        from django.core.cache import caches
        from rest_framework.throttling import ScopedRateThrottle

        settings.TRUST_CF_HEADERS = True
        monkeypatch.setattr(
            ScopedRateThrottle, 'THROTTLE_RATES', {'password_reset': '3/min'})
        caches['throttle'].clear()
        try:
            for i in range(3):
                ok = api_client.post(
                    self.RESET_URL, {'email': user.email},
                    HTTP_CF_CONNECTING_IP='203.0.113.50',
                    HTTP_X_FORWARDED_FOR=f'203.0.113.50, 172.71.0.{i}')
                assert ok.status_code == status.HTTP_200_OK

            throttled = api_client.post(
                self.RESET_URL, {'email': user.email},
                HTTP_CF_CONNECTING_IP='203.0.113.50',
                HTTP_X_FORWARDED_FOR='203.0.113.50, 172.71.0.99')
            assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS

            # A different client (different CF-Connecting-IP) has its own
            # bucket and is not caught by the first client's limit.
            other = api_client.post(
                self.RESET_URL, {'email': user.email},
                HTTP_CF_CONNECTING_IP='198.51.100.7',
                HTTP_X_FORWARDED_FOR='198.51.100.7, 172.71.0.99')
            assert other.status_code == status.HTTP_200_OK
        finally:
            caches['throttle'].clear()


# ---------------------------------------------------------------------------
# Phase 73: brute-force ceilings on login and password-reset-confirm
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPhase73AuthThrottles:
    """Login and reset-confirm had no scoped throttle before phase 73.

    Both are mounted as re_path shadows with an optional trailing slash. That
    detail is the whole test: dj-rest-auth registers its own views as
    r'login/?$', so a path() shadow captures only 'login/' and a caller who
    drops the slash reaches the original, unthrottled view. Each throttle is
    therefore asserted on both spellings — the no-slash case is the one that
    silently regresses.
    """

    LOGIN_SLASH = '/api/auth/login/'
    LOGIN_BARE = '/api/auth/login'
    CONFIRM_SLASH = '/api/auth/password/reset/confirm/'
    CONFIRM_BARE = '/api/auth/password/reset/confirm'

    def _set_rate(self, monkeypatch, scope, rate):
        from rest_framework.throttling import ScopedRateThrottle

        monkeypatch.setattr(
            ScopedRateThrottle, 'THROTTLE_RATES', {scope: rate})

    def test_login_shadow_is_mounted_on_both_spellings(self):
        from django.urls import resolve

        from .views import ThrottledLoginView

        for url in (self.LOGIN_SLASH, self.LOGIN_BARE):
            assert resolve(url).func.view_class is ThrottledLoginView, url

    def test_reset_confirm_shadow_is_mounted_on_both_spellings(self):
        from django.urls import resolve

        from .views import ThrottledPasswordResetConfirmView

        for url in (self.CONFIRM_SLASH, self.CONFIRM_BARE):
            assert resolve(url).func.view_class is (
                ThrottledPasswordResetConfirmView), url

    @pytest.mark.parametrize('url_attr', ['LOGIN_SLASH', 'LOGIN_BARE'])
    @pytest.mark.throttled
    def test_failed_logins_are_throttled(
            self, api_client, user, monkeypatch, url_attr):
        from django.core.cache import caches

        self._set_rate(monkeypatch, 'login', '3/min')
        caches['throttle'].clear()
        url = getattr(self, url_attr)
        try:
            for _ in range(3):
                denied = api_client.post(
                    url, {'email': user.email, 'password': 'wrong-password'},
                    format='json')
                assert denied.status_code == status.HTTP_400_BAD_REQUEST

            throttled = api_client.post(
                url, {'email': user.email, 'password': 'wrong-password'},
                format='json')
            assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        finally:
            caches['throttle'].clear()

    @pytest.mark.throttled
    def test_login_throttle_also_stops_correct_credentials(
            self, api_client, user, monkeypatch):
        """The bucket counts attempts, not failures.

        A limiter that only counted failures would let an attacker who guesses
        right on attempt 500 through, having been rate limited for none of it.
        """
        from django.core.cache import caches

        self._set_rate(monkeypatch, 'login', '2/min')
        caches['throttle'].clear()
        try:
            for _ in range(2):
                api_client.post(
                    self.LOGIN_SLASH,
                    {'email': user.email, 'password': 'wrong-password'},
                    format='json')

            correct = api_client.post(
                self.LOGIN_SLASH,
                {'email': user.email, 'password': 'testpass123'},
                format='json')
            assert correct.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        finally:
            caches['throttle'].clear()

    @pytest.mark.parametrize('url_attr', ['CONFIRM_SLASH', 'CONFIRM_BARE'])
    @pytest.mark.throttled
    def test_reset_confirm_token_guessing_is_throttled(
            self, api_client, monkeypatch, url_attr):
        from django.core.cache import caches

        self._set_rate(monkeypatch, 'password_reset_confirm', '3/hour')
        caches['throttle'].clear()
        url = getattr(self, url_attr)
        body = {
            'uid': 'bogus-uid',
            'token': 'bogus-token',
            'new_password1': 'Str0ng-Passphrase-9182',
            'new_password2': 'Str0ng-Passphrase-9182',
        }
        try:
            for _ in range(3):
                rejected = api_client.post(url, body, format='json')
                assert rejected.status_code == status.HTTP_400_BAD_REQUEST

            throttled = api_client.post(url, body, format='json')
            assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        finally:
            caches['throttle'].clear()

    def test_scoped_views_keep_the_global_ceilings(self):
        """A scoped throttle listed alone replaces DEFAULT_THROTTLE_CLASSES.

        Every view here must name the globals too, or the scoped rate becomes
        the only limit on the endpoint.
        """
        from core.throttling import (
            ClientIPAnonRateThrottle, ClientIPUserRateThrottle,
        )

        from .views import (
            ThrottledLoginView, ThrottledPasswordResetConfirmView,
            ThrottledPasswordResetView, demo_login,
        )

        scoped_views = [
            ThrottledLoginView, ThrottledPasswordResetView,
            ThrottledPasswordResetConfirmView, demo_login.cls,
        ]
        for view in scoped_views:
            classes = view.throttle_classes
            assert ClientIPAnonRateThrottle in classes, view.__name__
            assert ClientIPUserRateThrottle in classes, view.__name__
