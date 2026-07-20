# Handoff: Phase 31 — Instructor analytics dashboard

## Current state
Phase 31 **implemented + verified + committed** on `feat/phase-31-instructor-analytics`
(cut from `feat/phase-30-gamification` HEAD per spec branch note). **Not pushed.**
Commits: `4a4ee3c` feat (endpoints + tests + page), docs commit follows this file.

Backend (`courses` app): 4 instructor-only endpoints in `views.py` —
`analytics_overview/quizzes/students/activity` + shared `_analytics_student_rows`
bulk helper (gradebook best-attempt + weighted-grade calcs, roster at-risk rule);
routes in `urls.py` beside gradebook. `tests.py`: `TestInstructorAnalytics`,
28 tests (4x permission boundary parametrized, metric correctness, zero-data).
Frontend: `services/analytics.ts` (typed, 4 methods), `pages/instructor/AnalyticsPage.tsx`
(stat cards, quiz + lesson-check tables, sortable at-risk-first students table,
recharts 3-series 30-day chart), `CourseToolsNav.tsx` Analytics tab, `App.tsx`
route, `recharts` added to package.json (installed locally AND in the container).

Verified: **pytest 276 passed** (248+28); **tsc 0 errors**; **lint 0 errors/25 warn**
(= baseline); **code-reviewer: no correctness bugs**; endpoints live (401 unauth).

## In progress / not done
- **Manual click-through** — the only unchecked spec section (§Verification);
  agent can't drive a browser. Stack is up and backend restarted, ready to click.
- Branch not pushed; no PR. Phase 30 also still unpushed beneath this.

## Next steps
1. Manual click-through (spec §Verification): seeded course → Analytics tab on
   ManageCourse/Gradebook/Roster; worst quiz first; stuck lesson check flagged;
   at-risk rows red (both triggers); streaks real; 3-series chart renders; empty
   states on zero-quiz/zero-student course; student hits AccessDenied + API 403.
2. Check off the manual section in `docs/specs/phase-31-instructor-analytics-dashboard.md`.
3. Rebase chain onto merged `lms/main` when Phases 29/30 land, push, PR
   (`gh --repo Cesar6060/LMS`).

## Decisions made
- **Shared `_analytics_student_rows` helper** for overview+students so both stay
  consistent with gradebook math and stay one-query-per-source (no N+1).
- **Attempts filtered to actively-enrolled students** in quiz/activity metrics so
  removed students can't push completion_rate over 100%.
- **Nulls, not zeros**, for empty averages/rates (`avg_score`, `pass_rate`, etc.);
  frontend renders `—`. Unattempted quizzes sort last (avg `null` → +inf).
- **Chart colors**: dataviz-skill categorical slots 1–3, validator PASS both modes;
  light-mode magenta contrast WARN mitigated by legend + tooltip (relief rule).
  Colors swap via CSS vars (Tailwind arbitrary props) since darkMode is `class`.
- In-progress lesson-check attempts (null `completed_at`) count as "attempted" in
  metrics but not in the activity series — deliberate, reviewer-flagged as OK.

## Gotchas discovered
- Local shell has no `python`/`pytest` — run tests via
  `docker compose exec -T backend pytest` (and `head` is still shadowed).
- Frontend node_modules is a container volume: `npm install` locally does NOT
  reach the dev server — also `docker compose exec -T frontend npm install <pkg>`.
- `.order_by()` must be chained on grouped querysets (`values().annotate()`) or
  model default ordering leaks into GROUP BY and breaks the counts.
- `QuizAttempt.completed_at` is `auto_now_add` — backdate in tests via
  `queryset.update()`, not `create()`.

## Files to read first
- `docs/specs/phase-31-instructor-analytics-dashboard.md` (only manual section open)
- `backend/courses/views.py` — "Instructor Analytics (Phase 31)" block
- `backend/courses/tests.py` — `TestInstructorAnalytics` (behavior spec)
- `frontend/src/pages/instructor/AnalyticsPage.tsx`
- `frontend/src/services/analytics.ts`
