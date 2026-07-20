# Phase 30 — Lightweight gamification (Stage 1)

## Goal
Layer a motivating progression loop on top of the learning data the platform
already produces — **no new grading category** (ADR-019 Stage 1, ADR-020). Students
earn **XP** for completing lessons and passing quizzes, that XP maps to **levels**
with a "progress to next level" ring, a **daily streak** counts consecutive days on
which they complete a lesson, and a **fixed catalog of milestone badges** is
auto-awarded and displayed. Feedback is immediate: a lightweight **"+XP" toast** on
completion, a **level-up modal** when a threshold is crossed, and a **badge-earned
modal + persistent bell notification** when a badge is unlocked. Gamification is
**student-only**; instructors see none of it. Existing students are **backfilled**
from their completion/quiz history so they don't start at zero (streaks excepted —
they start fresh). This is additive: it hooks the existing completion/quiz choke
points and adds a new backend surface + UI; it changes no existing grading, progress,
or completion behavior.

## Decisions locked this session (2026-07-19)
- **XP = flat awards.** Lesson completion → **+50 XP**; passing a quiz → **+20 XP**.
  Awarded **once per source** (a ledger row guarantees it) — re-completing a lesson
  or re-passing a quiz never re-awards, so toggling can't farm XP.
- **Both quiz systems award +20 on first pass** — unit quizzes (`quizzes.QuizAttempt`)
  and lesson comprehension quizzes (`courses.LessonQuizAttempt`). A quiz-gated lesson
  therefore yields 50 (completion) + 20 (its comprehension quiz) = 70 the first time.
- **Levels are derived from XP**, not stored. A single formula is the source of truth
  and lives **only in the backend**; the API returns the level and the ring's fill so
  the frontend never re-implements the math (no drift).
- **Streak = "completed ≥1 lesson today."** Only lesson completion advances it (not
  logins, not quiz attempts). Evaluated in the student's saved timezone
  (`UserPreferences.timezone`, falling back to `settings.TIME_ZONE`).
- **Badges = a fixed, system-seeded catalog** (below), auto-awarded, no instructor UI.
- **Backfill XP + badges** for existing students via an **idempotent management
  command** (not a data migration). Streaks start at 0 on launch.
- **Feedback UX = toast + modals + bell.** Build a small custom toast system (none
  exists). Level-up and badge-earned reuse the existing `Dialog`. Badge earns also
  create a persistent `Notification` (new `badge_earned` type) shown in the bell.
- **Student-only.** Instructors accrue nothing and see no XP/level/streak/badge UI.
- **New Django app `gamification`** (not folded into `accounts`) — the feature is big
  enough (4 models + service + endpoints + signals + command) that its own app keeps
  `accounts` focused and eases the deferred Stage 2 (Phase 32). `GameProfile` is a
  OneToOne onto the existing `accounts.User`.

## Out of scope (do NOT touch / defer to Phase 32)
- **Leaderboards, hearts/lives, streak freezes, retry-until-mastery, skill-tree /
  course-map visualization, mascot/character.** All ADR-019 **Stage 2 (Phase 32)**.
- **Instructor-configurable badges** — catalog is code-seeded and fixed this phase.
- **Instructor gamification** — instructors have no GameProfile-driven UI; the endpoint
  returns an inert payload for them.
- **XP clawback / streak reversal on un-completion or progress reset.** XP is
  monotonic: the ledger row persists; un-completing a lesson or an instructor reset
  (`views.py:1495/1557/1588/2117`, which use bulk `.update()` and fire no signals)
  does **not** remove XP or badges. Documented, intentional.
- **Changing existing grading / gradebook / completion gating** (ADR-020) — untouched.
  Gamification reads the same events; it is not a grade.
- **Email / websocket delivery** of gamification events — bell notification only, no
  new email templates, no realtime push.
