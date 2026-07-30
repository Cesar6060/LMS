# Handoff: Phase 59 — Django 4.2.30 → 5.2.16 LTS upgrade

## Current state
Phase 59 complete on `feat/phase-59-django-5-2-upgrade`;
**PR #77 open on Cesar6060/LMS, awaiting user merge**. Delivered:
- `backend/requirements.txt`: Django pinned to 5.2.16 (latest 5.2 patch,
  OSV 0 advisories). No other pins touched; pyjwt==2.13.0 intact.
- `backend/pytest.ini`: `error::django.utils.deprecation.
  RemovedInDjango60Warning` added last in filterwarnings, with a comment
  explaining last-match-wins ordering (guard against future ignore lines).
- CSP comment in `backend/config/settings.py` rewritten: 5.2 admin pages
  we serve emit ZERO inline styles; 'unsafe-inline' kept as headroom only.
- Stale 4.2 refs fixed in README.md (tracked) and CLAUDE.md, PORTFOLIO.md,
  INTERVIEW_GUIDE.md, DEMO_SCRIPT.md (all gitignored — local-only edits).
Verified: /verify-stack PASS twice — 631 backend tests (113s, in
container), tsc 0, eslint 0. `makemigrations --check` clean; NO new
migrations. Neon prod in sync (84/84 local plan applied; extras are 4
historical authtoken rows). Full click-through done: student+instructor
login/logout, ROB101 lesson + 4/4 comprehension check, instructor
outline, /admin/ with no CSP violations, password-reset email rendered.
Reviews: code-reviewer APPROVE WITH NITS (all fixed, `dc207d4`);
adversarial-tester 0 BROKEN, 12 HELD.

## In progress / not done
- **PR #77 merge** — user decision. No migrations; deploy is pin-only.
- Post-merge (user): confirm Render `PYTHON_VERSION=3.12`, then check
  api.stemquests.com/api/health/?deep=1 + a stemquests.com login.

## Next steps
1. User: merge PR #77, verify prod health + login after Render deploy.
2. Worthwhile test-infra items from review (small, any future phase):
   promote the warning-filter 3-way check to a permanent test; add
   no-slash route coverage for /api/auth/user and /api/auth/password/reset.
3. Carried items: XP double-award schema fix, JAVA101 answer-rotation
   reseed, phase-56 regression click-through, school-device login test,
   Sentry LoginPage TypeError.

## Decisions made
- Pinned 5.2.16 (not .15 or floating) — newest patch, OSV-clean, matches
  the CI pip-audit gate.
- Kept 'unsafe-inline' in style-src despite 5.2 admin needing none on our
  pages — conditional <style> in admin/change_list.html (actions-less
  changelists) and third-party widgets make dropping it fragile; comment
  now states the real reason so a future tightening pass has the facts.
- Neon prod check done via Neon MCP diff of django_migrations vs local
  `showmigrations --plan` — the literal in-container `migrate --check`
  against prod was permission-blocked; evidence is equivalent.

## Gotchas discovered
- CLAUDE.md, PORTFOLIO.md, INTERVIEW_GUIDE.md, DEMO_SCRIPT.md are
  gitignored — version-ref fixes there can't ship in a PR.
- Dangling Postgres connection to test_gamedev_db (interrupted pytest)
  cascades into misleading ObjectInUse/"database does not exist" failures
  on later runs; check pg_stat_activity on the db container, terminate
  the stale backend, rerun. Pre-existing, not 5.2-related.
- No local venv/pytest on host — backend suite runs only in-container.
- RemovedInDjango60Warning subclasses DeprecationWarning: the error line
  MUST stay after (and never gain lines below) the ignore lines.

## Files to read first
1. docs/specs/phase-59-django-5-2-upgrade.md — checklist + evidence.
2. backend/pytest.ini — warning-filter ordering + guard comment.
3. backend/config/settings.py CSP block (~line 294) — new rationale.
4. docs/handoffs/2026-07-28-phase-58-robotics-course.md — carried items.
