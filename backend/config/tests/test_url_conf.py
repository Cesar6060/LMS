"""
Guard tests for the URL configuration.

The backend URL layout intentionally keeps its doubled prefixes
(/api/courses/courses/, /api/assignments/assignments/<pk>/) and mounts the
quizzes and discussions apps at bare /api/. These tests pin that layout so
the include ordering in config/urls.py can't silently break: the
courses/<code>/... routes in quizzes/discussions only resolve because the
courses app defines no competing pattern under api/courses/.
"""

import pytest
from django.urls import Resolver404, resolve


def test_course_quizzes_falls_through_to_quizzes_app():
    match = resolve('/api/courses/CS101/quizzes/')
    assert match.func.__module__ == 'quizzes.views'
    assert match.url_name == 'course-quizzes'


def test_course_threads_falls_through_to_discussions_app():
    match = resolve('/api/courses/CS101/threads/')
    assert match.func.__module__ == 'discussions.views'
    assert match.url_name == 'course-threads'


def test_quick_grade_resolves_with_single_quizzes_segment():
    match = resolve('/api/quizzes/1/quick-grade/2/')
    assert match.func.__module__ == 'quizzes.views'
    assert match.url_name == 'quick-grade-quiz'


def test_quick_grade_doubled_quizzes_segment_does_not_resolve():
    with pytest.raises(Resolver404):
        resolve('/api/quizzes/quizzes/1/quick-grade/2/')


def test_canonical_doubled_prefix_paths_still_resolve():
    assert resolve('/api/courses/courses/').func.__module__ == 'courses.views'
    assert resolve('/api/courses/courses/CS101/').func.__module__ == 'courses.views'
    assert resolve('/api/assignments/assignments/1/').func.__module__ == 'assignments.views'
