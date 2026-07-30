from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Count, Max
from django.db.models.functions import Coalesce

from core.demo import require_not_demo
from courses.models import Course
from courses.permissions import is_course_instructor, can_access_course as can_access
from notifications.models import Notification
from .models import Thread, Reply
from .serializers import (
    ThreadListSerializer, ThreadDetailSerializer, ThreadCreateSerializer,
    ReplySerializer, ReplyCreateSerializer,
)


# ==================== Thread Views ====================

def thread_detail_queryset():
    """Queryset for every view that renders `ThreadDetailSerializer`.

    That serializer nests `replies` (each with a `UserSerializer(author)`) plus
    `course.code` and its own `author`, so a bare `Thread.objects` render costs
    ~2 queries per reply. The prefetch collapses the reply authors into one
    query and, because a forward-FK prefetch reuses a single instance per
    distinct user, the (out-of-scope) `UserSerializer.preferences` lookup drops
    from one per reply to one per distinct author.

    `get_object_or_404` still 404s normally: it calls `.get()` on this
    queryset, and `DoesNotExist` is what it converts to `Http404`.
    """
    return Thread.objects.select_related('course', 'author').prefetch_related('replies__author')


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def course_threads(request, course_code):
    """List threads for a course or create a new thread."""
    course = get_object_or_404(Course, code=course_code)

    if not can_access(request.user, course):
        return Response(
            {'detail': 'You must be enrolled or the instructor to access discussions.'},
            status=status.HTTP_403_FORBIDDEN
        )

    if request.method == 'GET':
        # Already flat: `reply_count` / `last_activity` are annotated (no
        # per-thread aggregate) and the author FK is joined, so this costs a
        # constant number of queries in the thread count. The one remaining
        # per-thread query is the reverse OneToOne `UserSerializer.preferences`
        # (accounts/serializers.py:46), which that serializer resolves lazily
        # for every user it renders across 7 nesting sites. Fixing it belongs
        # in `accounts/`, not here — patching only this call site would leave
        # the other six — so it is deliberately left in place (phase 63,
        # "Out of scope", recorded as follow-up debt). Measured: 12 threads =
        # 16 queries, 12 of them `accounts_userpreferences`.
        threads = Thread.objects.filter(course=course).select_related('author').annotate(
            reply_count=Count('replies'),
            last_activity=Coalesce(Max('replies__created_at'), 'created_at'),
        ).order_by('-is_pinned', '-last_activity')
        serializer = ThreadListSerializer(threads, many=True, context={'request': request})
        return Response(serializer.data)

    # POST — instructor or enrolled student creates a thread. The demo
    # account reads discussions but never writes: anything it posted would be
    # visitor-authored content shown to every other visitor.
    require_not_demo(request.user)
    serializer = ThreadCreateSerializer(data=request.data)
    if serializer.is_valid():
        thread = serializer.save(course=course, author=request.user)
        return Response(
            ThreadDetailSerializer(thread, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def thread_detail(request, thread_id):
    """Get, update, or delete a thread."""
    thread = get_object_or_404(thread_detail_queryset(), id=thread_id)
    course = thread.course

    if not can_access(request.user, course):
        return Response(
            {'detail': 'You must be enrolled or the instructor to access this thread.'},
            status=status.HTTP_403_FORBIDDEN
        )

    if request.method == 'GET':
        serializer = ThreadDetailSerializer(thread, context={'request': request})
        return Response(serializer.data)

    # Edit = author only; delete = author or course instructor — and never
    # the demo account (it can't create threads, but could otherwise edit or
    # delete seeded ones it "authored").
    require_not_demo(request.user)
    is_author = thread.author == request.user
    is_instructor = is_course_instructor(request.user, course)

    if request.method == 'PUT':
        if not is_author:
            return Response(
                {'detail': 'Only the author can edit this thread.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = ThreadCreateSerializer(thread, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(ThreadDetailSerializer(thread, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # DELETE
    if not (is_author or is_instructor):
        return Response(
            {'detail': 'Only the author or course instructor can delete this thread.'},
            status=status.HTTP_403_FORBIDDEN
        )
    thread.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_pin(request, thread_id):
    """Toggle the pinned state of a thread. Instructor only."""
    thread = get_object_or_404(thread_detail_queryset(), id=thread_id)

    if not is_course_instructor(request.user, thread.course):
        return Response(
            {'detail': 'Only the course instructor can pin threads.'},
            status=status.HTTP_403_FORBIDDEN
        )

    thread.is_pinned = not thread.is_pinned
    thread.save(update_fields=['is_pinned'])
    return Response(ThreadDetailSerializer(thread, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_lock(request, thread_id):
    """Toggle the locked state of a thread. Instructor only."""
    thread = get_object_or_404(thread_detail_queryset(), id=thread_id)

    if not is_course_instructor(request.user, thread.course):
        return Response(
            {'detail': 'Only the course instructor can lock threads.'},
            status=status.HTTP_403_FORBIDDEN
        )

    thread.is_locked = not thread.is_locked
    thread.save(update_fields=['is_locked'])
    return Response(ThreadDetailSerializer(thread, context={'request': request}).data)


# ==================== Reply Views ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_reply(request, thread_id):
    """Create a reply on a thread."""
    thread = get_object_or_404(Thread, id=thread_id)
    course = thread.course

    if not can_access(request.user, course):
        return Response(
            {'detail': 'You must be enrolled or the instructor to reply.'},
            status=status.HTTP_403_FORBIDDEN
        )

    require_not_demo(request.user)

    # Locked threads block replies from everyone except the course instructor
    if thread.is_locked and not is_course_instructor(request.user, course):
        return Response(
            {'detail': 'This thread is locked.'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = ReplyCreateSerializer(data=request.data)
    if serializer.is_valid():
        reply = serializer.save(thread=thread, author=request.user)

        # Notify the thread author (never for their own reply)
        if reply.author != thread.author:
            Notification.objects.create(
                recipient=thread.author,
                type='reply',
                title=f'New reply to "{thread.title}"',
                message=reply.content[:200] + ('...' if len(reply.content) > 200 else ''),
                related_url=f'/courses/{course.code}/discussions/{thread.id}'
            )

        return Response(
            ReplySerializer(reply, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def reply_detail(request, reply_id):
    """Update (author only) or delete (author or course instructor) a reply."""
    reply = get_object_or_404(Reply, id=reply_id)
    require_not_demo(request.user)
    course = reply.thread.course
    is_author = reply.author == request.user
    is_instructor = is_course_instructor(request.user, course)

    if request.method == 'PUT':
        if not is_author:
            return Response(
                {'detail': 'Only the author can edit this reply.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = ReplyCreateSerializer(reply, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(ReplySerializer(reply, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # DELETE
    if not (is_author or is_instructor):
        return Response(
            {'detail': 'Only the author or course instructor can delete this reply.'},
            status=status.HTTP_403_FORBIDDEN
        )
    reply.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