- **Changing the level formula's numbers after launch** — pick them now; re-tuning
  thresholds later is its own task (would shift everyone's displayed level).

## Relevant existing code (from Phase 30 exploration)
- **Completion choke point:** `LessonProgressUpdateSerializer.update()`
  `backend/courses/serializers.py:412-419` sets `completed_at = timezone.now()` **only**
  on the not-completed→completed transition — the single place a lesson "becomes done."
  View: `LessonProgressView` (RetrieveUpdateAPIView) `backend/courses/views.py:409-432`.
- **Unit-quiz grading:** `submit_quiz` `backend/quizzes/views.py:167-246` (creates
  `QuizAttempt`, sets `passed`); `QuizAttempt` `backend/quizzes/models.py:57-74`
  (`student`, `quiz`, `score` %, `passed`, `completed_at`).
- **Lesson-quiz grading:** `submit_lesson_quiz` `backend/courses/views.py:1701-1816`;
  `LessonQuizAttempt` `backend/courses/models.py:368-404` (`user`, `lesson`, `score`
  = correct count, `total_questions`, `passed`; `passed` requires all correct).
- **Course hierarchy:** `Course → Unit → Lesson → LessonSection`
  `backend/courses/models.py:11-129,479-527`; `Enrollment` `:132-169`;
  `LessonProgress` `:204-237` (`user`, `lesson`, `completed`, `completed_at`).
- **User & prefs:** `accounts.User` `backend/accounts/models.py:31-69` (role flag
  `is_instructor` only); `UserPreferences` `:72-122` (has `timezone`), auto-created by
  `create_user_preferences` signal `backend/accounts/signals.py:7-11`.
- **Signals wiring:** `AppConfig.ready()` imports signals in
  `backend/accounts/apps.py:8-9` and `backend/notifications/apps.py:8-9`. `courses`
  and `quizzes` have **no** `ready()`. Existing receivers are all `post_save`.
- **Notifications:** `Notification` `backend/notifications/models.py:5-33`
  (`recipient`, `type` choices `enrollment|new_lesson|announcement|reply`, `title`,
  `message`, `is_read`, `related_url`); created inside signals only; in-app pull only
  (`backend/notifications/views.py`). Frontend `NotificationBell.tsx` polls unread every
  30s and maps type→emoji in `getTypeIcon` (`types/index.ts:126` type union).
- **Frontend homes:** `DashboardPage.tsx` Quick Stats row `:171-197` (student-only,
  already uses `Trophy`/`Target` icons) — home for XP/level/streak tiles;
  `CoursePlayerPage.tsx` `handleMarkComplete` `:258-295` & `handleVideoEnded` `:316-367`
  (guard on `updated.completed === true`) and `LessonQuizSection.tsx` pass card
  `:254-302` — where XP feedback fires; `SettingsPage.tsx` (tabbed) — home for an
  **Achievements** tab.
- **Services/types pattern:** `frontend/src/services/*.ts` export an object of async
  methods over the shared `api` axios instance returning `response.data` (rule:
  no inline axios); types in the single barrel `frontend/src/types/index.ts`.
- **UI primitives:** `components/ui/` has `Card`, `Button` (`neon` variant), `Dialog`,
  `Tabs`, `Skeleton`. **No** reusable `ProgressBar`/`Badge` component and **no** toast
  system exist. Gaming CSS utilities in `index.css`: `.card-gaming`, `.progress-gaming`
  + `.progress-gaming-bar`, `.badge-gaming`, `.text-gradient-gaming`, `@keyframes
  shimmer`; `tailwindcss-animate` (`animate-in`, `fade-in`, `slide-in-from-*`) available.

## Level formula (backend source of truth)
Cumulative XP required to *reach* level `L`:  **`xp_for_level(L) = 50 · L · (L−1)`**
→ Lv1: 0, Lv2: 100, Lv3: 300, Lv4: 600, Lv5: 1000, Lv6: 1500, …
Inverse (level for a given XP, min 1):  **`level = floor((1 + sqrt(1 + 0.08·xp)) / 2)`**

For the ring the API returns, for the current level `L`:
- `level` = L
- `level_floor_xp` = `xp_for_level(L)`
- `next_level_xp` = `xp_for_level(L+1)`
- `xp_into_level` = `total_xp − level_floor_xp`
- `level_span` = `next_level_xp − level_floor_xp`
- `level_progress_pct` = `round(100 · xp_into_level / level_span)`

(The AskUserQuestion preview's "620/800" numbers were illustrative — these are the
binding values. Implement as pure helpers in `gamification/leveling.py` with unit tests.)

## Badge catalog (seeded, fixed)
Seed via a **data migration** in the `gamification` app (re-runnable/idempotent by
`key`), or a `seed_badges` step folded into the backfill command — either way keyed on
unique `key` so re-running is a no-op. Fields per badge: `key`, `name`, `description`,
`icon` (emoji), `criteria_type`, `threshold` (nullable), `order`.

| key            | name         | description                        | criteria_type    | threshold |
|----------------|--------------|------------------------------------|------------------|-----------|
| `first_lesson` | First Steps  | Complete your first lesson         | `lessons_done`   | 1         |
| `streak_7`     | On Fire      | Reach a 7-day streak               | `streak`         | 7         |
| `perfect_quiz` | Sharpshooter | Score 100% on any quiz             | `perfect_quiz`   | —         |
| `course_done`  | Scholar      | Complete every lesson in a course  | `course_complete`| —         |
| `xp_100`       | Getting Going| Earn 100 XP                        | `xp`             | 100       |
| `xp_500`       | Committed    | Earn 500 XP                        | `xp`             | 500       |
| `xp_1000`      | Unstoppable  | Earn 1000 XP                       | `xp`             | 1000      |

Criteria evaluation (all cheap, run after every award and during backfill):
- `lessons_done` → count of the student's `LessonProgress` with `completed=True` ≥ threshold.
- `streak` → `GameProfile.longest_streak` ≥ threshold (durable; unearnable via backfill
  since streaks start at 0 — intended).
- `perfect_quiz` → exists a `QuizAttempt` with `score == 100`, OR a `LessonQuizAttempt`
  with `score == total_questions` (and `total_questions > 0`).
- `course_complete` → for some active `Enrollment`, every `Lesson` in the course has a
  completed `LessonProgress` for this user (course must have ≥1 lesson).
- `xp` → `GameProfile.total_xp` ≥ threshold.

## Backend tasks
- [x] **1. Create app `gamification`.** `startapp gamification`; add to
  `INSTALLED_APPS` (`config/settings.py`); `GamificationConfig.ready()` imports
  `gamification.signals` (mirror `accounts/apps.py:8-9`); include its urls under
  `/api/gamification/` in `config/urls.py`.
- [x] **2. Models** (`gamification/models.py`) + one migration:
  - `GameProfile` — OneToOne `accounts.User` (`related_name='game_profile'`):
    `total_xp` PositiveInteger default 0, `current_streak` PositiveInteger default 0,
    `longest_streak` PositiveInteger default 0, `last_activity_date` DateField
    null=True, `created_at`/`updated_at`. Level is a **derived property** (not a field).
  - `XPEvent` — ledger for idempotency + toast source + backfill dedup: `user` FK,
    `source_type` CharField (`lesson`|`quiz`|`lesson_quiz`), `source_id` PositiveInteger,
    `amount` PositiveInteger, `created_at`. **`unique_together = ['user','source_type',
    'source_id']`** (this is what guarantees award-once).
  - `Badge` — catalog: `key` unique, `name`, `description`, `icon`, `criteria_type`,
    `threshold` (null), `order`.
  - `UserBadge` — `user` FK, `badge` FK, `earned_at` auto_now_add;
    `unique_together = ['user','badge']`.
- [x] **3. Leveling helpers** (`gamification/leveling.py`): pure `xp_for_level(L)`,
  `level_for_xp(xp)`, and a `level_progress(total_xp) -> dict` returning the ring fields
  above. No DB access. Unit-tested.
- [x] **4. Award service** (`gamification/services.py`) — the only place that mutates
  gamification state. All functions **skip instructors** (`user.is_instructor`) and
  accept an optional injectable `today`/`now` for deterministic streak tests.
  - `_award_xp(user, source_type, source_id, amount) -> bool` — `get_or_create` the
    `XPEvent`; if created, `F()`-increment `GameProfile.total_xp`; return `created`.
  - `award_lesson_completion(user, lesson, today=None) -> GamificationResult` — award
    +50 (`source_type='lesson'`), **advance the streak** (only here), evaluate badges.
  - `award_quiz_pass(user, quiz, today=None)` — +20 (`source_type='quiz'`), evaluate
    badges (no streak change).
  - `award_lesson_quiz_pass(user, lesson, today=None)` — +20
    (`source_type='lesson_quiz'`), evaluate badges (no streak change).
  - `_update_streak(profile, today)` — `today` = current date in the user's tz
    (`UserPreferences.timezone` via `zoneinfo`, blank/invalid → `settings.TIME_ZONE`).
    If `last_activity_date == today`: no-op; if `== today − 1`: `current_streak += 1`;
    else `current_streak = 1`. Set `last_activity_date = today`;
    `longest_streak = max(longest_streak, current_streak)`.
  - `_evaluate_badges(user, profile) -> list[Badge]` — `get_or_create` each satisfied
    catalog badge; return the newly created ones.
  - `GamificationResult` (plain dataclass/dict) surfaced to the API:
    `{xp_awarded, total_xp, level, leveled_up, new_badges: [{key,name,icon,...}],
    current_streak}` — `leveled_up` = `level_for_xp(before) < level_for_xp(after)`.
  - Wrap each award in `transaction.atomic()`.
- [x] **5. Signals** (`gamification/signals.py`): `post_save` on `UserBadge` (created)
  → create a `Notification` (`type='badge_earned'`, title e.g. "Badge earned: Scholar",
  `related_url` to the Achievements tab). Reuses the existing notification pattern; keeps
  badge→bell decoupled from the service.
- [x] **6. Notification type** — add `('badge_earned', 'Badge Earned')` to
  `Notification.type` choices (`backend/notifications/models.py`) + the trivial choices
  migration. (Adding a choice is non-destructive.)
- [x] **7. Hook the choke points** (award + surface a `gamification` key in the response):
  - **Lesson completion:** in `LessonProgressUpdateSerializer.update()`
    (`courses/serializers.py:412`) flag the transition (e.g. `instance._just_completed
    = True`); in `LessonProgressView` (`courses/views.py:409`) override `update()` to,
    after `save()`, call `award_lesson_completion` when the flag is set and merge the
    `GamificationResult` into the response under `gamification`. (Award in the **view**,
    not the read serializer, so the response shape is controlled there.)
  - **Unit quiz:** in `submit_quiz` (`quizzes/views.py:241`), after the attempt is saved
    and `passed`, call `award_quiz_pass` and add `gamification` to the response JSON.
  - **Lesson quiz:** in `submit_lesson_quiz` (`courses/views.py:1790`), after the attempt
    is saved and `passed`, call `award_lesson_quiz_pass` and add `gamification`.
  - If no XP was newly awarded (already earned), the award functions return
    `xp_awarded=0`; still safe to include (frontend shows nothing).
- [x] **8. Read endpoint** — `GET /api/gamification/profile/`
  (`gamification/views.py`, `IsAuthenticated`). Students: 200 with
  `{is_gamified: true, total_xp, level, level_floor_xp, next_level_xp, xp_into_level,
  level_progress_pct, current_streak, longest_streak, last_activity_date,
  badges: [earned...], all_badges: [catalog with earned:bool + earned_at]}`.
  Instructors: 200 with `{is_gamified: false}` (inert). `get_or_create` the
  `GameProfile` on read so it always exists.
- [x] **9. Serializers** (`gamification/serializers.py`) for the profile + badge shapes.
- [x] **10. Backfill command** — `python manage.py backfill_gamification` (idempotent):
  for each non-instructor user, `_award_xp` for every completed `LessonProgress`
  (+50, `source_type='lesson'`), every distinct passed `QuizAttempt.quiz`
  (+20, `quiz`), every distinct passed `LessonQuizAttempt.lesson` (+20, `lesson_quiz`),
  then `_evaluate_badges`. **Streaks untouched (stay 0).** Re-running is a no-op
  (XPEvent/UserBadge uniqueness). Also ensures the badge catalog is seeded (if not done
  via data migration). Print a summary. Must be **run manually after deploy** — note in
  handoff.
- [x] **11. Backend tests** (`gamification/tests.py`):
  - Complete a lesson → +50, `XPEvent` created, streak=1, `last_activity_date`=today.
  - **Idempotency:** toggle a lesson complete→incomplete→complete → total_xp stays 50,
    one `XPEvent`. Re-pass a quiz → no second +20.
  - **Streak:** with injected `today`, completions on consecutive days → streak
    increments; a 1-day gap → resets to 1; same-day second completion → no change;
    `longest_streak` tracks the max.
  - Unit-quiz pass → +20; lesson-quiz pass → +20; both quiz systems covered.
  - **Level derivation** via the endpoint: total_xp 100 → level 2; 600 → level 4; ring
    fields correct.
  - **Badges:** first completion → `first_lesson`; 100% unit quiz and 100% lesson quiz
    → `perfect_quiz`; crossing 100/500/1000 XP → the `xp_*` badges; completing all
    lessons of a course → `course_done`; a 7-day streak → `streak_7`; badge award is
    idempotent (no duplicate `UserBadge`).
  - `UserBadge` create → a `badge_earned` `Notification` exists for the user.
  - **Instructor** completing a lesson awards nothing; endpoint returns
    `is_gamified:false`.
  - Endpoint: student 200 shape; unauthenticated 401.
  - Completion/quiz responses include the `gamification` delta.
  - **Backfill:** seed completions + passed attempts with no gamification rows, run the
    command → correct `total_xp` + badges; run again → unchanged counts.

## Frontend tasks
- [x] **1. Types** (append to `frontend/src/types/index.ts`): `GamificationProfile`
  (the endpoint shape), `BadgeInfo` (`key,name,description,icon,earned,earned_at?`),
  `GamificationDelta` (`xp_awarded,total_xp,level,leveled_up,new_badges,current_streak`).
  Extend the return types of `updateLessonProgress`, `submitQuiz`, `submitLessonQuiz`
  to carry optional `gamification?: GamificationDelta`.
- [x] **2. Service** `frontend/src/services/gamification.ts` (object pattern):
  `getProfile(): Promise<GamificationProfile>` → `GET /gamification/profile/`.
- [x] **3. Toast system** (none exists): `contexts/ToastContext.tsx` +
  `components/ui/Toast.tsx` — `useToast().show({ message, icon?, variant? })`, stacked,
  auto-dismiss ~3s, animated with `animate-in`/`slide-in-from-bottom`. Mount
  `<ToastProvider>` in `App.tsx`'s provider tree.
- [x] **4. Reusable primitives:** `components/ui/ProgressBar.tsx` (fill %, reuses
  `.progress-gaming`), and gamification pieces under `components/gamification/`:
  `LevelRing.tsx` (level + ring from the profile's ring fields), `StreakFlame.tsx`
  (streak count + flame), `BadgeCard.tsx` (earned = bright, locked = greyed w/ tooltip),
  `BadgeGrid.tsx`, `LevelUpModal.tsx` + `BadgeEarnedModal.tsx` (both reuse `Dialog`).
- [x] **5. Dashboard tiles** — in `DashboardPage.tsx` Quick Stats row (`:171-197`,
  student-only), add a **Level** tile (`LevelRing`) and a **Streak** tile
  (`StreakFlame`), fed by `getProfile()`. Match the existing `card-gaming` tile styling.
- [x] **6. Completion feedback** — in `CoursePlayerPage.tsx` read `gamification` from the
  `updateLessonProgress` response in `handleMarkComplete` (`:266`, guard
  `updated.completed === true`) and `handleVideoEnded` (`:338`): if `xp_awarded > 0`
  → toast "+{xp} XP"; if `leveled_up` → `LevelUpModal`; for each `new_badges` →
  `BadgeEarnedModal`. Same wiring for quiz passes in `LessonQuizSection.tsx`
  (`handleSubmitQuiz`, pass card `:254-302`) and the unit-quiz submit flow.
- [x] **7. Achievements tab** — add an **"Achievements"** tab to `SettingsPage.tsx`
  (student-only; hidden for instructors) rendering a large `LevelRing`, `StreakFlame`
  (current + longest), and `BadgeGrid` (earned + locked from `all_badges`).
- [x] **8. Bell icon** — add a `badge_earned` case to `NotificationBell.tsx`
  `getTypeIcon` and to the `NotificationType` union in `types/index.ts:126`.
- [x] **9. Instructor gating** — no XP/level/streak/badge UI renders when
  `isInstructor` (skip the dashboard tiles, the Achievements tab, and all toasts/modals).

## Verification
Run `/verify-stack` first (must stay green), then the phase-specific checks.

- [x] **pytest** — `docker compose exec -T backend pytest`: baseline **203** plus the
  new `gamification` tests all pass, including the idempotency, streak (with injected
  `today`), backfill-rerun, and instructor-inert cases.
- [x] **tsc** — `cd frontend && npx tsc --noEmit`: **0 errors**.
- [x] **lint** — `cd frontend && npm run lint`: **0 errors** (warning baseline ~23).
- [x] **db-migration-checker** — run over the new `gamification` migration + the
  `Notification` choices migration: new tables only, no destructive ops, reversible.
- [x] **Backfill** — run `docker compose exec -T backend python manage.py
  backfill_gamification`, then re-run it: second run reports zero new XPEvents/badges
  (idempotent).
- [ ] **Manual click-through (hand to user — no browser automation in agent env):**
  1. As a **student**, complete a lesson → **"+50 XP" toast**; dashboard Level tile and
     Streak tile update (streak = 1).
  2. Pass a quiz → **"+20 XP" toast**.
  3. Keep earning until a level threshold is crossed → **Level-Up modal** fires once.
  4. Earn `first_lesson` → **Badge-earned modal** + a **bell notification** (badge icon).
  5. Open **Settings → Achievements** → large level ring, current + longest streak, and
     the badge grid (earned bright, locked greyed with tooltips).
  6. Re-complete / reset a lesson → **no** XP change (monotonic), no duplicate toast.
  7. Log in as an **instructor** → **no** gamification UI anywhere (tiles, tab, toasts).
  8. Confirm a pre-existing student (post-backfill) shows non-zero XP/level and any
     earned milestone badges, with streak at 0.

## Notes
- **Base branch:** cut `feat/phase-30-gamification` from `lms/main` (remote `lms`;
  `gh --repo Cesar6060/LMS`) after the Phase 29 PR merges. Do not stack on the phase-29
  branch. If #-for-29 is still open, branch from merged main once it lands.
- **Award-once discipline:** the `XPEvent` `unique_together` is the correctness core —
  every XP path goes through `_award_xp`; nothing increments `total_xp` directly.
- **Streak testability:** the injectable `today` param exists specifically because
  `Date.now()`/wall-clock is non-deterministic — tests must pass explicit dates.
- **Backfill is manual** — it does not run on deploy/migrate. Call it out in the handoff.
- Commits: `feat:` for the app + hooks + UI; a `docs:` commit for this spec + the
  handoff. Conventional format, **no Co-Authored-By** (per CLAUDE.md).
- `PLAN.md` + `CLAUDE.md` are gitignored — not in the diff. Update this spec's
  checkboxes as items land.
