# Phase 34: Student Dashboard — Backdrop Hero & Declutter

## Goal

Turn the student dashboard into one calm, visually pleasing page anchored by a
single hero container whose background IS the student's equipped avatar
backdrop (the Phase 33 `backdrop` slot, rendered at container scale instead of
only inside the 120×120 mascot SVG). The hero holds the mascot, the
rename-aware greeting, the Customize entry point, and the Continue Learning
CTA + progress; XP/level sits in the hero's top-left corner and streak in the
top-right. Everything below the hero is consolidated: the 5-tile stat grid is
removed, the two overlapping course lists merge into one, and a small
earned-badges strip is added. Frontend-only phase — no backend changes.

## Out of scope

- Any backend change (no new catalog items, models, migrations, or endpoints).
  The existing 6 backdrop items (`plain`, `none`, `grid`, `stars`, `sunset`,
  `galaxy`) are the full set for this phase.
- Instructor dashboard — unchanged (announcement hero, WeekCalendar, course
  management cards all stay as-is).
- Changing how the backdrop renders inside small `Mascot` SVGs elsewhere
  (quiz flows, customizer tiles) — the SVG panel behavior stays.
- Announcements/notifications on the student dashboard.
- Badge earning logic or a full badge gallery (full grid stays in Settings).
- Mobile-app-style layouts beyond responsive behavior of the new hero.

## Backend tasks

- [x] None. Guard: full pytest suite still passes at the Phase 33 baseline
      (341 passed) with zero backend diffs.

## Frontend tasks

### Backdrop scene rendering
- [x] New `frontend/src/components/gamification/BackdropScene.tsx` (or
      equivalent helper): maps each of the 6 backdrop keys to a
      **container-scale** background treatment that visually matches the
      existing SVG art in `Mascot.tsx` (grid → faint primary grid lines over
      muted; stars → `#0f172a` night sky with sparkle stars; sunset → warm
      vertical gradient + sun glow; galaxy → diagonal purple gradient +
      ring/stars accents). CSS gradients + absolutely-positioned SVG accents
      are fine; reuse the `useId()` pattern if gradients need ids.
