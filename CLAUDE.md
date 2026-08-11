# STEM Quest

Educational LMS for Computer Science (including video game development) and Robotics courses.

This file and `.claude/` are tracked in a **public** repo. Nothing secret, no
private URLs, no credentials in either.

## Tech Stack
- Backend: Django 5.2 LTS + DRF + PostgreSQL 16 (in `backend/`)
- Frontend: React 18 + TypeScript + Vite + Tailwind (in `frontend/`)
- Auth: django-allauth + dj-rest-auth (JWT). Runs via Docker Compose.

## Commands
```bash
docker compose up -d                        # start stack
docker compose restart backend              # after backend changes
docker compose exec -T backend pytest       # backend tests (~280s, --cov forced)
cd frontend && npx tsc --noEmit             # type check (must pass before done)
cd frontend && npm run lint                 # lint
cd frontend && npm test                     # vitest (CI runs it; so must you)
```
There is no host Python — a bare `pytest` cannot run. Also: bare `head` on this
machine is shadowed by an unrelated Perl tool, so use `/usr/bin/head`.

## Layout
- `backend/`: accounts, courses, quizzes, discussions, gamification, notifications (Django apps) + `core/` (not an installed app)
- `core/` is a package of **mandatory call-throughs**, not optional helpers:
  `email.py` (always pass `triggered_by`), `demo.py` (demo write-blocking),
  `throttling.py` (never use stock DRF throttle classes), `uploads.py`
  (verification + `download_url()`), `password_validation.py`,
  `permissions.py`, `pagination.py`. Reimplementing any of them locally is a bug.
- `frontend/src/`: components, pages, services, contexts, types
- Detailed conventions load automatically from `.claude/rules/`, split by path:
  `backend.md` / `frontend.md` are the always-on cores, plus `backend-views.md`,
  `backend-serializers.md`, `backend-tests.md`, `backend-migrations.md`,
  `frontend-services.md`, `frontend-components.md`, `frontend-tests.md`.

## Workflow rules
- Work happens in phases. `/start-phase` writes the spec, `/verify-stack` gates
  the work, `/finish-phase` closes it out, `/handoff` ends the session.
- Before starting a phase, read the latest file in `docs/handoffs/` and the phase spec in `docs/specs/` (if one exists). Specs + handoffs are the source of truth for project state; there is no roadmap file (PLAN.md was retired at phase 50 — archive at `docs/archive/PLAN.md`).
- Run `/verify-stack` before declaring any task complete. Show the output as evidence.
- At the end of a work session, run `/handoff` to write a handoff file.
- Update the phase spec checklist as items complete.

## Git
- No "Co-Authored-By" lines in commits
- Conventional commit format (feat:, fix:, chore:)
- Feature branches always — never commit directly to `main`. `main` is
  protected: both CI jobs required with `strict: true`, force-pushes and
  deletions blocked. But `enforce_admins` is deliberately **off**, so an admin
  override can still put a red build into production. The protection is a
  backstop, not permission to skip verify.
- `origin` must resolve to `Cesar6060/LMS`, and `gh`'s default repo is set to
  the same. Check with `git remote -v` and `gh repo set-default --view` before
  pushing or opening a PR. (The retired `dev-learning-platform` repo is kept as
  the `old-origin` remote; two earlier phases opened PRs on it by accident.)
- Merging is the user's decision, made in the GitHub UI. `gh pr merge` is denied
  by `.claude/settings.json`.

## Gotchas
- Backend changes require `docker compose restart backend` to take effect
- **Never run pytest while a review subagent is also running it.** Both use the
  shared `test_gamedev_db` and the collision produces hundreds of bogus errors
  that look like real failures. This has cost real time twice.
- Merging to `main` deploys **both** targets: the backend on Render
  (`branch: main` in `render.yaml`) and the frontend on Cloudflare Pages.
  Migrations run automatically via `preDeployCommand` and a failure aborts the
  deploy — but that only guarantees ORDERING. The pre-deploy runs while the old
  code is still serving, so every migration must still be additive and
  old-code-safe (nullable columns; `db_default` on new NOT NULL fields).
- `/api/health/?deep=1` only runs `SELECT 1` — it cannot detect a missing
  column and will report 200 through a total outage. Verify a deploy with a
  real content read as well.
