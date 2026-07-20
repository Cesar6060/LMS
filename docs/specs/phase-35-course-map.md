# Phase 35: Course Map — Duolingo-Style Skill Path

## Goal

Give students a Duolingo-style course map: a new `/courses/:code/map` page
rendering each enrolled course as a winding vertical path of nodes — lesson
nodes grouped under Orbitron unit headers, with each unit's quizzes as
distinct "boss" nodes at the end of the unit's stretch — drawn over the
student's equipped `BackdropScene` and tinted by `SceneTheme`, with the
Circuit mascot standing at the current node. Gating is **soft**: nodes past
the first incomplete one render locked (dimmed, lock icon, not clickable),
but this is purely visual — the course player's free navigation is untouched
and the backend enforces nothing new. Lock/complete state is computed
server-side by a new single-call map endpoint so the page needs no N+1
progress fetching.

## Out of scope

- Hard gating of any kind: no backend enforcement, no changes to which
  lessons/quizzes a student can open from the player sidebar, course detail
  page, or direct URL.
- Changes to course player behavior (auto-advance, Mark Complete flow,
  sidebar) beyond adding one "Map" header button.
- Replacing `CourseDetailPage` — it stays as-is; the map is a sibling page.
- Hearts/lives, leaderboards, XP changes, new badges, new cosmetics.
- Instructor authoring/analytics changes. Instructors may open the map (same
  course-access rule as the player) but no instructor-specific view is built.
- New models or migrations — map state is derived at read time from
  `LessonProgress` and `QuizAttempt`.
- Lesson comprehension questions (`LessonQuestion`) as map nodes — they stay
  inside the lesson experience; only unit-level `Quiz` objects get nodes.

## Node sequence & state rules (reference for both sides)

- Flattened sequence per course: for each `Unit` (by `order`): its lessons
  (by `order`), then its quizzes (by `order`) as boss nodes.
- Node completion: lesson → `LessonProgress.completed=True` for this user;
  quiz → any `QuizAttempt` with `passed=True` for this user.
