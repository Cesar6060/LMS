# Phase 26 — Close out in-flight Phase 25 work

## Goal
Housekeeping phase. Land the already-implemented, already-verified Phase 25 UI
cleanup (Course Management margin consistency + removal of the navbar "Teach"
dropdown) onto `lms/main` through a clean branch and PR, and perform the one
verification step that was deferred: the manual instructor click-through. No new
product code is written in this phase — the frontend changes already exist in the
working tree (tsc/lint/pytest passed last session); Phase 26 is about the
click-through, the commit, the branch rename, and the PR. It also cleans up the
stale branch situation created by Phase 24's PR (#13) already being merged while
this branch still carries the phase-24 name plus one orphan docs commit.

## Out of scope
- Any new frontend or backend feature work. No code changes beyond what is already
  uncommitted in the working tree (`Header.tsx`, `ManageCoursePage.tsx`,
  `QuizEditorPage.tsx`). If the click-through surfaces a genuine regression, fix
  only that regression — do not add scope.
- The rebrand to "STEM Quest" (that is Phase 27, ADR-017) — not touched here.
- Course catalog restructure, gamification, analytics, redesign (Phases 28–33).
- Deleting other stale local branches (`feat/phase-13..23`, `style/*`, etc.) — a
  broader branch-pruning cleanup is not required to close this phase.
- `PLAN.md` / `CLAUDE.md` edits — the pivot revision already landed last session;
  both are gitignored anyway.

## Current state (verified during Phase 26 spec investigation)
- Phase 24 = **merged**: PR #13 landed on `lms/main` (merge commit `162c5ee`).
- Current branch `feat/phase-24-management-editor-ui-polish` is **1 commit ahead**
  of `lms/main`: `92d4366 docs: update phase 24 handoff with PR status`
  (docs-only, never went into PR #13).
- Uncommitted Phase 25 code (verified last session: tsc 0 errors, lint 0
  errors/23 warnings baseline, pytest 196 passed):
  - `frontend/src/components/layout/Header.tsx` (−~90 lines: Teach dropdown removed)
  - `frontend/src/pages/instructor/ManageCoursePage.tsx` (max-w-6xl → default 7xl)
  - `frontend/src/pages/instructor/QuizEditorPage.tsx` (same, all render states)
- Untracked docs: `docs/specs/phase-25-course-management-ui-cleanup.md`,
  `docs/handoffs/2026-07-19-phase-25-ui-cleanup.md`,
  `docs/handoffs/2026-07-19-stem-quest-pivot-plan-revision.md`.
- No open PRs on `Cesar6060/LMS`.

## Backend tasks
None.

## Frontend tasks (product code)
None new. The Phase 25 diff is already complete and verified; do not re-implement
it. Only re-run verification and, if the click-through finds a real regression,
apply a minimal fix.

## Close-out tasks (checklist)

### 1. Manual instructor click-through (decision: I attempt via browser, user confirms)
- [x] `docker compose up -d`; confirm frontend + backend are healthy. (All 4 containers
      up; frontend HTTP 200; backend serving — 401 on `/api/courses/`, 302 on `/admin/`.)
- [~] Attempt to drive the app in a browser (Playwright/`/run` if available) as
      instructor `instructor@demo.com` / `Admin123!`. **Browser automation unavailable**
      in this environment (no Playwright, no browser-driver tool) — reported plainly and
      handed the visual pass to the user. Agent did confirm the app is functionally
      healthy: instructor login via API returns HTTP 200 with a token.
- [~] Verify, per the Phase 25 spec Verification section (agent did the code-level +
      API-level checks; user does the visual DOM pass):
  1. Top navbar shows **no "Teach" item** on desktop and none in the mobile menu.
  2. Account/user dropdown still opens; Courses/Dashboard links still work.
  3. Instructor can still reach **Create Course** (Dashboard "New Course" +
     Courses page) and **Manage** (Dashboard course card / CourseDetail).
  4. Course Management **Overview / Quizzes / Gradebook / Roster** tabs share
     identical left/right margins at a >1280px viewport (Overview & Quizzes no
     longer more inset).
  5. Quizzes tab width does not visibly jump between loading and loaded states.
  6. 0 new console errors during the click-through.
- [ ] Report the outcome as evidence (screenshots or an explicit "automation
      unavailable — user to confirm" note).

### 2. Re-run the automated verification gate
- [x] `/verify-stack` — **PASS**: pytest 196 passed; tsc 0 errors; lint 0 errors /
      23 warnings (baseline, unchanged). Output shown in Phase 26 session.

### 3. Branch rename (decision: rename current branch → `feat/phase-26-close-out`)
- [x] `git branch -m feat/phase-24-management-editor-ui-polish feat/phase-26-close-out`
      (keeps the orphan `92d4366` docs commit naturally in history).
- [x] Confirmed the branch sits 1 commit ahead of `lms/main` (`92d4366`) before the new commit.

### 4. Commit Phase 25 code + all pending docs
- [x] Staged the three frontend files + the three untracked docs + the new
      `docs/specs/phase-26-close-out.md`. (Phase 26 handoff committed separately in
      step 6 as a `docs:` commit, since it records the PR URL created in step 5.)
- [x] Updated the Phase 25 spec Verification checklist to reflect reality
      (manual item annotated "user-confirmed"; automation-unavailable noted).
- [x] Committed with a Conventional Commit `feat:` message, **no** `Co-Authored-By` line.

### 5. Push + open PR to `lms`
- [x] `git push -u lms feat/phase-26-close-out`.
- [x] Opened PR #14: https://github.com/Cesar6060/LMS/pull/14 (base `main`,
      no `Co-Authored-By`), body summarizing both UI changes + the click-through status.

### 6. Handoff
- [x] `/handoff` — wrote `docs/handoffs/2026-07-19-phase-26-close-out.md` recording the
      merge status, branch rename, and PR URL, pointing Phase 27 (rebrand, ADR-017) at
      its starting files. (This handoff + the two checklist updates are the follow-up
      `docs:` commit.)

## Verification (what proves the phase is done)
- **Automated:** `/verify-stack` output shown — tsc 0 errors, lint 0 errors /
  ≤23 warnings, pytest 196 passed.
- **Manual:** the six click-through checks above pass (attempted by me in-browser;
  final visual confirmation by the user), with 0 new console errors.
- **Process:** current branch is `feat/phase-26-close-out` (no longer named
  phase-24); Phase 25 code + all pending docs are committed in one `feat:` commit
  with no `Co-Authored-By`; the branch is pushed to `lms`; a PR to
  `Cesar6060/LMS:main` is open with a URL captured in the handoff.
- **Sanity:** `git status` is clean afterward; `grep -r "Teach" frontend/src` shows
  no navbar "Teach" dropdown remnants; `grep -rn "max-w-6xl"
  frontend/src/pages/instructor/ManageCoursePage.tsx
  frontend/src/pages/instructor/QuizEditorPage.tsx` returns nothing.

## Reference
- Phase 25 spec (all code items checked, manual item pending):
  `docs/specs/phase-25-course-management-ui-cleanup.md`
- Prior handoffs: `docs/handoffs/2026-07-19-phase-25-ui-cleanup.md`,
  `docs/handoffs/2026-07-19-stem-quest-pivot-plan-revision.md`
- Plan: `PLAN.md` Part 9, Phase 26 row (gitignored, on disk only).
- Go-forward repo is `Cesar6060/LMS` (remote `lms`); `origin`
  (`dev-learning-platform`) is the archived old repo — push/PR to `lms`.
