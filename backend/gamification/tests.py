from datetime import date, timedelta
from unittest import mock

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from courses.models import (
    Course, Unit, Lesson, Enrollment, LessonProgress, LessonQuizAttempt,
)
from quizzes.models import Quiz, QuizAttempt
from notifications.models import Notification

from gamification.avatar_catalog import CATALOG as AVATAR_CATALOG
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


# --------------------------------------------------------------------------
# Avatar customization (Phase 33)
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestAvatar:
    AVATAR_URL = '/api/gamification/avatar/'
    PROFILE_URL = '/api/gamification/profile/'

    def _set_xp(self, student, xp):
        profile, _ = GameProfile.objects.get_or_create(user=student)
        profile.total_xp = xp
        profile.save()
        return profile

    def test_fresh_profile_has_defaults(self, api_client, student):
        api_client.force_authenticate(user=student)
        avatar = api_client.get(self.PROFILE_URL).data['avatar']
        assert avatar['mascot_name'] == 'Circuit'
        assert avatar['equipped'] == {
            'color': 'classic', 'headgear': 'none',
            'eyes': 'none', 'accessory': 'none', 'backdrop': 'plain',
            # Phase 64 slots ('aura' was retired after phase 64)
            'companion': 'none', 'held': 'none',
        }
        assert len(avatar['catalog']) == len(AVATAR_CATALOG)

    def test_unlocked_flags_at_level_boundary(self, api_client, student):
        api_client.force_authenticate(user=student)

        self._set_xp(student, 99)  # still level 1
        catalog = api_client.get(self.PROFILE_URL).data['avatar']['catalog']
        ember = next(i for i in catalog if i['slot'] == 'color' and i['key'] == 'ember')
        assert ember['required_level'] == 2
        assert ember['unlocked'] is False

        self._set_xp(student, 100)  # level 2
        catalog = api_client.get(self.PROFILE_URL).data['avatar']['catalog']
        ember = next(i for i in catalog if i['slot'] == 'color' and i['key'] == 'ember')
        assert ember['unlocked'] is True
        # Level-1 defaults are always unlocked. Scoped to level-gated items:
        # badge/streak items also carry required_level 1 (so the level gate
        # never double-blocks them) but are locked until their own gate opens.
        assert all(
            i['unlocked'] for i in catalog
            if i['unlock_type'] == 'level' and i['required_level'] == 1
        )

    def test_equip_unlocked_item_persists(self, api_client, student):
        self._set_xp(student, 100)  # level 2
        api_client.force_authenticate(user=student)
        response = api_client.patch(
            self.AVATAR_URL, {'color': 'ember', 'headgear': 'cap', 'backdrop': 'grid'}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['equipped']['color'] == 'ember'
        assert response.data['equipped']['headgear'] == 'cap'
        assert response.data['equipped']['backdrop'] == 'grid'
        profile = GameProfile.objects.get(user=student)
        assert profile.avatar_color == 'ember'
        assert profile.avatar_headgear == 'cap'
        assert profile.avatar_backdrop == 'grid'

    def test_equip_locked_item_400_nothing_persists(self, api_client, student):
        self._set_xp(student, 0)  # level 1
        api_client.force_authenticate(user=student)
        response = api_client.patch(
            self.AVATAR_URL, {'mascot_name': 'Sparky', 'color': 'ember'}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'detail' in response.data
        profile = GameProfile.objects.get(user=student)
        assert profile.avatar_color == 'classic'
        assert profile.mascot_name == 'Circuit'  # all-or-nothing

    def test_unknown_key_400(self, api_client, student):
        api_client.force_authenticate(user=student)
        response = api_client.patch(self.AVATAR_URL, {'headgear': 'propeller'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_slot_mismatch_key_400(self, api_client, student):
        self._set_xp(student, 1000)  # high level: cap is unlocked, just wrong slot
        api_client.force_authenticate(user=student)
        response = api_client.patch(self.AVATAR_URL, {'eyes': 'cap'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert GameProfile.objects.get(user=student).avatar_eyes == 'none'

    def test_rename_happy_path_trims(self, api_client, student):
        api_client.force_authenticate(user=student)
        response = api_client.patch(self.AVATAR_URL, {'mascot_name': '  Sparky  '})
        assert response.status_code == status.HTTP_200_OK
        assert response.data['mascot_name'] == 'Sparky'
        assert GameProfile.objects.get(user=student).mascot_name == 'Sparky'

    @pytest.mark.parametrize('bad_name', ['', '   ', 'x' * 21, None])
    def test_rename_invalid_400(self, api_client, student, bad_name):
        api_client.force_authenticate(user=student)
        response = api_client.patch(
            self.AVATAR_URL, {'mascot_name': bad_name}, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert GameProfile.objects.get(user=student).mascot_name == 'Circuit'

    def test_stale_equipped_key_falls_back_to_default(self, api_client, student):
        profile = self._set_xp(student, 100)
        profile.avatar_headgear = 'retired_item'  # simulate a removed catalog key
        profile.save()
        api_client.force_authenticate(user=student)
        avatar = api_client.get(self.PROFILE_URL).data['avatar']
        assert avatar['equipped']['headgear'] == 'none'

    def test_unauthenticated_401(self, api_client):
        response = api_client.patch(self.AVATAR_URL, {'mascot_name': 'Sparky'})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_instructor_patch_403(self, api_client, instructor):
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(self.AVATAR_URL, {'mascot_name': 'Sparky'})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'detail' in response.data

    def test_instructor_profile_stays_inert(self, api_client, instructor):
        api_client.force_authenticate(user=instructor)
        response = api_client.get(self.PROFILE_URL)
        assert response.data == {'is_gamified': False}


# --------------------------------------------------------------------------
# Avatar expansion: new slots, badge/streak gates, demo policy (Phase 64)
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestAvatarPhase64:
    AVATAR_URL = '/api/gamification/avatar/'
    PROFILE_URL = '/api/gamification/profile/'

    def _profile(self, student, **fields):
        profile, _ = GameProfile.objects.get_or_create(user=student)
        for key, value in fields.items():
            setattr(profile, key, value)
        profile.save()
        return profile

    def _award(self, student, badge_key):
        UserBadge.objects.create(
            user=student, badge=Badge.objects.get(key=badge_key)
        )

    def _item(self, catalog, slot, key):
        return next(i for i in catalog if i['slot'] == slot and i['key'] == key)

    def _catalog(self, api_client):
        return api_client.get(self.PROFILE_URL).data['avatar']['catalog']

    # -- new slots ---------------------------------------------------------

    def test_every_slot_defaults(self, api_client, student):
        api_client.force_authenticate(user=student)
        equipped = api_client.get(self.PROFILE_URL).data['avatar']['equipped']
        assert equipped == {
            'color': 'classic', 'headgear': 'none', 'eyes': 'none',
            'accessory': 'none', 'backdrop': 'plain',
            'companion': 'none', 'held': 'none',
        }

    def test_retired_aura_slot_is_not_served(self, api_client, student):
        """The slot was retired after phase 64. Its GameProfile column is
        deliberately still there, but nothing should read or serve it."""
        api_client.force_authenticate(user=student)
        avatar = api_client.get(self.PROFILE_URL).data['avatar']
        assert 'aura' not in avatar['equipped']
        assert not [i for i in avatar['catalog'] if i['slot'] == 'aura']
        # And it can't be equipped through the back door.
        response = api_client.patch(self.AVATAR_URL, {'aura': 'golden'})
        assert response.status_code == status.HTTP_200_OK
        assert 'aura' not in response.data['equipped']

    def test_equip_new_slots_persists(self, api_client, student):
        self._profile(student, total_xp=xp_for_level(8))
        api_client.force_authenticate(user=student)
        response = api_client.patch(self.AVATAR_URL, {
            'companion': 'robo_cat', 'held': 'codex',
        })
        assert response.status_code == status.HTTP_200_OK
        profile = GameProfile.objects.get(user=student)
        assert profile.avatar_companion == 'robo_cat'
        assert profile.avatar_held == 'codex'

    @pytest.mark.parametrize('slot,key', [
        ('companion', 'drone'), ('held', 'wrench'),
    ])
    def test_stale_key_falls_back_on_new_slots(
            self, api_client, student, slot, key):
        profile = self._profile(student, total_xp=xp_for_level(15))
        setattr(profile, f'avatar_{slot}', key)
        profile.save()
        # Simulate the item being retired from the catalog later.
        setattr(profile, f'avatar_{slot}', 'retired_item')
        profile.save()
        api_client.force_authenticate(user=student)
        equipped = api_client.get(self.PROFILE_URL).data['avatar']['equipped']
        assert equipped[slot] == 'none'

    # -- extended level ladder ---------------------------------------------

    @pytest.mark.parametrize('level,slot,key', [
        (9, 'color', 'violet'),
        (15, 'companion', 'dragon'),
    ])
    def test_level_gate_boundary_beyond_lv8(
            self, api_client, student, level, slot, key):
        """The ladder now runs past Lv 8 — check both ends of the new range."""
        floor_xp = xp_for_level(level)
        api_client.force_authenticate(user=student)

        self._profile(student, total_xp=floor_xp - 1)
        assert self._item(self._catalog(api_client), slot, key)['unlocked'] is False
        assert api_client.patch(
            self.AVATAR_URL, {slot: key}
        ).status_code == status.HTTP_400_BAD_REQUEST

        self._profile(student, total_xp=floor_xp)
        assert self._item(self._catalog(api_client), slot, key)['unlocked'] is True
        assert api_client.patch(
            self.AVATAR_URL, {slot: key}
        ).status_code == status.HTTP_200_OK

    # -- badge gate --------------------------------------------------------

    def test_badge_gate_blocks_then_opens(self, api_client, student):
        self._profile(student, total_xp=0)
        api_client.force_authenticate(user=student)

        assert self._item(self._catalog(api_client), 'eyes', 'laser')['unlocked'] is False
        response = api_client.patch(self.AVATAR_URL, {'eyes': 'laser'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Sharpshooter badge' in response.data['detail']

        self._award(student, 'perfect_quiz')
        assert self._item(self._catalog(api_client), 'eyes', 'laser')['unlocked'] is True
        assert api_client.patch(
            self.AVATAR_URL, {'eyes': 'laser'}
        ).status_code == status.HTTP_200_OK
        assert GameProfile.objects.get(user=student).avatar_eyes == 'laser'

    def test_rename_only_patch_still_reports_badge_unlocks(
            self, api_client, student):
        """
        Guard on the rename-only shortcut in update_avatar: skipping the badge
        query must not make the response claim badge-gated items are locked.
        """
        self._award(student, 'perfect_quiz')
        api_client.force_authenticate(user=student)
        response = api_client.patch(self.AVATAR_URL, {'mascot_name': 'Sparky'})
        assert response.status_code == status.HTTP_200_OK
        laser = self._item(response.data['catalog'], 'eyes', 'laser')
        assert laser['unlocked'] is True, (
            'rename-only PATCH returned a payload with badge unlocks missing'
        )

    def test_badge_gate_ignores_level(self, api_client, student):
        """A max-level student without the badge still cannot equip it."""
        self._profile(student, total_xp=xp_for_level(20))
        api_client.force_authenticate(user=student)
        assert self._item(self._catalog(api_client), 'color', 'aurora')['unlocked'] is False

    # -- streak gate -------------------------------------------------------

    def test_streak_gate_reads_longest_not_current(self, api_client, student):
        """
        The regression guard for the Phase 64 decision: streak unlocks are
        permanent, so they read longest_streak. A student mid-streak whose
        longest is short must NOT have the item; a student whose streak broke
        after a long run must keep it.
        """
        api_client.force_authenticate(user=student)

        self._profile(student, current_streak=30, longest_streak=0)
        assert self._item(
            self._catalog(api_client), 'companion', 'phoenix'
        )['unlocked'] is False
        assert api_client.patch(
            self.AVATAR_URL, {'companion': 'phoenix'}
        ).status_code == status.HTTP_400_BAD_REQUEST

        self._profile(student, current_streak=0, longest_streak=30)
        assert self._item(
            self._catalog(api_client), 'companion', 'phoenix'
        )['unlocked'] is True
        assert api_client.patch(
            self.AVATAR_URL, {'companion': 'phoenix'}
        ).status_code == status.HTTP_200_OK

    def test_streak_unlock_is_never_revoked(self, api_client, student):
        """Equipped streak item survives the streak breaking."""
        self._profile(student, current_streak=30, longest_streak=30)
        api_client.force_authenticate(user=student)
        assert api_client.patch(
            self.AVATAR_URL, {'companion': 'phoenix'}
        ).status_code == status.HTTP_200_OK

        # Streak breaks — longest_streak is untouched by design.
        self._profile(student, current_streak=0)
        equipped = api_client.get(self.PROFILE_URL).data['avatar']['equipped']
        assert equipped['companion'] == 'phoenix', (
            'a broken streak must not silently downgrade an equipped item'
        )

    def test_badge_unlock_is_never_revoked(self, api_client, student):
        self._award(student, 'perfect_quiz')
        api_client.force_authenticate(user=student)
        api_client.patch(self.AVATAR_URL, {'held': 'trophy'})
        equipped = api_client.get(self.PROFILE_URL).data['avatar']['equipped']
        assert equipped['held'] == 'trophy'

    # -- unlock_label ------------------------------------------------------

    @pytest.mark.parametrize('slot,key,expected', [
        ('color', 'violet', 'Lv 9'),
        ('eyes', 'laser', 'Sharpshooter badge'),
        ('headgear', 'flame_crest', '14-day streak'),
        ('companion', 'phoenix', '30-day streak'),
        ('color', 'aurora', 'Scholar badge'),
    ])
    def test_unlock_label_shape(self, api_client, student, slot, key, expected):
        api_client.force_authenticate(user=student)
        item = self._item(self._catalog(api_client), slot, key)
        assert item['unlock_label'] == expected

    def test_every_catalog_item_reports_gate_fields(self, api_client, student):
        api_client.force_authenticate(user=student)
        for item in self._catalog(api_client):
            assert item['unlock_type'] in ('level', 'badge', 'streak')
            assert item['unlock_label'], f"{item['slot']}/{item['key']} has a blank label"
            assert isinstance(item['unlocked'], bool)

    # -- query discipline (Phase 63 rule) ----------------------------------

    # The profile endpoint's whole query budget. Deliberately an ABSOLUTE
    # number, not a before/after comparison: a per-item badge lookup would
    # cost the same in both halves of a comparison and sail straight through
    # it. If this number goes up, something started scaling with the catalog.
    PROFILE_QUERY_BUDGET = 8

    def test_profile_avatar_block_costs_no_per_item_queries(
            self, api_client, student):
        """
        The avatar block ships 71 catalog items and each badge-gated one needs
        the earned badge set. That set must be fetched once for the request,
        never once per item.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self._profile(student, total_xp=xp_for_level(15))
        self._award(student, 'perfect_quiz')
        self._award(student, 'course_done')
        api_client.force_authenticate(user=student)

        with CaptureQueriesContext(connection) as ctx:
            response = api_client.get(self.PROFILE_URL)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['avatar']['catalog']) == len(AVATAR_CATALOG)
        # 71 catalog items, 7 badges — if either count could drive the query
        # count, this budget would be blown many times over.
        assert len(ctx.captured_queries) <= self.PROFILE_QUERY_BUDGET, (
            f'{len(ctx.captured_queries)} queries for a profile with '
            f'{len(AVATAR_CATALOG)} catalog items — budget is '
            f'{self.PROFILE_QUERY_BUDGET}. Something is scaling with the '
            'catalog or the badge list.'
        )

    def test_avatar_payload_query_count_is_flat_in_catalog_size(
            self, api_client, student):
        """
        Directly pins the property the budget above protects: tripling the
        catalog must not change the query count by even one.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from gamification import services

        self._profile(student, total_xp=xp_for_level(15))
        self._award(student, 'perfect_quiz')
        api_client.force_authenticate(user=student)

        with CaptureQueriesContext(connection) as small:
            api_client.get(self.PROFILE_URL)

        tripled = list(AVATAR_CATALOG) * 3
        with mock.patch.object(services, 'CATALOG', tripled):
            with CaptureQueriesContext(connection) as big:
                response = api_client.get(self.PROFILE_URL)

        assert len(response.data['avatar']['catalog']) == len(tripled)
        assert len(big.captured_queries) == len(small.captured_queries), (
            f'{len(small.captured_queries)} queries for {len(AVATAR_CATALOG)} '
            f'items vs {len(big.captured_queries)} for {len(tripled)} — the '
            'payload is querying per catalog item'
        )

    # -- demo policy -------------------------------------------------------

    @pytest.mark.parametrize('body', [
        {'headgear': 'none'},
        {'companion': 'none'},
        {'color': 'classic'},
        {'aura': 'none', 'held': 'none'},
    ])
    def test_instructor_403_on_cosmetic_only_body(
            self, api_client, instructor, body):
        """
        Phase 64 moved the demo guard out of the view body and into the
        mascot_name branch, leaving the instructor check at the top as the
        only thing gating this endpoint. The pre-existing instructor test
        sends mascot_name, so nothing covered a slot-only body — this does.
        Every key here is an always-unlocked default, so a 403 can only come
        from the role check.
        """
        api_client.force_authenticate(user=instructor)
        response = api_client.patch(self.AVATAR_URL, body, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not GameProfile.objects.filter(user=instructor).exists(), (
            'the instructor check must reject before get_or_create runs'
        )

    def test_demo_can_equip_cosmetics(self, api_client, settings, student):
        # Lv 2 so 'cap' is genuinely unlocked — this test is about the demo
        # gate, not the level gate.
        self._profile(student, total_xp=xp_for_level(2))
        settings.DEMO_ACCOUNT_EMAIL = student.email
        api_client.force_authenticate(user=student)
        response = api_client.patch(self.AVATAR_URL, {'headgear': 'cap'})
        assert response.status_code == status.HTTP_200_OK
        assert GameProfile.objects.get(user=student).avatar_headgear == 'cap'

    def test_demo_rename_still_blocked(self, api_client, settings, student):
        settings.DEMO_ACCOUNT_EMAIL = student.email
        api_client.force_authenticate(user=student)
        response = api_client.patch(self.AVATAR_URL, {'mascot_name': 'Vandal'})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data['code'] == 'demo_blocked'
        assert GameProfile.objects.get(user=student).mascot_name == 'Circuit'

    def test_demo_mixed_body_persists_nothing(self, api_client, settings, student):
        """A rename smuggled in beside valid cosmetics must roll the whole
        request back, not save the cosmetics as a consolation prize."""
        self._profile(student, total_xp=xp_for_level(2))
        settings.DEMO_ACCOUNT_EMAIL = student.email
        api_client.force_authenticate(user=student)
        response = api_client.patch(
            self.AVATAR_URL, {'mascot_name': 'Vandal', 'headgear': 'cap'}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        profile = GameProfile.objects.get(user=student)
        assert profile.mascot_name == 'Circuit'
        assert profile.avatar_headgear == 'none'


@pytest.mark.django_db
class TestAvatarNameHardening:
    """
    `mascot_name` is free text that goes straight to a Postgres column, so
    length is not the only rule that matters. Found by the phase-64
    adversarial pass: a bare NUL byte passed the length check and blew up as
    an unhandled 500 inside save().
    """
    AVATAR_URL = '/api/gamification/avatar/'

    @pytest.mark.parametrize('name,label', [
        ('a\x00b', 'NUL byte'),
        ('a\x07b', 'BEL control char'),
        ('bad\nname', 'newline'),
        ('​', 'zero-width space only'),
        ('​hi', 'zero-width space embedded'),
        ('‮evil', 'RTL override'),
    ])
    def test_control_and_format_chars_rejected_with_400(
            self, api_client, student, name, label):
        api_client.force_authenticate(user=student)
        response = api_client.patch(
            self.AVATAR_URL, {'mascot_name': name}, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f'{label} should be a clean 400, not a 500'
        )
        assert GameProfile.objects.get(user=student).mascot_name == 'Circuit'

    @pytest.mark.parametrize('name,expected', [
        ('Sparky', 'Sparky'),
        ('  Sparky  ', 'Sparky'),
        ('Robo 9000', 'Robo 9000'),
        ('Ünïcødé Bot', 'Ünïcødé Bot'),
        ('x' * 20, 'x' * 20),
    ])
    def test_legitimate_names_still_accepted(
            self, api_client, student, name, expected):
        api_client.force_authenticate(user=student)
        response = api_client.patch(
            self.AVATAR_URL, {'mascot_name': name}, format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['mascot_name'] == expected

    def test_oversized_payload_is_a_400_not_a_crash(self, api_client, student):
        api_client.force_authenticate(user=student)
        response = api_client.patch(
            self.AVATAR_URL, {'mascot_name': 'x' * 100_000}, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestAvatarNoIdor:
    """
    The endpoint is scoped entirely to request.user and takes no id of any
    kind. This pins that: a future refactor must not add a user-targeting
    parameter.
    """
    AVATAR_URL = '/api/gamification/avatar/'

    @pytest.mark.parametrize('smuggled', ['user', 'user_id', 'profile', 'id'])
    def test_extra_user_field_cannot_target_another_profile(
            self, api_client, student, smuggled):
        victim = User.objects.create_user(
            email='victim@test.com', password='pw', is_instructor=False
        )
        GameProfile.objects.create(user=victim, total_xp=5000)
        api_client.force_authenticate(user=student)

        response = api_client.patch(
            self.AVATAR_URL, {smuggled: victim.id, 'headgear': 'none'}
        )
        assert response.status_code == status.HTTP_200_OK
        assert GameProfile.objects.get(user=victim).avatar_headgear == 'none'
        assert GameProfile.objects.get(user=victim).mascot_name == 'Circuit'
        # The write landed on the caller, not the victim.
        assert GameProfile.objects.filter(user=student).exists()


@pytest.mark.django_db
class TestAvatarAllOrNothingOrdering:
    """
    All-or-nothing must hold regardless of the order fields appear in the
    body. `update_avatar` iterates the fixed SLOTS tuple and saves once at the
    end, so client key order is irrelevant — this pins that property.
    """
    AVATAR_URL = '/api/gamification/avatar/'

    @pytest.fixture
    def lv2(self, student):
        profile, _ = GameProfile.objects.get_or_create(user=student)
        profile.total_xp = xp_for_level(2)
        profile.save()
        return profile

    @pytest.mark.parametrize('body', [
        {'headgear': 'cap', 'companion': 'dragon'},          # valid, then locked
        {'companion': 'dragon', 'headgear': 'cap'},          # locked, then valid
        {'mascot_name': 'Sparky', 'companion': 'dragon'},    # rename + locked
        {'companion': 'dragon', 'mascot_name': 'Sparky'},    # locked + rename
        {'headgear': 'cap', 'eyes': 'cap'},                  # valid + wrong-slot key
        {'eyes': 'cap', 'headgear': 'cap'},                  # wrong-slot key + valid
        {'color': 'ember', 'companion': 'drone', 'held': 'debug_blade'},  # last one locked
    ])
    def test_mixed_body_persists_nothing(self, api_client, student, lv2, body):
        api_client.force_authenticate(user=student)
        response = api_client.patch(self.AVATAR_URL, body, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        profile = GameProfile.objects.get(user=student)
        assert profile.mascot_name == 'Circuit'
        assert profile.avatar_headgear == 'none'
        assert profile.avatar_color == 'classic'
        assert profile.avatar_eyes == 'none'
        assert profile.avatar_held == 'none'
        assert profile.avatar_companion == 'none'


@pytest.mark.django_db
class TestAvatarCatalogIntegrity:
    """
    The catalog validates itself at import (ImproperlyConfigured), but these
    pin the rules a bad edit is most likely to break with a readable failure.
    """

    def test_every_required_badge_exists(self):
        from gamification.catalog import BADGE_CATALOG
        known = {b['key'] for b in BADGE_CATALOG}
        for item in AVATAR_CATALOG:
            if item['unlock_type'] == 'badge':
                assert item['required_badge'] in known, (
                    f"{item['slot']}/{item['key']} gates on an unknown badge"
                )

    def test_every_slot_has_an_unconditional_level_1_default(self):
        from gamification.avatar_catalog import SLOTS, SLOT_DEFAULTS, get_item
        for slot in SLOTS:
            default = get_item(slot, SLOT_DEFAULTS[slot])
            assert default is not None, f'{slot} default missing from catalog'
            assert default['unlock_type'] == 'level'
            assert default['required_level'] == 1

    def test_keys_are_unique_within_each_slot(self):
        seen = set()
        for item in AVATAR_CATALOG:
            pair = (item['slot'], item['key'])
            assert pair not in seen, f'duplicate {pair}'
            seen.add(pair)

    def test_slots_cover_the_model_fields(self):
        from gamification.avatar_catalog import SLOTS
        for slot in SLOTS:
            assert hasattr(GameProfile(), f'avatar_{slot}'), (
                f'SLOTS lists {slot!r} but GameProfile has no avatar_{slot}'
            )

    def test_badge_and_streak_items_do_not_double_gate_on_level(self):
        for item in AVATAR_CATALOG:
            if item['unlock_type'] in ('badge', 'streak'):
                assert item['required_level'] == 1, (
                    f"{item['slot']}/{item['key']} would be blocked by the "
                    'level gate as well as its own'
                )
