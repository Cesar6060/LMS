# Phase 70 — Lesson-to-lesson transitions

> Phase 70 was previously pencilled in as *content-upsert hardening* (see
> `docs/handoffs/2026-08-06-phase-69-closed-rob201-live.md` → Next steps 5). The
> user redirected: that work moves to **phase 71**, unchanged. The three deferred
> `_content_upsert` findings are still open and still owed.

## Goal

Advancing to the next lesson must land the student on the **first page of that
lesson**, every time. Today the player restores each lesson's saved
`current_section` on *every* arrival — including sequential Next / auto-advance —
so any lesson the student already finished re-opens on its comprehension-quiz
page instead of at the start. This phase separates *sequential advance* (always
page 1) from *resume* (sidebar click, pasted URL, dashboard/course-map entry —
keeps the saved page), makes Next/Previous walk one explicit, testable node chain
that includes unit quizzes and skips instructor-locked units, and backs the whole
thing with an automated sweep over every seeded course so this class of bug is
caught for DEMO101, JAVA101, ROB101 and ROB201 rather than the one lesson someone
happened to notice.

## Root cause (confirmed, do not re-investigate)

`frontend/src/pages/courses/CoursePlayerPage.tsx:201-234`. `loadLesson` correctly
resets the page cursor:

```ts
setCurrentSectionIndex(0); // Reset section index
```

…and then, ~25 lines later, unconditionally overrides it:

```ts
// Resume at saved section
if (progressData?.current_section !== undefined) {
  const savedSection = progressData.current_section;
  if (savedSection <= maxSectionIndex) {
    setCurrentSectionIndex(savedSection);
  }
}
```

`maxSectionIndex` **includes** the quiz page, so the quiz index is explicitly
allowed. `current_section` is written on every page turn
(`CoursePlayerPage.tsx:296-302`) and the backend never clears it on completion
(`LessonProgress.current_section`, `backend/courses/models.py:441`;
`LessonProgressView`, `backend/courses/views.py:559-601`). Result: finish a
lesson on its quiz page → that lesson's saved cursor is the quiz page forever →
arriving from the previous lesson opens the quiz.

Two amplifiers, both real:

- The demo seed writes a mid-lesson baseline —
  `seed_demo_account.py:204-210` sets `current_section = section_count // 2` —
  so the demo student hits this on lessons they never opened.
- The instructor's progress is reset only on **player unmount**
  (`CoursePlayerPage.tsx:126-134`, `useEffect` with `[]` deps, keyed off
  `currentLessonRef`). Walking lesson→lesson inside the player never resets, so
  an instructor clicking through the course accumulates quiz-page cursors and
  then sees the bug on the second pass.

## Out of scope

- Any change to how `current_section` is stored or when it is written. The field,
  its writes, and the backend contract stay exactly as they are — this phase only
  changes when it is **read back**.
- A persisted course-level cursor (`Enrollment.current_lesson`). Course-level
  resume stays derived, in the two places that already derive it
  (`enhanced_dashboard` views.py:758-801, `course_map` views.py:3628).
- A backend next/previous endpoint. There is none today and the chain stays
  frontend-computed from the course-detail payload; this phase only makes that
  computation explicit and testable.
- Sequential unit gating, release dates, or any new access enforcement. Locked
  units keep behaving exactly as phase 66 left them.
- Editing seeded course content. The ordering audit is **report-only** — if it
  finds something, it goes in the handoff as a phase-71 item.
- Retiring the `?from=learn` back-link contract on `QuizDetailPage`; it is
  extended, not replaced.
- The three deferred `_content_upsert` findings (phase 71).

## Design decisions (locked in with user)

- **Resume rule:** sequential arrival (Next button, `→` key, auto-advance after
  completion) always opens the next lesson at **page 1**. Resume still applies
  when the student lands on a lesson directly — sidebar click, pasted URL,
  dashboard / course-map entry.
- **Unit boundary:** Next from the last page of a unit's last lesson goes to that
  unit's **quiz**, then on to the next unit's first lesson. (Today the quiz is
  skipped entirely and is only reachable from the sidebar.)
- **Locked units:** Previous/Next **skip** locked units, for instructors too.
- **Scope beyond the fix:** automated transition sweep + regression tests +
  read-only ordering audit + the rapid-click page-skip fix — all four.

### How "sequential" is signalled

Use react-router navigation state, not a ref:

```ts
navigate(`/courses/${code}/learn/${id}`, { state: { restart: true } });
```

