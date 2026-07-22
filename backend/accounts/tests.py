from io import BytesIO
from pathlib import Path

import pytest
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
        assert response.status_code == status.HTTP_400_BAD_REQUEST
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


def make_png(name='avatar.png'):
    # ImageField runs Pillow verification, so the payload must be a real PNG.
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
