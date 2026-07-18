# Handoff: Phase 18 submission removal — verification

## Current state
Phase 18 (assignment/submission system removal) is implemented and committed on
branch `feat/phase-18-submission-removal` (commit `eed9232`). This session ran
the final verification after an interrupted prior session:

- `docker compose exec backend pytest` — 192 passed (includes
  `test_assignments_app_is_gone` and new gradebook/migration tests).
- `cd frontend && npx tsc --noEmit` — 0 errors.
- `cd frontend && npm run lint` — 0 errors (24 pre-existing
  `react-hooks/exhaustive-deps` warnings, unrelated to this phase).
- Grep sweep: zero `assignment|submission` hits in `frontend/src`; backend hits
  are only intentional survivors (negative tests, migration files, C# lesson
  content about "assignment operators").
- `backend/assignments/` and `backend/media/submissions/` confirmed gone.

Modified this session: `docs/specs/phase-18-submission-removal.md` (checked off
the `/verify-stack` item with evidence) — not yet committed.

## In progress / not done
- Two spec checklist items remain unchecked in
  `docs/specs/phase-18-submission-removal.md`: the manual click-throughs
  (instructor: dashboard/manage course/gradebook/CSV/grading-config modal;
  student: dashboard/course detail/quiz/My Grades/settings/notification bell).
- Spec checklist update is uncommitted.

## Next steps
1. Do the two manual click-throughs (stack is already up via
   `docker compose up -d`; frontend at http://localhost:5173) and check them
   off in the spec.
2. Commit the spec/handoff docs (`docs:` conventional commit) on
   `feat/phase-18-submission-removal`.
3. Open/update the PR to `main` for phase 18 (push to remote `lms`).
4. Next candidate phase after merge: Instructor Analytics Dashboard (per spec's
   out-of-scope note).

## Decisions made
- Manual click-throughs left unchecked rather than marked done: they require a
  human in the browser; automated checks alone don't satisfy them.
- Grep survivors accepted as intentional (negative tests, historical
  migrations, coincidental "assignment operators" lesson content) — no further
  cleanup needed.

## Gotchas discovered
- `pytest` is not installed on the host; run it via
  `docker compose exec backend pytest`.
- The user's shell shadows `head` with a Perl LWP tool — use `sed -n '1,Np'`
  or `/usr/bin/head` in scripts.

## Files to read first
1. `docs/specs/phase-18-submission-removal.md` — full checklist + evidence.
2. `backend/courses/views.py` — rebuilt gradebook/CSV/grade-summary endpoints.
3. `frontend/src/pages/instructor/GradebookPage.tsx` — new matrix UI.
4. `frontend/src/pages/student/MyGradesPage.tsx` — quiz + participation view.
5. `backend/courses/migrations/0014_two_weight_grading_config.py` — weight
   redistribution data migration.