- Node state is one of `completed` / `current` / `unlocked` / `locked`:
  - A node is **unlocked** if it is the first node in the sequence or the
    previous node is completed.
  - **Deadlock exception:** a quiz that is some lesson's `required_quiz` is
    unlocked whenever that lesson is unlocked (the lesson cannot be marked
    complete until that quiz passes, so the quiz must never lock behind the
    lesson's completion).
  - **current** = the first node in the sequence that is unlocked but not
    completed (at most one per course).
  - Everything else incomplete is **locked** — visually only.

## Backend tasks

- [x] No new models/migrations. Guard: zero diffs under `backend/*/models.py`
      and `backend/*/migrations/`.
- [x] New endpoint `GET /api/courses/<code>/map/` in `courses/views.py` +
      `courses/urls.py`:
      (Served at `/api/courses/courses/<code>/map/` — the courses app's URL
      include doubles the prefix for every course route; `current_node_id` is
      a composite `"<node_type>-<id>"` string since lesson/quiz ids collide.)
      - Permissions: `IsAuthenticated` + `require_course_access(user,
        course)` (enrolled student or the course instructor; others 403,
        matching existing convention).
      - Response: `{course_code, course_title, total_nodes, completed_nodes,
        current_node_id, units: [{id, title, order, nodes: [...]}]}` where
        each node is `{node_type: "lesson"|"quiz", id, title, order,
        state: "completed"|"current"|"unlocked"|"locked"}`; quiz nodes also
        carry `passing_score` and `best_score` (highest attempt %, null if
        none).
      - Implements the state rules above. Query-efficient: prefetch
        `units__lessons` + `units__quizzes`, one query for the user's
        `LessonProgress` rows, one for passed/best `QuizAttempt`s — no
        per-lesson queries.
- [x] Serializer(s) in `courses/serializers.py` (plain read-only; no writes).
- [x] pytest cases (in the existing courses test module style):
      - Enrolled student gets the full tree with correct ordering
        (units by order; lessons before that unit's quizzes).
      - State progression: nothing done → node 1 `current`, rest `locked`;
        complete lesson 1 → it's `completed`, node 2 `current`.
      - Quiz boss node: passing attempt → `completed` with `best_score`;
        failed attempt only → not completed, `best_score` still reported.
      - `required_quiz` deadlock exception: quiz unlocks with its gated
        lesson, not after it.
      - Unenrolled student → 403; course instructor → 200; anonymous → 401.
      - Baseline: full suite still passes (341 pre-existing + new).

## Frontend tasks

### Types & service
- [x] `types/index.ts`: `CourseMap`, `CourseMapUnit`, `CourseMapNode`
      (discriminated on `node_type`), `NodeState`.
- [x] `services/courses.ts`: `getCourseMap(code)` → GET `/courses/<code>/map/`.

### Course map page
- [x] `pages/courses/CourseMapPage.tsx`, route `/courses/:code/map` in
      `App.tsx` under `ProtectedRoute` (alongside the `/learn` routes; keyed
      by `:code` like everything else).
- [x] Fetches `getCourseMap(code)` + uses `useAvatarContext()` /
      `gamificationService.getProfile()` for scene + HUD data.
- [x] Full-page equipped `BackdropScene` background with the same
      `plain`/`none`/unknown fallback rule as the dashboard hero (never
      unstyled), scene-matched scrim for readability.
- [x] Compact HUD header: back link to `/courses/:code`, course title, big
      Orbitron `completed_nodes/total_nodes` progress (SceneTheme `numeral`
      gradient), compact streak flame. Follow readability prefs: large type,
      real buttons.

### Path & nodes
- [x] `components/gamification/CourseMapPath.tsx` (+ small `MapNode`
      component if cleaner): single vertical scroll, nodes alternating
      left/right offsets along a winding SVG connector path; connector
      segments between completed nodes use SceneTheme `accent`, upcoming
      segments dimmed.
- [x] Unit headers: Orbitron, SceneTheme `numeral` gradient, `label` styling
      — a horizontal divider band between unit stretches.
- [x] Node states:
      - `completed`: bright/gold treatment (like earned trophy tiles),
        check mark; clickable.
      - `current`: enlarged with pulsing SceneTheme `accent` ring; the
        `Mascot` (equipped cosmetics, `hideBackdrop`) stands beside it.
      - `unlocked` (non-current, e.g. ahead via the deadlock exception):
        normal, clickable.
      - `locked`: dimmed scene-tinted disc + lock icon, `cursor-not-allowed`,
        NOT clickable; tooltip/title "Complete the previous lesson to
        unlock". Reminder: visual only — no route is actually blocked.
- [x] Boss (quiz) nodes: visually distinct (larger, e.g. shield/crown motif,
      gold accent regardless of scene — same rule as trophy case), showing
      `best_score` when present.
- [x] Navigation on tap: lesson node → `/courses/:code/learn/:lessonId`;
      quiz node → the existing quiz-taking route the player uses.
- [x] Responsive: single column path works at ~375px; nodes/tap targets stay
      comfortably large.

### Entry points
- [x] Dashboard (`DashboardPage.tsx`): each enrolled-course card gets a
      "Map" button/link → `/courses/:code/map` (real button per readability
      prefs; card's existing primary action unchanged).
- [x] Course player header (`CoursePlayerPage.tsx`): a "Map" button next to
      the existing back link → `/courses/:code/map`.
- [x] Continue Learning card points at `/courses/:code/map` (user directive
      post-implementation; superseded the original "stays at `/learn`" item —
      the map is now the student's main entry into a course).

## Verification

- [x] Backend pytest via `docker compose exec -T backend pytest` — all new
      map tests pass; total = 341 + new, 0 failures.
- [x] `cd frontend && npx tsc --noEmit` — 0 errors.
- [x] `cd frontend && npm run lint` — 0 errors, warnings ≤ 22 (Phase 34
      baseline).
- [x] `/verify-stack` output shown as evidence.
- [ ] Manual click-through (student account):
  1. Dashboard → course card "Map" button → map renders over the equipped
     backdrop; equip `galaxy` via dashboard Customize, revisit map → scene
     and node tints change; equip `none` → default gradient fallback.
  2. Fresh-progress course: node 1 is `current` (mascot beside it, pulsing
     ring), all later nodes locked with lock icons; clicking a locked node
     does nothing.
  3. Complete lesson 1 in the player → return to map → node 1 completed
     (gold), node 2 now current, connector segment lit.
  4. Boss node at the end of a unit is visually distinct; tapping it opens
     the quiz; after passing, it shows completed + best score.
  5. A lesson with a `required_quiz` → its quiz node is unlocked (not
     locked) while the lesson is still incomplete.
  6. Player header "Map" button round-trips player ↔ map.
  7. Player sidebar still freely navigates to ANY lesson, including ones the
     map shows as locked (soft gating confirmed).
  8. Instructor opens own course's map → 200, page renders, no crash;
     unenrolled student hitting the URL directly → access denied.
  9. Narrow viewport (~375px): path stays single-column, nodes tappable,
     unit headers readable over `stars`/`sunset`.
