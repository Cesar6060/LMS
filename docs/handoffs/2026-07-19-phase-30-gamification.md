# Handoff: Phase 30 — Lightweight gamification (Stage 1)

## Current state
Phase 30 **implemented + verified + committed** on `feat/phase-30-gamification`
(cut from Phase 29 HEAD — see Decisions). Working tree: this handoff only. **Not pushed.**
Commits: `3ba3b89` feat (app + hooks + UI), `774c52f` docs (spec + handoff).

New `backend/gamification/` app: `models.py` (GameProfile/XPEvent/Badge/UserBadge),
`leveling.py` (formula = single source of truth), `services.py` (award engine,
award-once via XPEvent uniqueness, tz-aware streak), `catalog.py`, `signals.py`
(badge→bell, w/ `suppress_badge_notifications`), `views/serializers/urls.py`
(`GET /api/gamification/profile/`), `management/commands/backfill_gamification.py`,
migrations `0001_initial`+`0002_seed_badges`, `tests.py` (45 tests).
Hooks: `courses/serializers.py` + `courses/views.py` (LessonProgressView.update +50),
`quizzes/views.py` submit_quiz (+20), `courses/views.py` submit_lesson_quiz (+20),
`notifications/models.py` + `0005_alter_notification_type` (badge_earned).
Frontend: `types/index.ts`, `services/gamification.ts`, `contexts/ToastContext.tsx`,
`components/ui/{Toast,ProgressBar}.tsx`, `components/gamification/*` (LevelRing,
StreakFlame, BadgeCard/Grid, LevelUp/BadgeEarned modals, useGamificationFeedback);
wired into `main.tsx`, `DashboardPage`, `CoursePlayerPage`, `LessonQuizSection`,
`QuizDetailPage`, `SettingsPage` (Achievements tab), `NotificationBell`.

Verified: **pytest 248 passed** (203+45); **tsc 0 errors**; **lint 0 errors/25 warn**
(baseline ~23); **db-migration-checker clean**; **backfill idempotent** (2nd run 0 new);
**code-reviewer: no correctness bugs**.

## In progress / not done
- **Manual click-through** — the only unchecked spec item (agent can't drive a browser).
- Branch not pushed; no PR.

## Next steps
1. Manual click-through (spec §Verification): student completes lesson → "+50 XP"
   toast + dashboard tiles; quiz pass → "+20 XP"; cross level → Level-Up modal once;
   `first_lesson` → badge modal + bell 🏅; Settings→Achievements shows ring/streak/grid;
   re-complete → no XP change; instructor → no gamification UI.
2. After deploy, run once (NOT run by migrate):
   `docker compose exec -T backend python manage.py backfill_gamification`.
3. Rebase onto merged `lms/main` once Phase 29 lands, then push + open PR
   (`gh --repo Cesar6060/LMS`).

## Decisions made
- **Branched off Phase 29 HEAD**, not `lms/main`: Phase 29 isn't merged, so `lms/main`
  would drop its work. Rebase before PR.
- **Level derived, never stored**; API returns level + ring so frontend never re-derives.
- **Suppressed badge bell notifications during backfill** (reviewer note): historical
  badges shouldn't ping students "just earned"; still show in Achievements grid.
- Left two reviewer notes as-is (intentional): zero-enrollment students see no tiles
  (matches Quick Stats gating); cross-day un/re-complete advances streak without XP.

## Gotchas discovered
- `head` is shadowed in this shell (HTTP tool) — never pipe to `| head`.
- Badge criteria `lessons_done`/`course_complete` read `LessonProgress`, written by the
  view *before* the award call — direct service tests must create it first.
- `migrate <app>` takes one app label; use bare `migrate` to apply all.

## Files to read first
- `backend/gamification/services.py` (award engine + streak)
- `backend/gamification/leveling.py` (formula)
- `backend/gamification/tests.py` (behavior spec)
- `frontend/src/components/gamification/useGamificationFeedback.tsx` (feedback wiring)
- `docs/specs/phase-30-gamification.md` (only manual click-through open)
