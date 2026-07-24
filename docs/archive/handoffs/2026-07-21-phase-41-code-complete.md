# Handoff: Phase 41 code complete — PR #32 open, prod rollout pending

## Current state

Phase 41 (portfolio polish) code is DONE and waiting on PR
https://github.com/Cesar6060/LMS/pull/32 (branch
`feat/phase-41-portfolio-polish`). Created this session:

- `backend/courses/management/commands/seed_demo_account.py` — creates/
  re-asserts the public demo student `jdoe@demo.com` / `Admin123!`
  (never staff/superuser/instructor, verified allauth email), enrolls
  in JAVA101, applies baseline (Unit 1 complete, first Unit 2 lesson at
  mid-section), `--reset` wipes all visitor data scoped to the user.
- `backend/courses/test_seed_demo_account.py` — 7 tests, all pass.
- `README.md` rewritten portfolio-first (live URLs, demo login, prod
  architecture, corrected stack table, stale assignments/WebSockets/
  VGD101 content removed).
- `docs/specs/phase-41-portfolio-polish.md` checklist ticked except
  rollout items.

`/verify-stack` PASS: pytest 383 passed (Docker), tsc 0 errors, lint
0 errors / 22 warnings (baseline). Local e2e done: jdoe login via API,
403 on instructor endpoint, `--reset` restored exact 5-row baseline.

## In progress / not done

Production rollout (spec section "Production rollout") — blocked on
merging PR #32 first.

## Next steps

1. Merge PR #32 (Cesar merges — never auto-merge; deploys to prod).
2. Run from local machine: `docker compose exec -it -e
   DATABASE_URL="$(cat <path>/.neon_url)" -e DEBUG=True backend
   python manage.py seed_demo_account` (phase-38 runbook Step 1 pattern).
3. Log in at https://stemquest.cesarvillarreal11.workers.dev as jdoe:
   dashboard shows JAVA101 Unit 1 complete; course map loads; learning
   mode opens partially-read "Number Types" lesson. Confirm no
   instructor pages / no /admin/ access.
4. Confirm README renders on GitHub (7 screenshots, live URLs), then
   tick the last spec checkboxes.

## Decisions made

- Baseline `current_section` computed as `sections.count() // 2` (not
  hardcoded) so it survives content edits.
- Plain rerun never downgrades visitor progress; only `--reset` forces
  the exact baseline — matches spec's "no-op" idempotency wording.
- `--reset` also deletes non-JAVA101 enrollments and stray EmailAddress
  rows (both user-scoped) under "ALL rows owned by the demo user".
- No XP/GameProfile baseline seeded — direct LessonProgress writes don't
  award XP and the spec doesn't ask for it; demo shows 0 XP until the
  visitor does something.

## Gotchas discovered

- Login API returns dj-rest-auth token `{"key": ...}`, not JWT `access`
  — use `Authorization: Token <key>` when curling.
- Profile serializer has `email` read-only, so keying the command on
  the email is safe against visitor edits.

## Files to read first

- `docs/specs/phase-41-portfolio-polish.md` — remaining unticked items
- `backend/courses/management/commands/seed_demo_account.py`
- `docs/runbooks/phase-38-deploy-steps.txt` — Step 1 (Neon DATABASE_URL)
- `README.md` — verify rendering after merge
