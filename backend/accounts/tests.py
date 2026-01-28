import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from .models import User


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
