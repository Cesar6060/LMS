"""Phase 56: the demo sandbox write policy, end to end.

One shared account means every write is either part of the demo experience
(learning writes — allowed, pinned here so a future permission sweep can't
quietly kill the demo) or shared-surface vandalism (identity writes —
blocked with the demo_blocked contract body). Cross-app on purpose: this is
the single file that states the whole policy.
"""

from io import BytesIO

import pytest
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from accounts.models import User
from core.demo import DEMO_BLOCKED_BODY, is_demo_user
from core.throttling import ClientIPUserRateThrottle
from courses.models import (
    Course, Enrollment, Lesson, LessonQuestion, LessonQuestionChoice, Unit,
)
from discussions.models import Reply, Thread
from notifications.models import Notification
from quizzes.models import Choice, Question, Quiz


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def demo_user(settings):
    """The shared demo student, wired up as settings.DEMO_ACCOUNT_EMAIL."""
    settings.DEMO_ACCOUNT_EMAIL = 'demo@test.com'
    return User.objects.create_user(
        email='demo@test.com',
        password='testpass123',
        first_name='Jordan',
        last_name='Doe',
    )


@pytest.fixture
def demo_client(api_client, demo_user):
    api_client.force_authenticate(user=demo_user)
    return api_client


@pytest.fixture
def student():
    return User.objects.create_user(
        email='student@test.com', password='testpass123',
        first_name='Test', last_name='Student',
    )


@pytest.fixture
def instructor():
    return User.objects.create_user(
        email='instructor@test.com', password='testpass123',
        is_instructor=True,
    )


@pytest.fixture
def course(instructor):
    return Course.objects.create(
        code='DEMO101', title='Demo Course', description='The sandbox.',
        instructor=instructor,
    )


@pytest.fixture
def other_course(instructor):
    return Course.objects.create(
        code='REAL101', title='Real Course', description='Not the sandbox.',
        instructor=instructor,
    )


@pytest.fixture
def demo_enrollment(demo_user, course):
    return Enrollment.objects.create(user=demo_user, course=course)


@pytest.fixture
def lesson(course):
    unit = Unit.objects.create(course=course, title='Unit 1', order=1)
    return Lesson.objects.create(
        unit=unit, title='Lesson 1', content='# Hi', order=1,
    )


@pytest.fixture
def quiz_with_question(lesson):
    quiz = Quiz.objects.create(
        unit=lesson.unit, title='Quiz', description='q', passing_score=70,
        points=10, order=1,
    )
    question = Question.objects.create(quiz=quiz, text='2 + 2?', order=1)
    Choice.objects.create(question=question, text='4', is_correct=True, order=1)
    Choice.objects.create(question=question, text='5', is_correct=False, order=2)
    return quiz, question


@pytest.fixture
def seeded_thread(course, student):
    return Thread.objects.create(
        course=course, author=student, title='Seeded thread', content='Hello',
    )


def make_png(name='avatar.png'):
    buf = BytesIO()
    Image.new('RGB', (4, 4), 'red').save(buf, format='PNG')
    buf.seek(0)
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(name, buf.read(), content_type='image/png')


def assert_demo_blocked(response):
    """The full contract: 403 and the exact body the frontend keys on."""
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == DEMO_BLOCKED_BODY


