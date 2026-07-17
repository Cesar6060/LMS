# Handoff: Phase 13 Discussion Forums (shipped) + README demo credentials (pending)

## Current state
Phase 13 — Discussion Forums is **complete and shipped**. Spec `docs/specs/phase-13-discussion-forums.md` is fully checked off (all 44 items).
- Backend: new `backend/discussions/` app (models, serializers, views, urls, admin, `tests.py` with 29 tests, migration `0001_initial`). Added `'reply'` to `notifications/models.py` TYPE_CHOICES (migration `0002_alter_notification_type`). Registered app in `config/settings.py`; mounted urls in `config/urls.py`.
- Frontend: `services/discussions.ts`, `pages/discussions/DiscussionsPage.tsx` + `ThreadDetailPage.tsx`, discussion types in `types/index.ts`, routes in `App.tsx`, Discussions section in `pages/courses/CourseDetailPage.tsx`.
- Also added `frontend/eslint.config.js` (was missing entirely) + fixed 7 pre-existing lint errors (CoursePlayerPage, LessonPage, StudentRosterPage, MyGradesPage, MakeAnnouncementModal, Input.tsx).
- **Verified (all green):** pytest 186 passed · `tsc --noEmit` 0 errors · `npm run lint` 0 errors (28 pre-existing exhaustive-deps warnings, exits 0). All run via `docker compose exec`.
- **Git:** new remote `lms` → github.com/Cesar6060/LMS. Pushed `main` as base, then 3 commits on `feat/phase-13-discussion-forums` → **PR #1** (github.com/Cesar6060/LMS/pull/1).

## In progress / not done
README demo-credentials fix — **not started** (user deferred to a new session). Plan saved at `/Users/cesar/.claude/plans/did-we-alread-do-breezy-sloth.md`.
- `README.md:106-117` "Demo Accounts" table lists password `password123` which is **WRONG**; real seeded password is `Admin123!`.
- Demo accounts do NOT exist in the running dev DB yet — `seed_data` has never been run against it (verified: instructor@demo.com NOT FOUND).

## Next steps
1. Fix `README.md:114-117`: change both passwords `password123` → `Admin123!`; add login URL `http://localhost:5173/login`. Note student1-5 share the password.
2. Ask user (was interrupted before answering): (a) also run `docker compose exec backend python manage.py seed_data` so accounts actually work? (b) delivery — new branch+PR on LMS, onto the Phase 13 branch, or local edit only?
3. Consider: README.md:94 still clones the OLD repo (`dev-learning-platform`); user has moved to LMS — may want that updated too (confirm first).

## Decisions made
- Followed `quizzes` app pattern (function-based `@api_view` + local `is_course_instructor`/`is_enrolled` helpers) per spec; notification idiom copied from `Announcement`.
- Added the missing eslint flat config + fixed pre-existing errors (user chose "fix the 7 errors" over ignoring) so verify-stack's lint gate actually runs.
- Pushed full `main` history to LMS as the PR base (preserves provenance) rather than a squashed fresh start; old repo being archived.

## Gotchas discovered
- Shell has a broken `head` alias (resolves to an HTTP HEAD tool) — piping to `head` errors. Avoid it; use `sed -n`/grep or Read.
- Stack runs in Docker — run pytest/tsc/lint via `docker compose exec`, not bare host commands.
- `seed_data` is NOT run on container startup; demo accounts require running it manually. Seeded password is `Admin123!` (README is stale). Login is by email (`USERNAME_FIELD='email'`).

## Files to read first
- `/Users/cesar/.claude/plans/did-we-alread-do-breezy-sloth.md` (the pending README task)
- `README.md` (lines 85-118, Quick Start / Demo Accounts)
- `backend/courses/management/commands/seed_data.py` (authoritative credentials)
- `docs/specs/phase-13-discussion-forums.md` (completed spec, for context)
