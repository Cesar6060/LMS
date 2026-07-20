from datetime import date, timedelta

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from courses.models import (
    Course, Unit, Lesson, Enrollment, LessonProgress, LessonQuizAttempt,
)
from quizzes.models import Quiz, QuizAttempt
from notifications.models import Notification

from gamification.leveling import xp_for_level, level_for_xp, level_progress
from gamification.models import GameProfile, XPEvent, Badge, UserBadge
from gamification.services import (
    award_lesson_completion, award_quiz_pass, award_lesson_quiz_pass,
    _evaluate_badges,
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def instructor():
    return User.objects.create_user(
        email='instructor@test.com', password='pw', is_instructor=True
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        email='student@test.com', password='pw', is_instructor=False
    )


@pytest.fixture
def course(instructor):
    return Course.objects.create(
        code='GAM101', title='Gamified Course', instructor=instructor
    )


@pytest.fixture
def unit(course):
    return Unit.objects.create(course=course, title='Unit 1', order=1)


@pytest.fixture
def lesson(unit):
    return Lesson.objects.create(unit=unit, title='Lesson 1', order=1)


@pytest.fixture
def lessons(unit):
    return [
        Lesson.objects.create(unit=unit, title=f'Lesson {i}', order=i)
        for i in range(1, 6)
    ]


@pytest.fixture
def enrollment(student, course):
    return Enrollment.objects.create(user=student, course=course)


@pytest.fixture
def quiz(unit):
    return Quiz.objects.create(unit=unit, title='Quiz', passing_score=70, order=1)


# --------------------------------------------------------------------------
# Leveling helpers (pure)
# --------------------------------------------------------------------------

@pytest.mark.parametrize('level,expected', [
    (1, 0), (2, 100), (3, 300), (4, 600), (5, 1000), (6, 1500),
])
def test_xp_for_level(level, expected):
    assert xp_for_level(level) == expected


@pytest.mark.parametrize('xp,expected', [
    (0, 1), (99, 1), (100, 2), (299, 2), (300, 3), (599, 3), (600, 4), (1000, 5),
])
def test_level_for_xp(xp, expected):
    assert level_for_xp(xp) == expected


def test_level_progress_ring_fields():
    ring = level_progress(620)
    assert ring['level'] == 4
    assert ring['level_floor_xp'] == 600
    assert ring['next_level_xp'] == 1000
    assert ring['xp_into_level'] == 20
    assert ring['level_span'] == 400
    assert ring['level_progress_pct'] == 5


# --------------------------------------------------------------------------
# XP awards + idempotency
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestXPAwards:
    def test_lesson_completion_awards_50(self, student, lesson):
        today = date(2026, 7, 19)
        result = award_lesson_completion(student, lesson, today=today)

        assert result.xp_awarded == 50
        assert result.total_xp == 50
        profile = GameProfile.objects.get(user=student)
        assert profile.total_xp == 50
        assert profile.current_streak == 1
        assert profile.last_activity_date == today
        assert XPEvent.objects.filter(
            user=student, source_type='lesson', source_id=lesson.id
        ).count() == 1

    def test_lesson_completion_idempotent(self, student, lesson):
        today = date(2026, 7, 19)
        award_lesson_completion(student, lesson, today=today)
        # Re-award the same lesson (e.g. incomplete -> complete toggle).
        result = award_lesson_completion(student, lesson, today=today)

        assert result.xp_awarded == 0
        profile = GameProfile.objects.get(user=student)
        assert profile.total_xp == 50
        assert XPEvent.objects.filter(user=student).count() == 1

    def test_unit_quiz_pass_awards_20(self, student, quiz):
        result = award_quiz_pass(student, quiz)
        assert result.xp_awarded == 20
        assert GameProfile.objects.get(user=student).total_xp == 20
        assert XPEvent.objects.filter(
            user=student, source_type='quiz', source_id=quiz.id
        ).count() == 1

    def test_unit_quiz_pass_idempotent(self, student, quiz):
        award_quiz_pass(student, quiz)
        result = award_quiz_pass(student, quiz)
        assert result.xp_awarded == 0
        assert GameProfile.objects.get(user=student).total_xp == 20

    def test_lesson_quiz_pass_awards_20(self, student, lesson):
        result = award_lesson_quiz_pass(student, lesson)
        assert result.xp_awarded == 20
        assert XPEvent.objects.filter(
            user=student, source_type='lesson_quiz', source_id=lesson.id
        ).count() == 1

    def test_quiz_gated_lesson_yields_70(self, student, lesson):
        """Completion (50) + its comprehension quiz (20) = 70 the first time."""
        award_lesson_completion(student, lesson, today=date(2026, 7, 19))
        award_lesson_quiz_pass(student, lesson)
        assert GameProfile.objects.get(user=student).total_xp == 70


# --------------------------------------------------------------------------
# Streaks (injected today)
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestStreaks:
    def test_consecutive_days_increment(self, student, lessons):
        d1 = date(2026, 7, 19)
        award_lesson_completion(student, lessons[0], today=d1)
        award_lesson_completion(student, lessons[1], today=d1 + timedelta(days=1))
        profile = GameProfile.objects.get(user=student)
        assert profile.current_streak == 2
        assert profile.longest_streak == 2

    def test_same_day_no_change(self, student, lessons):
        d1 = date(2026, 7, 19)
        award_lesson_completion(student, lessons[0], today=d1)
        award_lesson_completion(student, lessons[1], today=d1)
        profile = GameProfile.objects.get(user=student)
        assert profile.current_streak == 1

    def test_gap_resets_streak(self, student, lessons):
        d1 = date(2026, 7, 19)
        award_lesson_completion(student, lessons[0], today=d1)
        award_lesson_completion(student, lessons[1], today=d1 + timedelta(days=1))
        # Two-day gap -> reset to 1, but longest preserved.
        award_lesson_completion(student, lessons[2], today=d1 + timedelta(days=4))
        profile = GameProfile.objects.get(user=student)
        assert profile.current_streak == 1
        assert profile.longest_streak == 2


# --------------------------------------------------------------------------
# Badges
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestBadges:
    def test_first_lesson_badge(self, student, lesson):
        # The view marks progress complete before awarding; mirror that here.
        LessonProgress.objects.create(user=student, lesson=lesson, completed=True)
        award_lesson_completion(student, lesson, today=date(2026, 7, 19))
        assert UserBadge.objects.filter(
            user=student, badge__key='first_lesson'
        ).exists()

    def test_perfect_unit_quiz_badge(self, student, quiz):
        QuizAttempt.objects.create(quiz=quiz, student=student, score=100, passed=True)
        profile, _ = GameProfile.objects.get_or_create(user=student)
        _evaluate_badges(student, profile)
        assert UserBadge.objects.filter(
            user=student, badge__key='perfect_quiz'
        ).exists()

    def test_perfect_lesson_quiz_badge(self, student, lesson):
        LessonQuizAttempt.objects.create(
            user=student, lesson=lesson, attempt_number=1,
            score=3, total_questions=3, passed=True,
        )
        profile, _ = GameProfile.objects.get_or_create(user=student)
        _evaluate_badges(student, profile)
        assert UserBadge.objects.filter(
            user=student, badge__key='perfect_quiz'
        ).exists()

    @pytest.mark.parametrize('xp,expected_keys', [
        (100, {'xp_100'}),
        (500, {'xp_100', 'xp_500'}),
        (1000, {'xp_100', 'xp_500', 'xp_1000'}),
    ])
    def test_xp_badges(self, student, xp, expected_keys):
        profile, _ = GameProfile.objects.get_or_create(user=student, defaults={'total_xp': xp})
        profile.total_xp = xp
        profile.save()
        _evaluate_badges(student, profile)
        earned = set(UserBadge.objects.filter(
            user=student, badge__key__startswith='xp_'
        ).values_list('badge__key', flat=True))
        assert expected_keys.issubset(earned)

    def test_streak_7_badge(self, student):
        profile, _ = GameProfile.objects.get_or_create(user=student)
        profile.longest_streak = 7
        profile.save()
        _evaluate_badges(student, profile)
        assert UserBadge.objects.filter(user=student, badge__key='streak_7').exists()

    def test_course_complete_badge(self, student, course, unit, lessons, enrollment):
        for lsn in lessons:
            LessonProgress.objects.create(user=student, lesson=lsn, completed=True)
        profile, _ = GameProfile.objects.get_or_create(user=student)
        _evaluate_badges(student, profile)
        assert UserBadge.objects.filter(user=student, badge__key='course_done').exists()

    def test_course_incomplete_no_badge(self, student, course, unit, lessons, enrollment):
        for lsn in lessons[:-1]:  # all but one
            LessonProgress.objects.create(user=student, lesson=lsn, completed=True)
        profile, _ = GameProfile.objects.get_or_create(user=student)
        _evaluate_badges(student, profile)
        assert not UserBadge.objects.filter(user=student, badge__key='course_done').exists()

    def test_badge_award_idempotent(self, student, lesson):
        LessonProgress.objects.create(user=student, lesson=lesson, completed=True)
        award_lesson_completion(student, lesson, today=date(2026, 7, 19))
        profile = GameProfile.objects.get(user=student)
        _evaluate_badges(student, profile)
        _evaluate_badges(student, profile)
        assert UserBadge.objects.filter(user=student, badge__key='first_lesson').count() == 1

    def test_badge_earn_creates_notification(self, student, lesson):
        LessonProgress.objects.create(user=student, lesson=lesson, completed=True)
        award_lesson_completion(student, lesson, today=date(2026, 7, 19))
        notif = Notification.objects.filter(recipient=student, type='badge_earned')
        assert notif.exists()
        assert 'First Steps' in notif.first().title


# --------------------------------------------------------------------------
# Instructor is inert
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestInstructorInert:
    def test_instructor_completion_awards_nothing(self, instructor, lesson):
        result = award_lesson_completion(instructor, lesson, today=date(2026, 7, 19))
        assert result.xp_awarded == 0
        assert not XPEvent.objects.filter(user=instructor).exists()
        assert not GameProfile.objects.filter(user=instructor).exists()

    def test_instructor_endpoint_inert(self, api_client, instructor):
        api_client.force_authenticate(user=instructor)
        response = api_client.get('/api/gamification/profile/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {'is_gamified': False}


# --------------------------------------------------------------------------
# Read endpoint
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestProfileEndpoint:
    def test_unauthenticated_401(self, api_client):
        response = api_client.get('/api/gamification/profile/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_student_shape(self, api_client, student):
        api_client.force_authenticate(user=student)
        response = api_client.get('/api/gamification/profile/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data['is_gamified'] is True
        for key in [
            'total_xp', 'level', 'level_floor_xp', 'next_level_xp',
            'xp_into_level', 'level_progress_pct', 'current_streak',
            'longest_streak', 'last_activity_date', 'badges', 'all_badges',
        ]:
            assert key in data
        assert len(data['all_badges']) == Badge.objects.count()

    def test_level_derivation_via_endpoint(self, api_client, student):
        profile, _ = GameProfile.objects.get_or_create(user=student)
        profile.total_xp = 100
        profile.save()
        api_client.force_authenticate(user=student)
        response = api_client.get('/api/gamification/profile/')
        assert response.data['level'] == 2
        assert response.data['level_floor_xp'] == 100

        profile.total_xp = 600
        profile.save()
        response = api_client.get('/api/gamification/profile/')
        assert response.data['level'] == 4

    def test_earned_badges_reflected(self, api_client, student, lesson):
        LessonProgress.objects.create(user=student, lesson=lesson, completed=True)
        award_lesson_completion(student, lesson, today=date(2026, 7, 19))
        api_client.force_authenticate(user=student)
        response = api_client.get('/api/gamification/profile/')
        earned_keys = {b['key'] for b in response.data['badges']}
        assert 'first_lesson' in earned_keys
        first = next(b for b in response.data['all_badges'] if b['key'] == 'first_lesson')
        assert first['earned'] is True
        assert first['earned_at'] is not None


# --------------------------------------------------------------------------
# Choke-point responses carry the gamification delta
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestChokePointResponses:
    def test_complete_lesson_response_has_delta(self, api_client, student, lesson, enrollment):
        api_client.force_authenticate(user=student)
        response = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/progress/', {'completed': True}
        )
        assert response.status_code == status.HTTP_200_OK
        assert 'gamification' in response.data
        assert response.data['gamification']['xp_awarded'] == 50
        assert response.data['gamification']['current_streak'] == 1

    def test_recomplete_lesson_no_double_award(self, api_client, student, lesson, enrollment):
        api_client.force_authenticate(user=student)
        api_client.patch(f'/api/courses/lessons/{lesson.id}/progress/', {'completed': True})
        # Already complete: no transition -> no gamification delta.
        response = api_client.patch(
            f'/api/courses/lessons/{lesson.id}/progress/', {'completed': True}
        )
        assert 'gamification' not in response.data
        assert GameProfile.objects.get(user=student).total_xp == 50


# --------------------------------------------------------------------------
# Backfill command
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestBackfill:
    def test_backfill_awards_and_is_idempotent(self, student, course, unit, lessons, quiz, enrollment):
        from django.core.management import call_command

        # History with no gamification rows yet.
        for lsn in lessons:
            LessonProgress.objects.create(user=student, lesson=lsn, completed=True)
        QuizAttempt.objects.create(quiz=quiz, student=student, score=100, passed=True)
        # Two attempts of the same quiz -> only counted once.
        QuizAttempt.objects.create(quiz=quiz, student=student, score=80, passed=True)

        call_command('backfill_gamification')

        profile = GameProfile.objects.get(user=student)
        # 5 lessons * 50 + 1 distinct quiz * 20 = 270
        assert profile.total_xp == 270
        assert profile.current_streak == 0  # streaks stay 0
        xp_events = XPEvent.objects.filter(user=student).count()
        badges = UserBadge.objects.filter(user=student).count()
        # first_lesson, course_done, perfect_quiz, xp_100 expected.
        assert UserBadge.objects.filter(user=student, badge__key='course_done').exists()

        # Backfilled badges are historical: no bell notifications fired.
        assert not Notification.objects.filter(
            recipient=student, type='badge_earned'
        ).exists()

        # Re-run -> no change.
        call_command('backfill_gamification')
        profile.refresh_from_db()
        assert profile.total_xp == 270
        assert XPEvent.objects.filter(user=student).count() == xp_events
        assert UserBadge.objects.filter(user=student).count() == badges

    def test_backfill_skips_instructors(self, instructor, course, unit, lesson):
        from django.core.management import call_command
        LessonProgress.objects.create(user=instructor, lesson=lesson, completed=True)
        call_command('backfill_gamification')
        assert not GameProfile.objects.filter(user=instructor).exists()


# --------------------------------------------------------------------------
# Streak freezes (Phase 32)
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestStreakFreezes:
    def test_earned_on_level_up(self, student, lessons):
        """Crossing a level threshold grants +1 freeze and surfaces it."""
        today = date(2026, 7, 19)
        first = award_lesson_completion(student, lessons[0], today=today)  # 50 XP
        assert first.freezes_earned == 0

        second = award_lesson_completion(student, lessons[1], today=today)  # 100 XP -> L2
        assert second.leveled_up is True
        assert second.freezes_earned == 1
        assert second.streak_freezes == 1
        assert GameProfile.objects.get(user=student).streak_freezes == 1

    def test_earn_capped_at_two(self, student, lessons):
        profile, _ = GameProfile.objects.get_or_create(user=student)
        profile.streak_freezes = 2
        profile.total_xp = 90
        profile.save()

        result = award_lesson_completion(student, lessons[0], today=date(2026, 7, 19))
        assert result.leveled_up is True  # 90 -> 140 crosses level 2
        assert result.freezes_earned == 0
        assert result.streak_freezes == 2

    def test_multi_level_jump_respects_cap(self, student):
        """A single award crossing 2 levels grants 2 freezes, never more."""
        from gamification.services import _award
        from gamification.models import XPEvent

        result = _award(student, XPEvent.SOURCE_LESSON, 999, 350)  # 0 -> 350 = L1 -> L3
        assert result.level == 3
        assert result.freezes_earned == 2
        assert result.streak_freezes == 2

        # Another jump with a full bank earns nothing.
        result2 = _award(student, XPEvent.SOURCE_LESSON, 998, 700)  # 350 -> 1050
        assert result2.leveled_up is True
        assert result2.freezes_earned == 0
        assert result2.streak_freezes == 2

    def test_one_day_gap_consumed_streak_continues(self, student, lessons):
        d1 = date(2026, 7, 19)
        award_lesson_completion(student, lessons[0], today=d1)
        profile = GameProfile.objects.get(user=student)
        profile.total_xp = 100  # mid-level so the next +50 can't level up
        profile.streak_freezes = 1
        profile.current_streak = 5
        profile.save()

        # Miss one day: freeze absorbs it, streak continues.
        result = award_lesson_completion(student, lessons[1], today=d1 + timedelta(days=2))
        assert result.freezes_used == 1
        assert result.current_streak == 6
        profile.refresh_from_db()
        assert profile.streak_freezes == 0
        assert profile.current_streak == 6

    def test_gap_larger_than_freezes_resets_and_keeps_freezes(self, student, lessons):
        d1 = date(2026, 7, 19)
        award_lesson_completion(student, lessons[0], today=d1)
        profile = GameProfile.objects.get(user=student)
        profile.total_xp = 100  # mid-level so the next +50 can't level up
        profile.streak_freezes = 1
        profile.current_streak = 5
        profile.longest_streak = 5
        profile.save()

        # Two missed days with only 1 freeze: reset, consume nothing.
        result = award_lesson_completion(student, lessons[1], today=d1 + timedelta(days=3))
        assert result.freezes_used == 0
        assert result.current_streak == 1
        profile.refresh_from_db()
        assert profile.streak_freezes == 1
        assert profile.longest_streak == 5

    def test_two_day_gap_two_freezes_consumed(self, student, lessons):
        d1 = date(2026, 7, 19)
        award_lesson_completion(student, lessons[0], today=d1)
        profile = GameProfile.objects.get(user=student)
        profile.total_xp = 100  # mid-level so the next +50 can't level up
        profile.streak_freezes = 2
        profile.current_streak = 3
        profile.save()

        result = award_lesson_completion(student, lessons[1], today=d1 + timedelta(days=3))
        assert result.freezes_used == 2
        assert result.current_streak == 4
        profile.refresh_from_db()
        assert profile.streak_freezes == 0

    def test_instructor_still_inert(self, instructor, lesson):
        result = award_lesson_completion(instructor, lesson, today=date(2026, 7, 19))
        assert result.freezes_earned == 0
        assert result.freezes_used == 0
        assert not GameProfile.objects.filter(user=instructor).exists()

    def test_profile_endpoint_includes_freezes(self, api_client, student):
        profile, _ = GameProfile.objects.get_or_create(user=student)
        profile.streak_freezes = 2
        profile.save()
        api_client.force_authenticate(user=student)
        response = api_client.get('/api/gamification/profile/')
        assert response.data['streak_freezes'] == 2

    def test_delta_shape_includes_freeze_fields(self, student, lesson):
        result = award_lesson_completion(student, lesson, today=date(2026, 7, 19))
        payload = result.as_dict()
        for key in ('streak_freezes', 'freezes_earned', 'freezes_used'):
            assert key in payload
