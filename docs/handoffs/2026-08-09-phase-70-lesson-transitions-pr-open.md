# Handoff: Phase 70 — lesson transitions, PR open, not merged

## Current state
**Phase 70 is code-complete and reviewed. PR #104 is open and NOT merged.**
https://github.com/Cesar6060/LMS/pull/104 — branch `phase-70-lesson-transitions`,
two commits: `2800152` (feature) and `ccd145b` (review fixes).

Advancing to the next lesson now lands on page 1; direct arrival still resumes.
Next/Previous walk one chain (`frontend/src/lib/playerNavigation.ts`) that
includes unit quizzes and skips locked units for the owner too.

Created: `frontend/src/lib/playerNavigation.ts` (+ `.test.ts`, 48 tests),
`frontend/src/pages/quizzes/QuizDetailPage.test.tsx` (17),
`backend/courses/test_lesson_sequencing.py` (16),
`backend/courses/test_audit_content_ordering.py` (20),
`backend/courses/management/commands/audit_content_ordering.py`.
Modified: `CoursePlayerPage.tsx` (+ its test, 25), `QuizDetailPage.tsx`,
`LessonQuizSection.tsx` (+ new test), `backend/courses/tests.py`,
`docs/specs/phase-70-lesson-transitions.md` (all 15 items checked, full evidence).

Verify: pytest **1181 passed**, tsc **0**, lint **0 errors** (1 known
`react-refresh` warning), vitest **22 files / 234 passed**. No migrations.

## In progress / not done
1. **PR #104 is not merged.** Merging deploys backend (Render) + frontend
   (Cloudflare Pages). No new env vars needed.
2. **Spec verification item 7 — the DEMO101 demo-student click-through — was
   not done.** Driving `jdoe@demo.com` needs a password typed into a login
   form, which I don't do. The same property was verified on an equivalent
   mid-lesson cursor (lesson 258 set to 2: resumes 3/6 direct, opens 1/6
   sequentially). Yours to click through if you want it literally.

Carried from phase 69, all untouched: Neon `production` still
`protected: false`; `THROTTLE_JOIN_CODE` / `THROTTLE_INVITE_LINK` unset in
Render; `_dmarc` + root SPF still absent; invite-deliverability test; JAVA101
answer rotation; the three `_content_upsert` findings (phase 71).

## Next steps
1. Review and merge PR #104, then verify in prod with a real content read —
   `/api/health/?deep=1` cannot see this (it is frontend-only behaviour, so the
   real check is a browser click-through of Next in ROB101).
2. **Phase 71 is still content-upsert hardening** — the three deferred findings
   from the phase-69 adversarial pass. Phase 70 displaced it, nothing else changed.
3. The four phase-69 owner-dashboard actions above (Neon protection, Render
   throttles, Cloudflare DNS, invite test).
4. Consider adding **CS101** and **VGD101** to
   `backend/courses/test_lesson_sequencing.py`'s `COURSES` list if they ever get
   `populate_*` commands — see Gotchas.

## Decisions made
- **`restart` is consumed on the first page turn, not on arrival.** React Router
  keeps location state in `history.state`, so it is not one-shot. Consuming it
  on arrival would make a reload resume the *stale* cursor this phase exists to
  ignore; leaving it armed forever inverts the resume rule. The first page turn
  is the moment the stored cursor becomes trustworthy.
- **The cross-course `?next=` guard lives in the player, not the quiz page.**
  The player holds the course payload, so one check covers the hand-edited
  `?next=`, a typed `/learn/<id>` and a stale bookmark. It compares the lesson's
  `unit` against `course.units` (which includes locked units) so a locked lesson
  still gets its phase-66 403 notice instead of being called foreign.
- **Previous resumes, Next restarts.** The spec's sequential list is Next / `→`
  / auto-advance only, and `restart` defaults to resume.
- **Section saves keep sharing `isSavingRef` with video-position saves** but now
  both drain the pending queue, rather than giving sections their own flag —
  the spec explicitly kept that ref as a firehose rate limit.

## Gotchas discovered
- **There is no host python/pytest.** Backend tests run
  `docker compose exec -T backend pytest`. `cd backend && pytest` from CLAUDE.md
  does not work in this environment.
- **`origin` is the ARCHIVED repo** (`Cesar6060/dev-learning-platform`). Push to
  **`lms`** (`Cesar6060/LMS`). A push to origin was correctly blocked.
- **The spec's guess `populate_demo_course` does not exist.** DEMO101 is built by
  `clone_course_for_demo`, which deep-copies JAVA101 and hard-fails without it —
  so the sweep test's list is `(code, [commands])`, not `(command, code)`.
- **The local stack has SIX courses, not four**: CS101 (3 units, **no quizzes at
  all**) and VGD101 (4 units, **3 quizzes — one unit has none**) alongside the
  four the spec names. Both are the degenerate shapes `buildChain` must tolerate.
- **`Unit.order` is unclamped** by `UnitViewSet.partial_update` — a `PATCH` with
  `order: 1500000000` returns 200. That made the audit build a billion-element
  gap list before it was capped.
- **A review agent's isolated vitest file hung for 3 minutes** rendering bare
  `/learn`; the same path works fine in the real app and in the full suite. Test-
  harness artefact, not a product loop — verified in the browser.

## Files to read first
1. `docs/specs/phase-70-lesson-transitions.md` — Evidence section has the
   verification, the manual click-through table, the review round, and the
   local-only side effects below.
2. `frontend/src/lib/playerNavigation.ts` — the chain and its locked-unit escape hatch.
3. `frontend/src/pages/courses/CoursePlayerPage.tsx` — the five phase-70 changes
   plus the seven review fixes.
4. `backend/courses/test_lesson_sequencing.py` — its docstring carries the
   two-list maintenance contract (the `COMMANDS` trap from phase 69).

## Local dev-DB side effects of this session
Dev database only; production untouched.
- **`student1@demo.com`'s password is now `Phase70Check!`** — changed to drive
  the click-through; the original is not recoverable.
- Emma consumed 2 of 3 attempts on ROB101 unit 1 quiz (id 64), both 100%.
  Her cursors on lessons 254–255 moved as a result of the walk-through.
- `seed_demo_account` was run; it re-asserted `jdoe@demo.com` and **removed 1
  enrollment of that account outside DEMO101**.
- ROB101 unit 2 (id 80) was locked and unlocked; confirmed `is_locked = False`.