and in the player, `const restart = (useLocation().state as {restart?: boolean} | null)?.restart === true;`
gates the resume block. A ref would be consumed twice under React StrictMode's
double-invoked effects and silently resume in dev only. History-entry state is
idempotent and survives the double invoke.

## Backend tasks

No models, no migrations, no endpoint changes. Everything here is tests and one
read-only command.

- [x] [P] **Ordering audit command** — `backend/courses/management/commands/audit_content_ordering.py`,
      read-only (no writes, no `--fix`). For every course, or one passed as
      `--course CODE`, report:
      - units whose `order` values are not contiguous from their base (seeded
        content is 0-indexed, API-created content starts at 1 — see
        `CourseUnitsView.perform_create` views.py:326 vs `_content_upsert.py:305`;
        the audit reports gaps, not the base);
      - lessons the same way, within each unit;
      - **quizzes sharing an `order` inside a unit** — `Quiz` has no
        `unique_together` on `(unit, order)` (`backend/quizzes/models.py:26-31`,
        called out in `_content_upsert.py:252-255`), so this is the one place a
        genuine duplicate can exist. `Quiz.Meta.ordering = ['order', 'created_at']`
        means a duplicate resolves by creation time, i.e. non-deterministically
        across a reseed;
      - units holding more than one quiz (the chain assumes at most one per unit
        for the "Next → unit quiz" step; more than one is not an error, they
        chain in `order` — just report it).
      Exit 0 always; this is a report, not a gate.
- [x] [P] **Sweep test** — `backend/courses/test_lesson_sequencing.py`. For each
      seeded course, built by calling its management command in a fixture
      (`populate_demo_course`, `populate_java_course`, `populate_robotics_course`,
      `populate_robotics_2_course` — check the real names in
      `backend/courses/management/commands/`), assert:
      - `test_units_are_contiguously_ordered` / `test_lessons_are_contiguously_ordered_within_each_unit`
      - `test_no_two_quizzes_share_an_order_within_a_unit`
      - `test_chain_contains_every_lesson_exactly_once` — the derived
        units→lessons→quizzes chain (mirroring `course_map`'s node order,
        views.py:3676-3689) visits every non-locked lesson once, in
        `unit.order, lesson.order`.
      Parametrize over the courses so a fifth course is one list entry, **and add
      the new courses to the parametrize list here as well as to the `COMMANDS`
      list in `test_populate_courses.py`** — registering in `COMMANDS` alone buys
      nothing (see the phase-69 handoff gotcha).
- [x] **Regression: completion does not move the cursor** — in
      `backend/courses/tests.py`, assert `LessonProgress.current_section` is
      unchanged by a `completed: true` PATCH. This pins the backend half of the
      contract so a future "helpfully reset it server-side" change is a visible
      decision rather than a silent one.

## Frontend tasks

