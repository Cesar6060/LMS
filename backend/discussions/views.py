from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Count, Max
from django.db.models.functions import Coalesce

from courses.models import Course, Enrollment
from notifications.models import Notification
from .models import Thread, Reply
from .serializers import (
    ThreadListSerializer, ThreadDetailSerializer, ThreadCreateSerializer,
    ReplySerializer, ReplyCreateSerializer,
)


def is_course_instructor(user, course):
    """Check if user is the instructor of a course."""
    return course.instructor == user


def is_enrolled(user, course):
    """Check if user is actively enrolled in a course."""
    return Enrollment.objects.filter(user=user, course=course, is_active=True).exists()


def can_access(user, course):
    """Read access = instructor of the course or active enrollment."""
    return is_course_instructor(user, course) or is_enrolled(user, course)


# ==================== Thread Views ====================

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
        threads = Thread.objects.filter(course=course).select_related('author').annotate(
            reply_count=Count('replies'),
            last_activity=Coalesce(Max('replies__created_at'), 'created_at'),
        ).order_by('-is_pinned', '-last_activity')
        serializer = ThreadListSerializer(threads, many=True, context={'request': request})
        return Response(serializer.data)

    # POST — instructor or enrolled student creates a thread
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
    thread = get_object_or_404(Thread, id=thread_id)
    course = thread.course

    if not can_access(request.user, course):
        return Response(
            {'detail': 'You must be enrolled or the instructor to access this thread.'},
            status=status.HTTP_403_FORBIDDEN
        )

    if request.method == 'GET':
        serializer = ThreadDetailSerializer(thread, context={'request': request})
        return Response(serializer.data)

    # Edit = author only; delete = author or course instructor
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
    thread = get_object_or_404(Thread, id=thread_id)

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
    thread = get_object_or_404(Thread, id=thread_id)

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
