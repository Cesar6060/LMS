# Handoff: Phase 35 — Course map (Duolingo-style skill path)

## Current state
Phase 35 **implemented + verified + committed** on branch
`feat/phase-35-course-map` (branched from `bdb028b` after Phase 34's PR #19
merged; the branch is even with `lms/main` plus this work). Commit `45e95b8`
feat, this docs commit, then two post-review user-directed follow-ups:
`8556198` (dashboard Continue Learning → map) and `8ced813` (course detail
Continue Learning CTA → map). PR #20 open against `lms/main`.

Verified: **pytest 346 passed** (341 baseline + 5 new map tests);
**tsc 0 errors**; **lint 0 errors / 22 warnings** (= Phase 34 baseline).
Zero diffs under `backend/*/models.py` / `backend/*/migrations/` (spec guard).

Backend:
- `GET /api/courses/courses/<code>/map/` — `course_map` in
  `courses/views.py` (bottom of file), route in `courses/urls.py`,
  read-only `CourseMap*Serializer`s at the bottom of
  `courses/serializers.py`. Auth = `IsAuthenticated` +
  `require_course_access` (enrolled or instructor; 403/401 otherwise).
- Node sequence per unit (by order): lessons (by order) then quizzes (by
  order) as boss nodes. States `completed`/`current`/`unlocked`/`locked`
  computed per the spec, including the **required_quiz deadlock exception**
  (a lesson's `required_quiz` unlocks with the lesson, never behind it).
- Query-efficient: course prefetch (`units__lessons`, `units__quizzes`) +
  one `LessonProgress` query + one aggregated `QuizAttempt` query
  (`Max(score)` + passed count, `status='completed'` rows only per the
  Phase 32 rule). No per-lesson queries.
- Tests: `TestCourseMap` in `courses/tests.py` (ordering, progression,
  boss scores, deadlock exception, 401/403/200 boundary).

Frontend:
- `pages/courses/CourseMapPage.tsx` — route `/courses/:code/map`
  (ProtectedRoute). Fixed full-viewport `BackdropScene` (same
  plain/none/unknown fallback as the hero), sticky scene-tinted HUD:
  back button, course title, Orbitron `completed/total` in
  `SceneTheme.numeral`, compact 🔥 streak (hero style, not `StreakFlame`).
- `components/gamification/CourseMapPath.tsx` — serpentine path +
  internal `MapNode`. Per-unit SVG connector (viewBox `0 0 100 H`,
  `preserveAspectRatio="none"`, `vectorEffect="non-scaling-stroke"`);
  x positions from a global node index so the winding continues across
  unit bands. Segments behind completed nodes lit in `scene.accent` via
  `stroke="currentColor"` + text-color class. Unit headers = Orbitron
  `scene.numeral` divider bands. Completed = gold disc + check; boss =
  larger gold-accented crown disc (+ "Best N%"); current = scaled disc,
  ping ring, `Mascot pose="cheer" hideBackdrop` beside it (side flips
  with the serpentine); locked = dimmed disc + lock, `cursor-not-allowed`,
  tooltip, **not a link** (visual only — no route is blocked).
- Entry points: Dashboard student course cards got a real "Map" button
  (footer is now two flex buttons; card's Link still opens the course);
  CoursePlayerPage header got a "Map" button next to Back to Course.
  **User directive (supersedes the spec's original "unchanged" item): both
  Continue Learning buttons — the dashboard card AND the course detail hero
  CTA — now open `/courses/:code/map`.** The map is the student's main way
  into a course; the current node on the map is one tap from the lesson.
  Still pointing at `/learn`: the course detail page's small unit-milestone
  timeline circles (offered to reroute; user hasn't asked) and the
  instructor "Student View" link in `CourseToolsNav`.
- `Layout.tsx`: the learning-mode regex is now
  `/\/courses\/[^/]+\/(learn|map)/` so the map hides the global header +
  AnimatedBackground and owns the full page.
- Types in `types/index.ts` (`CourseMap`, `CourseMapUnit`,
  `CourseMapNode` discriminated on `node_type`, `NodeState`);
  `courseService.getCourseMap` in `services/courses.ts`.

## In progress / not done
- Manual click-through (9 steps in the spec) not yet user-confirmed —
  convention: silence means it passed. Watch step 9 (~375px) and the
  scene look: `BackdropScene` was drawn for a 400×200 hero, so on a
  full viewport the star/ring accents crop to the middle slice at
  narrow widths (gradients + scrims are fine).
- PR review/merge.

## Next steps
1. Review + merge the Phase 35 PR (`feat/phase-35-course-map` → `lms/main`).
2. After merge, delete local `feat/phase-34-student-dashboard` and
   `feat/phase-35-course-map` branches.
3. Emma's XP is still 2800/Lv 8 in the dev DB (Phase 34 gotcha) — handy
   for testing all backdrops on the map; revert to 330 if demo realism
   matters.

## Decisions made
- Endpoint lives at `/api/courses/courses/<code>/map/` — the courses app
  include doubles the prefix for every course route; the spec's
  `/api/courses/<code>/map/` shorthand was normalized to the convention
  (noted in the spec).
- `current_node_id` is a composite `"<node_type>-<id>"` string (lesson
  and quiz ids can collide); the frontend just uses per-node `state`.
- Quiz nodes navigate to `/courses/:code/quizzes/:id` **without**
  `?from=learn` (that param makes the quiz page round-trip back to the
  player; from the map a plain visit is correct).
- Boss/completed nodes are gold regardless of scene (same rule as the
  trophy case); everything else tints from `SceneTheme`.
- `best_score` = highest % across completed attempts (passed or failed),
  matching the spec's "failed attempt only → best_score still reported".

## Gotchas discovered
- DRF `Serializer` output for dicts: heterogeneous nodes are handled by
  a `SerializerMethodField` on the unit serializer dispatching to
  lesson/quiz node serializers — `required=False` field-skipping on one
  shared serializer behaves surprisingly (`allow_null` fields emit
  `null` for missing keys), so don't refactor back to that.
- The map page must stay in `Layout`'s "learning mode" match, or the
  global header + AnimatedBackground stack over the scene.
- Backend restart needed after adding the endpoint
  (`docker compose restart backend`) — tests pass without it but the
  live API 404s.
- zsh here: `head` is shadowed (use `/usr/bin/head`), `echo ===` breaks
  (`=cmd` expansion); frontend checks run via
  `docker compose exec -T frontend ...`.

## Files to read first
- `docs/specs/phase-35-course-map.md` (checklist; only manual
  click-through unchecked)
- `backend/courses/views.py` — `course_map` (bottom)
- `frontend/src/components/gamification/CourseMapPath.tsx`
- `frontend/src/pages/courses/CourseMapPage.tsx`
