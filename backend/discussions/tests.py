import pytest
from rest_framework import status
from rest_framework.test import APIClient
from accounts.models import User
from courses.models import Course, Enrollment
from notifications.models import Notification
from .models import Thread, Reply


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def instructor():
    return User.objects.create_user(
        email='instructor@test.com', password='testpass123', is_instructor=True
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        email='student@test.com', password='testpass123', is_instructor=False
    )


@pytest.fixture
def second_student():
    return User.objects.create_user(
        email='student2@test.com', password='testpass123', is_instructor=False
    )


@pytest.fixture
def outsider():
    """An enrolled-nowhere student."""
    return User.objects.create_user(
        email='outsider@test.com', password='testpass123', is_instructor=False
    )


@pytest.fixture
def course(instructor):
    return Course.objects.create(
        code='TEST101', title='Test Course', description='A test course', instructor=instructor
    )


@pytest.fixture
def enrollment(student, course):
    return Enrollment.objects.create(user=student, course=course)


@pytest.fixture
def enrollment2(second_student, course):
    return Enrollment.objects.create(user=second_student, course=course)


@pytest.fixture
def thread(course, student):
    return Thread.objects.create(
        course=course, author=student, title='How do I sprite?', content='Help please'
    )


@pytest.mark.django_db
class TestThreadList:
    def test_list_enrolled_student(self, api_client, student, course, thread, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/{course.code}/threads/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['title'] == 'How do I sprite?'

    def test_list_instructor(self, api_client, instructor, course, thread):
        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/{course.code}/threads/')
        assert response.status_code == status.HTTP_200_OK

    def test_list_not_enrolled_forbidden(self, api_client, outsider, course, thread):
        api_client.force_authenticate(user=outsider)
        response = api_client.get(f'/api/courses/{course.code}/threads/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_anonymous_unauthorized(self, api_client, course, thread):
        response = api_client.get(f'/api/courses/{course.code}/threads/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_reply_count_and_last_activity(self, api_client, student, course, thread, enrollment):
        Reply.objects.create(thread=thread, author=student, content='self reply')
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/courses/{course.code}/threads/')
        assert response.data[0]['reply_count'] == 1
        assert response.data[0]['last_activity'] is not None

    def test_ordering_pinned_then_recent_activity(
        self, api_client, instructor, student, course, enrollment
    ):
        old = Thread.objects.create(course=course, author=student, title='Old', content='x')
        recent = Thread.objects.create(course=course, author=student, title='Recent', content='x')
        pinned = Thread.objects.create(
            course=course, author=student, title='Pinned', content='x', is_pinned=True
        )
        # Give `recent` newer activity than `old`
        Reply.objects.create(thread=recent, author=student, content='bump')

        api_client.force_authenticate(user=instructor)
        response = api_client.get(f'/api/courses/{course.code}/threads/')
        titles = [t['title'] for t in response.data]
        assert titles[0] == 'Pinned'
        assert titles.index('Recent') < titles.index('Old')


@pytest.mark.django_db
class TestThreadCreate:
    def test_create_enrolled_student(self, api_client, student, course, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.post(
            f'/api/courses/{course.code}/threads/',
            {'title': 'New thread', 'content': 'body'}, format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'New thread'
        assert response.data['author']['email'] == 'student@test.com'

    def test_create_not_enrolled_forbidden(self, api_client, outsider, course):
        api_client.force_authenticate(user=outsider)
        response = api_client.post(
            f'/api/courses/{course.code}/threads/',
            {'title': 'x', 'content': 'y'}, format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestThreadDetail:
    def test_detail_includes_replies(self, api_client, student, thread, enrollment):
        Reply.objects.create(thread=thread, author=student, content='a reply')
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/threads/{thread.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['replies']) == 1
        assert response.data['replies'][0]['content'] == 'a reply'

    def test_update_author(self, api_client, student, thread, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.put(
            f'/api/threads/{thread.id}/', {'title': 'Edited', 'content': 'new'}, format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Edited'

    def test_update_other_student_forbidden(
        self, api_client, second_student, thread, enrollment2
    ):
        api_client.force_authenticate(user=second_student)
        response = api_client.put(
            f'/api/threads/{thread.id}/', {'title': 'Hacked'}, format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_instructor_forbidden(self, api_client, instructor, thread):
        # Editing is author-only, even the instructor cannot edit another's post
        api_client.force_authenticate(user=instructor)
        response = api_client.put(
            f'/api/threads/{thread.id}/', {'title': 'Mod edit'}, format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_by_author_cascades_replies(self, api_client, student, thread, enrollment):
        Reply.objects.create(thread=thread, author=student, content='will be gone')
        api_client.force_authenticate(user=student)
        response = api_client.delete(f'/api/threads/{thread.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Thread.objects.filter(id=thread.id).exists()
        assert Reply.objects.filter(thread_id=thread.id).count() == 0

    def test_delete_by_instructor_moderation(self, api_client, instructor, thread):
        api_client.force_authenticate(user=instructor)
        response = api_client.delete(f'/api/threads/{thread.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_unrelated_student_forbidden(
        self, api_client, second_student, thread, enrollment2
    ):
        api_client.force_authenticate(user=second_student)
        response = api_client.delete(f'/api/threads/{thread.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestPinLock:
    def test_pin_instructor(self, api_client, instructor, thread):
        api_client.force_authenticate(user=instructor)
        response = api_client.post(f'/api/threads/{thread.id}/pin/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_pinned'] is True

    def test_pin_student_forbidden(self, api_client, student, thread, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/threads/{thread.id}/pin/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_lock_instructor(self, api_client, instructor, thread):
        api_client.force_authenticate(user=instructor)
        response = api_client.post(f'/api/threads/{thread.id}/lock/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_locked'] is True

    def test_lock_student_forbidden(self, api_client, student, thread, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.post(f'/api/threads/{thread.id}/lock/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestReplyCreate:
    def test_reply_enrolled(self, api_client, second_student, thread, enrollment2):
        api_client.force_authenticate(user=second_student)
        response = api_client.post(
            f'/api/threads/{thread.id}/replies/', {'content': 'my reply'}, format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['content'] == 'my reply'

    def test_reply_locked_student_forbidden(
        self, api_client, second_student, thread, enrollment2
    ):
        thread.is_locked = True
        thread.save(update_fields=['is_locked'])
        api_client.force_authenticate(user=second_student)
        response = api_client.post(
            f'/api/threads/{thread.id}/replies/', {'content': 'nope'}, format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_reply_locked_instructor_allowed(self, api_client, instructor, thread):
        thread.is_locked = True
        thread.save(update_fields=['is_locked'])
        api_client.force_authenticate(user=instructor)
        response = api_client.post(
            f'/api/threads/{thread.id}/replies/', {'content': 'instructor reply'}, format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_reply_notifies_thread_author(
        self, api_client, second_student, thread, enrollment2
    ):
        api_client.force_authenticate(user=second_student)
        api_client.post(
            f'/api/threads/{thread.id}/replies/', {'content': 'ping'}, format='json'
        )
        notifs = Notification.objects.filter(recipient=thread.author, type='reply')
        assert notifs.count() == 1
        assert notifs.first().related_url == f'/courses/{thread.course.code}/discussions/{thread.id}'

    def test_no_notification_on_self_reply(self, api_client, student, thread, enrollment):
        api_client.force_authenticate(user=student)  # student is the thread author
        api_client.post(
            f'/api/threads/{thread.id}/replies/', {'content': 'my own follow-up'}, format='json'
        )
        assert Notification.objects.filter(recipient=thread.author, type='reply').count() == 0


@pytest.mark.django_db
class TestReplyEditDelete:
    def _reply(self, thread, author):
        return Reply.objects.create(thread=thread, author=author, content='original')

    def test_edit_author(self, api_client, second_student, thread, enrollment2):
        reply = self._reply(thread, second_student)
        api_client.force_authenticate(user=second_student)
        response = api_client.put(
            f'/api/replies/{reply.id}/', {'content': 'edited'}, format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['content'] == 'edited'

    def test_edit_non_author_forbidden(
        self, api_client, student, second_student, thread, enrollment, enrollment2
    ):
        reply = self._reply(thread, second_student)
        api_client.force_authenticate(user=student)
        response = api_client.put(
            f'/api/replies/{reply.id}/', {'content': 'hijack'}, format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_author(self, api_client, second_student, thread, enrollment2):
        reply = self._reply(thread, second_student)
        api_client.force_authenticate(user=second_student)
        response = api_client.delete(f'/api/replies/{reply.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Reply.objects.filter(id=reply.id).exists()

    def test_delete_instructor_moderation(
        self, api_client, instructor, second_student, thread, enrollment2
    ):
        reply = self._reply(thread, second_student)
        api_client.force_authenticate(user=instructor)
        response = api_client.delete(f'/api/replies/{reply.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_unrelated_student_forbidden(
        self, api_client, student, second_student, thread, enrollment, enrollment2
    ):
        reply = self._reply(thread, second_student)
        api_client.force_authenticate(user=student)
        response = api_client.delete(f'/api/replies/{reply.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ===========================================================================
# Phase 63 — query-count guards for the thread-detail N+1
# ===========================================================================
#
# thread_detail was a bare get_object_or_404 feeding a serializer that nests a
# UserSerializer per reply, so a 50-reply thread cost ~100 queries. The
# prefetch makes the reply fan-out constant; the one remaining per-author query
# is UserSerializer.preferences, a reverse OneToOne that is out of scope for
# this phase (see the note in views.course_threads).


def queries_against(ctx, table):
    return [q['sql'] for q in ctx.captured_queries if table in q['sql'].lower()]


@pytest.mark.django_db
class TestPhase63ThreadDetailQueryCounts:

    @pytest.fixture
    def busy_thread(self, thread, student):
        """12 replies, all by the same author.

        One author on purpose: it isolates the reply fan-out this phase fixed
        from the per-distinct-author preferences query it did not.
        """
        for i in range(12):
            Reply.objects.create(
                thread=thread, author=student, content=f'reply {i}')
        return thread

    def test_reply_authors_are_not_fetched_per_reply(
            self, api_client, student, enrollment, busy_thread):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        api_client.force_authenticate(user=student)
        with CaptureQueriesContext(connection) as ctx:
            response = api_client.get(f'/api/threads/{busy_thread.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['replies']) == 12
        assert len(queries_against(ctx, 'discussions_reply')) <= 1, (
            'replies must be prefetched, not fetched per access'
        )
        assert len(queries_against(ctx, 'accounts_user"')) <= 3, (
            'reply authors must come from the prefetch, not one query each'
        )

    def test_adding_replies_does_not_add_queries(
            self, api_client, student, enrollment, busy_thread):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        api_client.force_authenticate(user=student)
        url = f'/api/threads/{busy_thread.id}/'
        with CaptureQueriesContext(connection) as small:
            api_client.get(url)

        for i in range(100, 112):
            Reply.objects.create(
                thread=busy_thread, author=student, content=f'more {i}')

        with CaptureQueriesContext(connection) as big:
            response = api_client.get(url)
        assert len(response.data['replies']) == 24

        assert len(big.captured_queries) == len(small.captured_queries), (
            f'{len(small.captured_queries)} queries for 12 replies vs '
            f'{len(big.captured_queries)} for 24 — still scaling'
        )

    def test_replies_are_unchanged(
            self, api_client, student, enrollment, busy_thread):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/threads/{busy_thread.id}/')

        replies = response.data['replies']
        assert [r['content'] for r in replies] == [
            f'reply {i}' for i in range(12)]
        assert all(r['author']['email'] == 'student@test.com' for r in replies)

    def test_thread_with_no_replies(
            self, api_client, student, enrollment, thread):
        api_client.force_authenticate(user=student)
        response = api_client.get(f'/api/threads/{thread.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['replies'] == []

    def test_missing_thread_still_404s(self, api_client, student, enrollment):
        """The queryset form of get_object_or_404 must not change this."""
        api_client.force_authenticate(user=student)
        assert api_client.get('/api/threads/999999/').status_code == (
            status.HTTP_404_NOT_FOUND)

    def test_pin_and_lock_still_work(
            self, api_client, instructor, busy_thread):
        api_client.force_authenticate(user=instructor)

        pinned = api_client.post(f'/api/threads/{busy_thread.id}/pin/')
        assert pinned.status_code == status.HTTP_200_OK
        assert pinned.data['is_pinned'] is True
        assert len(pinned.data['replies']) == 12

        locked = api_client.post(f'/api/threads/{busy_thread.id}/lock/')
        assert locked.status_code == status.HTTP_200_OK
        assert locked.data['is_locked'] is True
