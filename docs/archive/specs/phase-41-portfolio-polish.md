# Phase 41: Portfolio Polish — README rewrite + public demo account

## Goal

Make the repo and the live deployment presentable to portfolio viewers.
Two deliverables: (1) rewrite `README.md` around the *deployed product* —
live URLs, real production stack (Render/Neon/Cloudflare/R2/Sentry/
UptimeRobot), existing screenshots, and a working demo login — instead of
the current local-Docker-only, VGD101-era document; (2) create a safe
public demo account `jdoe@demo.com` / `Admin123!` (plain student, never
superuser or instructor) enrolled in JAVA101 with partial progress, via a
new idempotent management command with a `--reset` flag so the account can
be restored to baseline whenever public visitors trash it.

## Decisions made (interview 2026-07-21)

- Demo account is **student only**. Instructor views are shown via README
  screenshots, not a live login (a public instructor could edit JAVA101).
- Seeding/reset via a **new management command** (`seed_demo_account`),
  run from a local machine against Neon (Render free tier has no shell —
  same `DATABASE_URL` pattern as `docs/runbooks/phase-38-deploy-steps.txt`
  Step 1).
- Reset is **manual only** — run the command when needed. No cron.
- **Keep the existing 7 screenshots** in `docs/screenshots/` (2026-07-20).

## Out of scope

- Production email backend (`EMAIL_BACKEND` still console) — top of backlog, separate phase
- DB backups (`pg_dump` against Neon)
- Frontend bundle code-splitting (1.29 MB warning)
- Deleting `r2-check@example.com` (still an /admin/ chore)
- Automated/scheduled demo reset (GitHub Actions cron etc.)
- Instructor demo account or sandbox course
- Retaking screenshots against the live site
- Any frontend code changes
- UptimeRobot dashboard cleanup (delete paused monitor 803564196) and the
  Gmail-Trash filter investigation — user dashboard chores, not repo work

## Backend tasks

- [x] `backend/courses/management/commands/seed_demo_account.py`:
  - [x] Creates user `jdoe@demo.com`, password `Admin123!`,
        `first_name='Jordan'`, `last_name='Doe'`, `is_instructor=False`,
        `is_staff=False`, `is_superuser=False` — assert all three flags
        false even if the user already exists (defense against drift)
  - [x] Creates a **verified** allauth `EmailAddress` row (required for login)
  - [x] `Enrollment.objects.get_or_create` into JAVA101; exit with a clear
        error (non-zero) if JAVA101 does not exist — never create it
  - [x] Baseline progress: all Unit 1 lessons `completed=True` with
        `completed_at` set; first lesson of Unit 2 partially read
        (`current_section` mid-lesson, `completed=False`); nothing beyond
  - [x] Idempotent: rerunning re-asserts password, name, flags, verified
        email, enrollment, and baseline progress without touching anything else
  - [x] `--reset` flag: delete ALL rows owned by the demo user beyond
        baseline — `LessonProgress`, unit-quiz attempts
        (`QuizAttempt`/`AttemptAnswer`), lesson-quiz attempts
        (`LessonQuizAttempt`/`LessonAttemptAnswer`), discussion
        posts/threads, notifications, gamification records (XP/badges),
        `UserPreferences` customizations — then re-apply baseline progress
        and re-assert credentials/profile (visitors can change them via
        settings)
  - [x] Command never touches other users, course content, or any
        non-demo data; scope every delete by `user=demo_user`
- [x] pytest coverage (add to existing courses tests or a new
      `test_seed_demo_account.py`):
  - [x] creates the user with correct flags and verified email
  - [x] enrolls in JAVA101 with the exact baseline progress shape
  - [x] errors cleanly when JAVA101 is absent
  - [x] running twice is a no-op (idempotency)
  - [x] `--reset` wipes extra progress/attempts/posts and restores baseline
  - [x] never produces `is_superuser=True` / `is_staff=True`

## README tasks

- [x] Rewrite `README.md` portfolio-first:
  - [x] Hero: what STEM Quest is, **live app URL**
        `https://stemquest.cesarvillarreal11.workers.dev`, API URL
        `https://stemquest-api.onrender.com`, and the demo login
        (`jdoe@demo.com` / `Admin123!`, note it resets periodically and a
        first request may take ~a minute if the free-tier backend is cold)
  - [x] Screenshots section reusing the 7 PNGs in `docs/screenshots/`
  - [x] Production architecture section (source:
        `docs/deployment-tools.txt`): Cloudflare Workers (frontend) →
        Render/gunicorn/WhiteNoise (Django API) → Neon Postgres; R2 media
        via django-storages; Sentry (django + react projects); UptimeRobot
        monitors incl. keep-warm ping; GitHub Actions CI gating merges
  - [x] Tech stack table corrected: production services as above; Docker
        Compose repositioned as local-dev only; drop Redis/WebSockets
        claims (Channels deps are commented out)
  - [x] Local dev Quick Start retained but secondary, after the live-demo
        content
  - [x] Demo Accounts section fixed: live demo login (jdoe) vs local-only
        `seed_data` accounts clearly separated, with the existing "never
        run seed_data against prod" caveat
  - [x] Remove stale content: `assignments/` app from the project
        structure (removed in Phase 18), VGD101-centric framing (JAVA101
        is the flagship course)
  - [x] Link `docs/specs/deployment-overview.md` and `docs/runbooks/` for
        deep-dive readers; keep MIT license and the CI badge
        (already points at `Cesar6060/LMS`)

## Frontend tasks

None. No frontend code changes in this phase.

## Production rollout (manual, after code merges)

- [ ] From local machine, run `seed_demo_account` against Neon:
      `docker compose exec -it -e DATABASE_URL="$(cat …/.neon_url)" -e
      DEBUG=True backend python manage.py seed_demo_account`
      (same pattern as phase-38 runbook Step 1)
- [ ] Log in at the live URL as `jdoe@demo.com` and click through:
      dashboard shows JAVA101 with Unit 1 complete; course map loads;
      learning mode opens the partially-read Unit 2 lesson
- [ ] Confirm jdoe cannot reach instructor pages or `/admin/`

## Verification

- [x] `/verify-stack` passes: pytest (376 existing + new command tests),
      `npx tsc --noEmit` 0 errors, lint at baseline (22 warnings)
- [x] Local end-to-end: `seed_demo_account` against local DB, log in as
      jdoe in the local frontend, JAVA101 progress visible
- [x] `seed_demo_account --reset` after making extra progress as jdoe
      restores the baseline state exactly
- [ ] README renders on GitHub: all 7 screenshot links resolve, live URLs
      correct, no references to removed apps/features
- [ ] Production rollout checklist above completed and demo login verified
      at the live URL