- [x] Fallbacks: `plain` → the current hero treatment (green/cyan gradient +
      `bg-grid` overlay, i.e. today's default look); `none` → same fallback.
      Unknown/missing key (avatar context null, non-gamified) → same fallback.
      The hero must never render empty/unstyled.
- [x] Readability scrim: whatever backdrop is equipped, greeting text, chips,
      and buttons must stay readable (overlay/scrim or text shadow where the
      scene is busy — stars/sunset/galaxy). Follow the user's readability
      preferences: larger type, real buttons, important info prominent.

### Dashboard hero
- [x] New `DashboardHero` component (students only) replacing BOTH the
      current `AvatarCard` usage and the "Continue Learning" hero card in
      `DashboardPage.tsx`. Contents:
      - Background: `BackdropScene` for the equipped backdrop (from
        `useAvatarContext`).
      - Top-left corner: level chip + slim XP progress bar toward next level
        (`level`, `level_progress_pct`, `xp_into_level` / `level_span` from
        the gamification profile), with `xp_into_level / level_span XP`
        subtext.
      - Top-right corner: streak — reuse `StreakFlame` +
        `StreakFreezeChip` in compact form.
      - Center (revised per Claude Design "Student Dashboard" option 1a):
        large `Mascot` (equipped cosmetics; `hideBackdrop` prop suppresses
        the SVG's own backdrop panel so scenes don't double-render) with the
        mascot name in small text beneath it, and the rename-aware greeting
        in a speech bubble to the mascot's right ("Welcome back,
        {firstName}! …"). Customize button pinned to the hero's bottom-right
        corner. Backdrops remain customize-only and level-gated — the
        design's live backdrop chip row was intentionally NOT implemented.
      - Trophy case (revised 2026-07-20): a shelf of ALL badges
        (`gameProfile.all_badges`) standing behind the mascot — earned badges
        bright on gold pedestals, unearned ones as black silhouettes
        (`filter: brightness(0)`), with a "View all" link to Settings.
        Hidden when the badge catalog is empty. No boxed containers inside
        the hero — content sits directly on the scene (text shadows + scrim
        for readability).
      - Continue Learning moved OUT of the hero (revised 2026-07-20): it is a
        standalone card below the hero — course title, current unit/lesson,
        `progress-gaming` bar + %, and a prominent "Continue Learning" button
        linking to `/courses/:code/learn` (from
        `enhanced_dashboard.continue_learning`); falls back to "Pick up where
        you left off" when `continue_learning` is null.
      - Customize button (Paintbrush) opening the existing
        `AvatarCustomizerModal`; equipping a new backdrop updates the hero
        live via `AvatarContext`.
- [x] Empty/edge states: no enrollments → hero still renders (backdrop +
      avatar + greeting) with a "Join a Course" CTA; `continue_learning`
      null but enrolled → the standalone card shows "Pick up where you left
      off". Non-gamified users (instructors) never see this hero.
- [x] Live backdrop preview: changing the backdrop in the customizer modal
      should reflect in the hero immediately on save (context refresh —
      verify no full-page reload needed).

### Declutter below the hero
- [x] Remove the 5-tile Quick Stats grid entirely (Level/Streak now live in
      hero corners; Courses/Completed/Progress tiles deleted).
- [x] Merge the two course sections into ONE list: enrolled-course cards that
      each carry the data from `course_progress_overview` (overall %, lessons
      completed/total bar, quizzes passed/total bar when quizzes exist).
      Delete the standalone "Course Progress Overview" section. Keep the
      existing empty state + `EnrollmentModal` flow.
- [x] ~~Badges strip under the hero~~ Superseded (revised 2026-07-20): badges
      are the in-hero trophy case (see hero contents above); no separate
      strip below the hero.
- [x] Resulting student page order: Hero (with trophy case) → Continue
      Learning card → single course list. Nothing else.
- [x] Clean up now-unused code: if `AvatarCard.tsx` has no remaining usages,
      delete it (check first); remove dead imports/state from
      `DashboardPage.tsx`.

### Types / services
- [x] No new API calls expected (`getEnhancedDashboard`, `getMyEnrollments`,
      `gamificationService.getProfile` already cover the data). Add/adjust
      TS types only if component extraction needs them.

## Verification

- [x] `cd frontend && npx tsc --noEmit` — 0 errors.
- [x] `cd frontend && npm run lint` — 0 errors, warnings ≤ 22 (Phase 33
      baseline).
- [x] Backend pytest via `docker compose exec -T backend pytest` — 341
      passed, no diffs in `backend/`.
- [x] `/verify-stack` output shown as evidence.
- [ ] Manual click-through (student account):
  1. Log in as a student with gamification data → dashboard shows ONE hero:
     equipped backdrop as the container background, trophy case behind the
     mascot, XP chip + bar top-left, streak flame top-right, greeting
     readable, no boxed containers over the scene.
  2. Open Customize → equip `galaxy` → save → hero background changes
     immediately; equip `none` → hero falls back to the default gradient
     treatment.
  3. Continue Learning card below the hero navigates to the correct
     `/courses/:code/learn` and the progress % matches the course.
  4. Stat tile grid is gone; exactly one course list renders, each card
     showing lessons/quizzes progress bars.
  5. Trophy case: earned badges bright on gold pedestals, unearned badges
     black silhouettes, "View all" links to Settings achievements.
  6. Student with no enrollments → hero renders with enroll CTA, no crash.
  7. Log in as instructor → dashboard identical to Phase 33 (announcement
     hero, WeekCalendar, no avatar hero).
  8. Narrow viewport (~375px): corner chips don't overlap the mascot;
     text stays readable over `stars` and `sunset` backdrops.