- [x] **Navigation chain module** — new `frontend/src/lib/playerNavigation.ts`,
      pure and unit-testable (follow the `lib/courseProgress.ts` shape: exported
      interfaces for the minimal input, no React, no service imports).
      - `export type ChainNode = { kind: 'lesson' | 'quiz'; id: number; title: string; unitId: number; unitTitle: string }`
      - `buildChain(units, quizzes): ChainNode[]` — for each unit in payload order
        (the API already sorts by `unit.order`): skip when `unit.is_locked`, then
        its lessons in payload order as `kind: 'lesson'`, then the quizzes whose
        `quiz.unit === unit.id` sorted by `order` as `kind: 'quiz'`. Lesson and
        quiz ids can collide across the two tables — key on `kind` + `id`, never
        `id` alone (this is exactly why `course_map` uses a composite
        `current_node_id`, `courses/serializers.py:1093`).
      - `getNextNode(chain, kind, id)` / `getPreviousNode(chain, kind, id)`.
      - Handles: empty course, unit with no lessons, unit with no quiz, locked
        first unit, locked last unit, current node absent from the chain
        (→ `null`, never index `-1 + 1 = 0`, which is today's silent "jump to
        lesson 1" on a stale id).
- [x] [P] **Chain tests** — `frontend/src/lib/playerNavigation.test.ts` covering
      every case above plus: last lesson of unit 1 → unit 1's quiz; that quiz →
      unit 2's first lesson; unit 2 locked → unit 1's quiz goes to unit 3's first
      lesson; previous is the exact mirror of next across a unit boundary.
- [x] **Player uses the chain** — `CoursePlayerPage.tsx`:
      - Replace `getPreviousLesson` / `getNextLesson` (:455-469) with
        `getPreviousNode` / `getNextNode` over `buildChain(course.units, quizzes)`
        (`quizzes` is already in state, :87). Memoize the chain on
        `[course, quizzes]`.
      - Next/Previous footer buttons (:886-963) and the `←`/`→` key handler
        (:519-556) route on node kind: `lesson` →
        `navigate(.../learn/<id>, { state: { restart: true } })`; `quiz` →
        `handleQuizSelect`.
      - Delete the **duplicated** inline auto-advance in `handleVideoEnded`
        (:442-449) — it re-derives its own flat list, ignores locked units and
        ignores quizzes. Call the same helper `handleMarkComplete` uses.
      - Auto-advance after completion (:368-373) passes `state: { restart: true }`
        too.
- [x] **Gate the resume** — `CoursePlayerPage.tsx:228-234`: skip the
      `setCurrentSectionIndex(savedSection)` block when the arrival was
      sequential. Read `restart` from `useLocation().state` (see *Design
      decisions*). Keep the `savedSection <= maxSectionIndex` clamp for the
      resume path. Leave `lastSavedSectionRef` seeded from the server value
      either way, so a restart-to-page-1 still writes `current_section: 0` on the
      first real page turn rather than being swallowed by the equality guard at
      :296.
- [x] **Sequential vs direct at the call sites** — `handleLessonSelect` (:271-273)
      grows an explicit argument (e.g. `goToLesson(id, { restart })`) rather than
      guessing. Sidebar `onLessonSelect` (`CourseSidebar.tsx`) passes
      `restart: false`; Next/`→`/auto-advance pass `restart: true`. Do not make
      `restart` default to `true` — a new call site should resume, which is the
      pre-phase-70 behaviour.
- [x] **Unit-quiz round trip** — the player currently sends
      `?from=learn` with no lesson, so returning from a unit quiz lands on bare
      `/courses/:code/learn` and re-runs the first-incomplete redirect, dropping
      the student somewhere else entirely (`handleQuizSelect` :275-278 vs
      `QuizDetailPage.tsx:27-36`).
      - Player sends `?from=learn&lesson=<currentLessonId>&next=<nextLessonId>`
        (omit `next` when the quiz is the last node).
      - `QuizDetailPage`: back link → `/courses/:code/learn/<lesson>` (resume, no
        `restart`). After a submitted attempt, a primary **"Continue to next
        lesson"** button → `/courses/:code/learn/<next>` with
        `state: { restart: true }`. Real button, prominent — this is the main
        forward path at a unit boundary.
      - Validate both params as integers before use; a hand-edited
        `?next=<other course's lesson>` must not navigate. Fall back to the back
        link.
- [x] **Skip-locked for the instructor too** — falls out of `buildChain`, but
      assert it explicitly in the player test: the instructor gets full
      `lessons[]` for a locked unit from the API
      (`UnitSerializer.to_representation`, `courses/serializers.py:428-439`), so
      without the `is_locked` check their Next walks into content they locked.
- [x] **Rapid-click page skipping** — `handleSectionChange` (:281-309) early-returns
      `if (isSavingRef.current) return`, so a second `→` press while the previous
      `current_section` PATCH is in flight is **silently dropped**: the page does
      not turn. Move the cursor update ahead of the guard so the UI always
      advances, and let the save coalesce (fire-and-forget the latest index, or
      keep a `pendingSectionRef` flushed when the in-flight request settles).
      Do not remove `isSavingRef` from `handleVideoProgress` (:381-398) — that
      one is a genuine rate limit on a firehose.
- [x] [P] **Stale-response guard** — `loadLesson` (:201-252) has no abort or
      ignore flag. Two quick lesson changes race and the *later-resolving*
      response wins, calling `setCurrentSectionIndex` for the wrong lesson. Add
      the standard `let ignore = false` / cleanup pattern (or compare the
      resolved lesson id against the current `lessonId` before committing state).
- [x] [P] **Child-state reset** — `LessonQuizSection.tsx`: `showQuiz` and
      `sessionResult` (:22-23) are not reset by its `useEffect([lessonId])`
      (:26-29); they survive today only because the parent unmounts the subtree
      behind a spinner. Reset them on `lessonId` change so the component is
      correct on its own terms. Also guard its async `loadData` (:31-46) against
      writing a stale `onStatusChange` into the parent after the parent already
      cleared it.
- [x] **Stop refetching the whole course on every lesson change** —
      `loadCourse` is a `useCallback` with `lessonId` in its deps (:199) and the
      effect at :255-259 depends on it, so **changing lesson refetches the entire
      course** and flips `isLoading`, hitting the full-page spinner early-return
      at :558-564. That is the visible flash between lessons and it unmounts the
      whole player subtree each time. Split the no-`lessonId` first-incomplete
      redirect (:174-187) into its own effect so `loadCourse` depends on `code`
      only. *(Not one of the four scope items you picked — folded in because it
      sits directly in the transition path and masks the child-state bugs above.
      Drop it if you'd rather keep the diff tight.)*
- [x] **Player regression tests** — `frontend/src/pages/courses/CoursePlayerPage.test.tsx`
      (today it covers only Present mode and locked units — **nothing** covers
      lesson-to-lesson advancement):
      - Next from the last page of lesson N opens lesson N+1 at page **1/…**, even
        when lesson N+1's progress returns `current_section` = its quiz index.
        *This is the reported bug — it must fail before the fix and pass after.*
      - Sidebar click on lesson N+1 still **resumes** at the saved page.
      - A direct visit to `/courses/CODE/learn/<N+1>` still resumes.
      - Auto-advance after Mark Complete lands on page 1.
      - `→` from the last page of a unit's last lesson navigates to
        `/courses/CODE/quizzes/<id>?from=learn&lesson=…&next=…`.
      - Next skips a locked unit for a course-owner viewer.
      - Two fast `→` presses turn two pages (rapid-click regression).

## Verification

Everything below must be shown as evidence, not asserted.

1. **`/verify-stack` → PASS.** Baseline to beat: pytest **1142 passed**, tsc
   **0**, lint **0 errors** (the one known `react-refresh` warning in
   `ErrorBoundary.tsx` is expected).
2. **Backend**, from `backend/`:
   - `pytest courses/test_lesson_sequencing.py -v` — every parametrized course
     passes.
   - `pytest courses/tests.py -k "current_section" -v`
   - `pytest courses/test_populate_courses.py -v` — unchanged.
3. **Ordering audit**, real output pasted into the handoff:
   - `docker compose exec backend python manage.py audit_content_ordering`
     against the local stack, for all four courses. Any finding is **recorded as
     a phase-71 item, not fixed here.**
4. **Frontend**, from `frontend/`:
   - `npx vitest run src/lib/playerNavigation.test.ts src/pages/courses/CoursePlayerPage.test.tsx`
   - `npx tsc --noEmit` → 0
   - `npm run lint`
5. **Bug-first proof.** Show the new "Next opens page 1" test **failing against
   the unmodified player** (stash the fix, or paste the run from before the
   change), then passing. A regression test that never saw red proves nothing.
6. **Manual click-through** on the local stack, as a **student** (not the
   instructor — the instructor's unmount reset hides the bug):
   1. Open ROB101, complete unit 1 lesson 1 through its comprehension quiz.
   2. Go back to lesson 1 from the sidebar → it **resumes on the quiz page**
      (resume still works).
   3. From lesson 1, press Next / `→` to the end → lands on lesson 2 at page
      **1/N**, not its quiz. Repeat across the whole of unit 1.
   4. At the last page of unit 1's last lesson, Next → **unit 1's quiz page**.
      Submit it → **"Continue to next lesson"** → unit 2 lesson 1, page 1.
      Use the back link instead → returns to the lesson you left, not to bare
      `/learn`.
   5. As the instructor, lock unit 2, then as the student walk unit 1's last
      lesson → Next skips to unit 3. Unlock it again.
   6. Hold `→` through a lesson — every press turns a page; no silent drops.
7. **Demo account.** The demo student is seeded mid-lesson
   (`current_section = count // 2`). Confirm: entering DEMO101 from the dashboard
   still resumes mid-lesson, but pressing Next out of that lesson lands on page 1
   of the following one.

---

## Evidence (2026-08-09, branch `phase-70-lesson-transitions`)

**1. `/verify-stack` → PASS.**

```
docker compose exec -T backend pytest   →  1180 passed in 281.07s   (baseline 1142, +38)
npx tsc --noEmit                        →  exit 0
npm run lint                            →  1 problem (0 errors, 1 warning)
                                           react-refresh/only-export-components in ErrorBoundary.tsx — the known one
```

Backend tests run through the container: there is no host python/pytest in this
environment (`python: command not found`).

**2. Backend targeted runs.**

```
pytest courses/test_lesson_sequencing.py -v   →  16 passed in 10.73s
     4 tests × [DEMO101, JAVA101, ROB101, ROB201], every one PASSED
pytest courses/tests.py -k "current_section" -v
     TestLessonProgressCurrentSection::test_completion_patch_leaves_current_section_unchanged        PASSED
     TestLessonProgressCurrentSection::test_completion_patch_may_still_set_current_section_explicitly PASSED
     TestLessonProgressCurrentSection::test_repeat_completion_patch_leaves_current_section_unchanged  PASSED
     →  3 passed, 533 deselected in 2.41s
pytest courses/test_populate_courses.py       →  39 passed in 26.05s  (unchanged)
pytest courses/test_audit_content_ordering.py →  19 passed  (the audit command's own tests)
```

**3. Ordering audit — real output, local stack.**

```
$ docker compose exec backend python manage.py audit_content_ordering
Auditing 6 course(s) for content-ordering problems...

CS101 — Principles of Computer Science
  OK   3 unit(s), 3 lesson(s), 0 quiz(zes)

DEMO101 — Java Fundamentals — Demo
  OK   5 unit(s), 20 lesson(s), 5 quiz(zes)

JAVA101 — Introduction to Programming with Java
  OK   5 unit(s), 20 lesson(s), 5 quiz(zes)

ROB101 — Robotics 1
  OK   6 unit(s), 24 lesson(s), 6 quiz(zes)

ROB201 — Robotics 2
  OK   6 unit(s), 24 lesson(s), 6 quiz(zes)

VGD101 — Game Programming with Godot
  OK   4 unit(s), 8 lesson(s), 3 quiz(zes)

Summary: no issues found across 6 course(s) (0 informational note(s)).
exit 0
```

**No findings — nothing to carry to phase 71 from the audit.** Two observations
worth recording anyway, neither an ordering error:

- The local stack holds **six** courses, not the four the spec names: **CS101**
  (3 units, 3 lessons, **no quizzes at all**) and **VGD101** (4 units, 8
  lessons, 3 quizzes — so **one unit has no quiz**). Both are exactly the
  degenerate shapes `buildChain` has to tolerate, and both are covered by the
  chain unit tests. Neither is seeded by a `populate_*` command, so neither is
  in the sweep-test parametrize list.
- `test_no_two_quizzes_share_an_order_within_a_unit` is the only one of the four
  sweep assertions that can realistically ever fail: `Unit` and `Lesson` already
  carry `unique_together` on `(parent, order)`, so their contiguity checks can
  only catch *gaps*, never duplicates. `Quiz` has no such constraint.

**4. Frontend.**

```
npx vitest run src/lib/playerNavigation.test.ts          →  34 passed
npx vitest run src/pages/courses/CoursePlayerPage.test.tsx →  19 passed (12 pre-existing + 7 new)
npx vitest run src/components/lesson/LessonQuizSection.test.tsx →  2 passed
npx vitest run  (full suite)                              →  21 files, 197 passed
npx tsc --noEmit → 0        npm run lint → 0 errors
```

**5. Bug-first proof.** The seven new transition tests were run against the
**unmodified** player (`git checkout HEAD -- CoursePlayerPage.tsx`, with only
the `data-testid="page-indicator"` hook injected so the failures are the real
bug and not a missing selector):

```
RED — phase-70 tests against the unmodified player
  × opens the next lesson at page 1 even when its saved cursor is the quiz page
  × lands on page 1 when Mark Complete auto-advances
  × goes to the unit quiz — with the round-trip params — off the last lesson of a unit
  × skips a locked unit for the course owner, who still receives its lessons
  × turns two pages on two fast presses while the first save is still in flight
  Tests  5 failed | 2 passed | 12 skipped (19)

GREEN — same tests, fix restored
  Tests  7 passed | 12 skipped (19)
```

The two that passed red are the two *resume* tests (sidebar click, direct URL
visit). That is the correct result and the point of the pair: resume was never
broken, and the fix must not break it.

---

## Notes for the implementation session

- No migrations, no model changes, no new endpoints. If a task seems to need one,
  stop — it is out of scope.
- `[P]` items touch different files and can go to parallel subagents. The player
  edits are **not** parallelizable with each other: `CoursePlayerPage.tsx` takes
  five separate changes and they conflict.
- Suggested order: chain module + its tests → player switched onto the chain →
  resume gate → quiz round trip → the hardening items → sweep + audit.
