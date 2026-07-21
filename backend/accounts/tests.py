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
        assert 'key' in response.data

    def test_login_invalid_credentials(self, api_client, user):
        response = api_client.post('/api/auth/login/', {
            'email': 'student@test.com',
            'password': 'wrongpassword'
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout(self, api_client, user):
        # Login first
        api_client.post('/api/auth/login/', {
            'email': 'student@test.com',
            'password': 'testpass123'
        })
        api_client.force_authenticate(user=user)

        response = api_client.post('/api/auth/logout/')
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

    def test_unauthenticated_profile_access(self, api_client):
        response = api_client.get('/api/auth/profile/')
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