@pytest.mark.django_db
class TestDemoBlockedWrites:
    """Identity / shared-surface writes → 403 with the demo_blocked body."""

    def test_body_shape_is_the_frontend_contract(self, demo_client):
        # Pin the exact JSON. The frontend interceptor matches
        # `code == 'demo_blocked'` on 403s; changing this shape breaks it.
        response = demo_client.patch('/api/auth/profile/', {'first_name': 'X'})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {
            'detail': 'This action is not available in the shared demo.',
            'code': 'demo_blocked',
        }

    def test_enrollment_create_blocked(self, demo_client, other_course):
        response = demo_client.post(
            '/api/courses/enrollments/',
            {'enrollment_code': other_course.enrollment_code},
        )
        assert_demo_blocked(response)
        assert not Enrollment.objects.filter(course=other_course).exists()

    def test_course_enroll_action_blocked(self, demo_client, other_course):
        # The second, parallel join path.
        response = demo_client.post(
            f'/api/courses/courses/{other_course.code}/enroll/',
            {'enrollment_code': other_course.enrollment_code},
        )
        assert_demo_blocked(response)
        assert not Enrollment.objects.filter(course=other_course).exists()

    def test_profile_update_blocked(self, demo_client, demo_user):
        for method in ('put', 'patch'):
            response = getattr(demo_client, method)(
                '/api/auth/profile/',
                {'first_name': 'Hacked', 'last_name': 'Name'},
            )
            assert_demo_blocked(response)
        demo_user.refresh_from_db()
        assert demo_user.first_name == 'Jordan'

    def test_rest_auth_user_update_blocked(self, demo_client, demo_user):
        # Same serializer, different route (dj-rest-auth's /api/auth/user/).
        for method in ('put', 'patch'):
            response = getattr(demo_client, method)(
                '/api/auth/user/',
                {'first_name': 'Hacked', 'last_name': 'Name'},
            )
            assert_demo_blocked(response)
        demo_user.refresh_from_db()
        assert demo_user.first_name == 'Jordan'

    def test_rest_auth_user_get_still_works(self, demo_client):
        response = demo_client.get('/api/auth/user/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == 'demo@test.com'

    def test_settings_update_blocked(self, demo_client):
        response = demo_client.patch('/api/auth/settings/', {'theme': 'dark'})
        assert_demo_blocked(response)

    def test_avatar_upload_blocked(self, demo_client):
        response = demo_client.post(
            '/api/auth/settings/avatar/', {'avatar': make_png()},
            format='multipart',
        )
        assert_demo_blocked(response)

    def test_avatar_delete_blocked(self, demo_client):
        response = demo_client.delete('/api/auth/settings/avatar/delete/')
        assert_demo_blocked(response)

    def test_gamification_avatar_blocked(self, demo_client):
        response = demo_client.patch(
            '/api/gamification/avatar/', {'mascot_name': 'Vandal'},
            format='json',
        )
        assert_demo_blocked(response)

    def test_thread_create_blocked(self, demo_client, course, demo_enrollment):
        response = demo_client.post(
            f'/api/courses/{course.code}/threads/',
            {'title': 'Spam', 'content': 'Spam'}, format='json',
        )
        assert_demo_blocked(response)
        assert Thread.objects.count() == 0

    def test_thread_edit_and_delete_blocked(
            self, demo_client, demo_enrollment, seeded_thread):
        response = demo_client.put(
            f'/api/threads/{seeded_thread.id}/',
            {'title': 'Defaced'}, format='json',
        )
        assert_demo_blocked(response)

        response = demo_client.delete(f'/api/threads/{seeded_thread.id}/')
        assert_demo_blocked(response)
        assert Thread.objects.filter(id=seeded_thread.id).exists()

    def test_reply_create_blocked(
            self, demo_client, demo_enrollment, seeded_thread):
        response = demo_client.post(
            f'/api/threads/{seeded_thread.id}/replies/',
            {'content': 'Spam reply'}, format='json',
        )
        assert_demo_blocked(response)
        assert Reply.objects.count() == 0

    def test_reply_edit_and_delete_blocked(
            self, demo_client, demo_enrollment, seeded_thread, student):
        reply = Reply.objects.create(
            thread=seeded_thread, author=student, content='Seeded reply',
        )
        response = demo_client.put(
            f'/api/replies/{reply.id}/', {'content': 'Defaced'}, format='json',
        )
        assert_demo_blocked(response)

        response = demo_client.delete(f'/api/replies/{reply.id}/')
        assert_demo_blocked(response)
        assert Reply.objects.filter(id=reply.id).exists()

    def test_thread_read_still_works(
            self, demo_client, course, demo_enrollment, seeded_thread):
        # Read-only discussions: browsing stays open, writing does not.
        listing = demo_client.get(f'/api/courses/{course.code}/threads/')
        assert listing.status_code == status.HTTP_200_OK
        assert len(listing.data) == 1

        detail = demo_client.get(f'/api/threads/{seeded_thread.id}/')
        assert detail.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestDemoPasswordIsFixedOnEveryPath:
    """Both password-write paths, not just the obvious one.

    Phase 42 protected password/change/; the phase-56 adversarial pass found
    password/reset/confirm/ — the sibling that calls set_password on the same
    row — completely unguarded. A valid token reaching it (log leak, future
    admin resend tool, reused SECRET_KEY) would lock every visitor out of the
    demo until an operator re-ran seed_demo_account.
    """

    def test_password_change_blocked(self, demo_client, demo_user):
        response = demo_client.post('/api/auth/password/change/', {
            'new_password1': 'BrandNewPass!123',
            'new_password2': 'BrandNewPass!123',
        })
        assert_demo_blocked(response)
        demo_user.refresh_from_db()
        assert demo_user.check_password('testpass123')

    def test_password_reset_confirm_blocked(self, api_client, demo_user):
        from allauth.account.forms import default_token_generator
        from allauth.account.utils import user_pk_to_url_str

        # A genuinely valid, server-signed token — the guard must hold even
        # when the token itself is beyond reproach.
        response = api_client.post('/api/auth/password/reset/confirm/', {
            'uid': user_pk_to_url_str(demo_user),
            'token': default_token_generator.make_token(demo_user),
            'new_password1': 'ForgedReset!123',
            'new_password2': 'ForgedReset!123',
        })
        assert_demo_blocked(response)
        demo_user.refresh_from_db()
        assert demo_user.check_password('testpass123')

    def test_reset_confirm_still_works_for_normal_users(
            self, api_client, student):
        from allauth.account.forms import default_token_generator
        from allauth.account.utils import user_pk_to_url_str

        response = api_client.post('/api/auth/password/reset/confirm/', {
            'uid': user_pk_to_url_str(student),
            'token': default_token_generator.make_token(student),
            'new_password1': 'RealReset!123',
            'new_password2': 'RealReset!123',
        })
        assert response.status_code == status.HTTP_200_OK
        student.refresh_from_db()
        assert student.check_password('RealReset!123')


@pytest.mark.django_db
class TestEnrollmentUpdateGuarded:
    """EnrollmentSerializer has no writable fields today, so PUT/PATCH was a
    silent no-op rather than a refusal — the one mutating action in the
    viewset that didn't match create/destroy. Guarded so a future writable
    field can't quietly reopen demo write access."""

    def test_demo_enrollment_update_blocked(
            self, demo_client, demo_enrollment):
        for method in ('put', 'patch'):
            response = getattr(demo_client, method)(
                f'/api/courses/enrollments/{demo_enrollment.id}/',
                {'is_active': False}, format='json',
            )
            assert_demo_blocked(response)
        demo_enrollment.refresh_from_db()
        assert demo_enrollment.is_active is True


@pytest.mark.django_db
class TestDemoEmailMatchIsCaseInsensitive:
    """allauth treats email login case-insensitively; the guard must too, so
    no future caller comparing a request-supplied address can slip past with
    a different case."""

    def test_case_variants_match(self, settings):
        from core.demo import is_demo_email

        settings.DEMO_ACCOUNT_EMAIL = 'demo@test.com'
        assert is_demo_email('demo@test.com') is True
        assert is_demo_email('DEMO@Test.COM') is True
        assert is_demo_email('  Demo@Test.com  ') is True
        assert is_demo_email('other@test.com') is False
        assert is_demo_email(None) is False


@pytest.mark.django_db
class TestDemoAllowedWrites:
    """Learning writes stay open — the demo must feel like the product.

    Each of these is a deliberate decision (phase 56 interview), pinned so a
    future lockdown sweep fails loudly instead of silently breaking the demo.
    """

    def test_lesson_progress_update_allowed(
            self, demo_client, lesson, demo_enrollment):
        response = demo_client.patch(
            f'/api/courses/lessons/{lesson.id}/progress/',
            {'video_position': 60, 'completed': True},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['completed'] is True

    def test_course_activity_ping_allowed(
            self, demo_client, course, demo_enrollment):
        response = demo_client.post(
            f'/api/courses/courses/{course.code}/activity/')
        assert response.status_code == status.HTTP_200_OK

    def test_quiz_submit_allowed(
            self, demo_client, quiz_with_question, demo_enrollment):
        quiz, question = quiz_with_question
        correct = question.choices.get(is_correct=True)
        response = demo_client.post(
            f'/api/quizzes/{quiz.id}/submit/',
            {'answers': {str(question.id): correct.id}}, format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['passed'] is True

    def test_quiz_session_allowed(
            self, demo_client, quiz_with_question, demo_enrollment):
        quiz, question = quiz_with_question
        start = demo_client.post(f'/api/quizzes/{quiz.id}/session/start/')
        assert start.status_code in (
            status.HTTP_200_OK, status.HTTP_201_CREATED)

    def test_lesson_quiz_session_allowed(
            self, demo_client, lesson, demo_enrollment):
        question = LessonQuestion.objects.create(
            lesson=lesson, text='Read it?', order=1)
        LessonQuestionChoice.objects.create(
            question=question, text='Yes', is_correct=True, order=1)
        LessonQuestionChoice.objects.create(
            question=question, text='No', is_correct=False, order=2)

        start = demo_client.post(
            f'/api/courses/lessons/{lesson.id}/quiz-session/start/')
        assert start.status_code in (
            status.HTTP_200_OK, status.HTTP_201_CREATED)

        correct = question.choices.get(is_correct=True)
        answer = demo_client.post(
            f'/api/courses/lessons/{lesson.id}/quiz-session/answer/',
            {'question_id': question.id, 'choice_id': correct.id},
            format='json',
        )
        assert answer.status_code == status.HTTP_200_OK

    def test_notification_read_marks_allowed(self, demo_client, demo_user):
        notification = Notification.objects.create(
            recipient=demo_user, type='announcement',
            title='Hi', message='Welcome',
        )
        response = demo_client.post(
            f'/api/notifications/{notification.id}/read/')
        assert response.status_code == status.HTTP_200_OK

        response = demo_client.post('/api/notifications/mark-all-read/')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestNormalUsersUnaffected:
    """The same writes keep working for a regular student."""

    def test_student_can_enroll_and_post(
            self, api_client, student, course, other_course, seeded_thread):
        api_client.force_authenticate(user=student)

        enroll = api_client.post(
            '/api/courses/enrollments/',
            {'enrollment_code': other_course.enrollment_code},
        )
        assert enroll.status_code == status.HTTP_201_CREATED

        Enrollment.objects.create(user=student, course=course)
        reply = api_client.post(
            f'/api/threads/{seeded_thread.id}/replies/',
            {'content': 'Real reply'}, format='json',
        )
        assert reply.status_code == status.HTTP_201_CREATED

    def test_student_can_edit_profile_and_settings(self, api_client, student):
        api_client.force_authenticate(user=student)

        profile = api_client.patch(
            '/api/auth/profile/', {'first_name': 'Renamed'})
        assert profile.status_code == status.HTTP_200_OK

        prefs = api_client.patch('/api/auth/settings/', {'theme': 'dark'})
        assert prefs.status_code == status.HTTP_200_OK

        upload = api_client.post(
            '/api/auth/settings/avatar/', {'avatar': make_png()},
            format='multipart',
        )
        assert upload.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestIsDemoSerializerField:
    def test_demo_login_payload_flags_demo(self, api_client, demo_user):
        response = api_client.post('/api/auth/demo-login/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['user']['is_demo'] is True

    def test_normal_user_not_flagged(self, api_client, student):
        api_client.force_authenticate(user=student)
        response = api_client.get('/api/auth/user/')
        assert response.data['is_demo'] is False

    def test_is_demo_is_read_only(self, api_client, student):
        api_client.force_authenticate(user=student)
        response = api_client.patch('/api/auth/profile/', {'is_demo': True})
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_demo'] is False


@pytest.mark.django_db
class TestRegistrationSubpathStubs:
    """With ALLOW_REGISTRATION off (the default), the sub-paths the frontend
    still calls must say 'registration is disabled', not 404."""

    def test_verify_email_stub(self, api_client):
        response = api_client.post(
            '/api/auth/registration/verify-email/', {'key': 'x'})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'disabled' in response.data['detail']

    def test_resend_email_stub(self, api_client):
        response = api_client.post(
            '/api/auth/registration/resend-email/', {'email': 'a@b.com'})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'disabled' in response.data['detail']


@pytest.mark.django_db
class TestDemoThrottleKeying:
    """Every visitor is the same user, so the 'user' throttle keys the demo
    account per client IP — one hammering visitor must not exhaust the
    shared allowance for everyone (settings comment used to claim demo
    traffic wasn't throttled at all; phase 51 changed that)."""

    def _request_for(self, user, ip):
        request = APIRequestFactory().get('/', REMOTE_ADDR=ip)
        request.user = user
        return request

    def test_demo_visitors_get_separate_buckets(self, demo_user):
        throttle = ClientIPUserRateThrottle()
        key_a = throttle.get_cache_key(
            self._request_for(demo_user, '203.0.113.1'), view=None)
        key_b = throttle.get_cache_key(
            self._request_for(demo_user, '203.0.113.2'), view=None)
        assert key_a != key_b

    def test_same_demo_visitor_shares_a_bucket(self, demo_user):
        throttle = ClientIPUserRateThrottle()
        key_a = throttle.get_cache_key(
            self._request_for(demo_user, '203.0.113.1'), view=None)
        key_b = throttle.get_cache_key(
            self._request_for(demo_user, '203.0.113.1'), view=None)
        assert key_a == key_b

    def test_normal_user_keyed_on_pk_not_ip(self, student):
        throttle = ClientIPUserRateThrottle()
        key_a = throttle.get_cache_key(
            self._request_for(student, '203.0.113.1'), view=None)
        key_b = throttle.get_cache_key(
            self._request_for(student, '203.0.113.2'), view=None)
        assert key_a == key_b
        assert str(student.pk) in key_a


@pytest.mark.django_db
class TestIsDemoUserHelper:
    def test_matches_only_the_demo_email(self, demo_user, student):
        assert is_demo_user(demo_user) is True
        assert is_demo_user(student) is False
        assert is_demo_user(None) is False
