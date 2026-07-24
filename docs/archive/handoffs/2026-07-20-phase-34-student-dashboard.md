# Handoff: Phase 34 — Student dashboard backdrop hero & declutter

## Current state
Phase 34 **implemented + verified + committed** on branch
`feat/phase-34-student-dashboard` (branched from the phase-33 tip `f01e8cd`,
which rides along in this PR — it was a docs-only commit pushed after PR #18
merged). Commit `521e204` feat, plus this docs commit. Frontend-only:
**zero backend diffs**; pytest stayed at the 341-pass baseline.

Frontend:
- `BackdropScene.tsx` — container-scale rendering of the Phase 33 backdrop
  slot. Each key gets a scene (grid lines / night sky / sunset / galaxy) with
  a **scene-matched scrim** (sunset sinks to deep rose, stars/galaxy to deep
  navy — never the theme background, which went muddy). `plain`/`none`/
  unknown → the old default hero gradient + bg-grid; the hero never renders
  unstyled. Star/ring accents are positioned in hero **dead zones** only
  (top-center strip, side edges) so they don't collide with the HUD.
- `backdrop.ts` — `SceneTheme` per backdrop key: `numeral` (gradient display
  text), `accent`, `label`, `track`, `bubble`, `button` classes +
  `getSceneTheme()`. This is how the hero's containers/buttons react to the
  equipped backdrop: house green/cyan on plain/grid, gold on stars/sunset,
  violet on galaxy. Tweak a scene's look here, not in the hero.
- `DashboardHero.tsx` — the single student hero (layout follows the user's
  Claude Design project "Student Dashboard Design", option **1a**): corner
  Lv/XP and streak as big Orbitron gradient numerals (NO container boxes —
  user explicitly removed them twice), gold Orbitron "Trophy Case" title,
  trophy shelf of ALL badges (`all_badges`) with earned = bright on gold
  pedestals and unearned = **black silhouettes** (`filter: brightness(0)`)
  on frosted slots, mascot (`hideBackdrop`) + Orbitron gradient name, white
  scene-tinted speech-bubble greeting, Customize pinned bottom-right,
  enroll CTA only when no enrollments.
- `DashboardPage.tsx` — student order: hero → Continue Learning card
  (standalone, old gradient style — user rejected it inside the hero) →
  single merged course list (enrollment cards + `course_progress_overview`
  bars). Stat tile grid and separate Course Progress section deleted;
  `AvatarCard.tsx` deleted. Instructor dashboard untouched.
- `Mascot.tsx` — new `hideBackdrop` prop; `starPath` moved to `starPath.ts`
  (react-refresh lint rule). `StreakFlame`/`StreakFreezeChip` unchanged
  (hero renders the streak itself).

Verified: **pytest 341 passed** (no backend diffs); **tsc 0 errors**;
**lint 0 errors / 22 warnings** (= Phase 33 baseline).

## In progress / not done
- Manual click-through (8 steps in the spec) not yet user-confirmed —
  convention: silence means it passed. Step 8 (≈375 px viewport) matters
  most: scene SVG accents scale with the container, so positions shift
  proportionally at extreme widths.
- PR review/merge (see next steps).

## Next steps
1. Review + merge the Phase 34 PR (`feat/phase-34-student-dashboard` →
   `lms/main`).
2. After merge, delete local `feat/phase-33-avatar-customization` and
   `feat/phase-34-student-dashboard` branches.
3. Consider restoring Emma's XP (see gotchas) if realistic demo data matters.

## Decisions made
- **Design source**: hero layout matches Claude Design project
  `01e3049f-d5ea-420c-af56-beca5488c46a`, option 1a. The design's live
  backdrop-chip switcher above the hero was **intentionally not built** —
  backdrops stay customize-only and level-gated (user directive).
- **Iterative user-driven styling** (each reversed a previous approach —
  don't reintroduce): boxed glass panels for XP/streak were removed twice
  (user: "containers not showing", "remove the containers … make them
  blend"); Continue Learning moved OUT of the hero; bubble is white
  (scene-tinted gradient + accent glow, dark text); Lv/streak/name/Trophy
  Case all use Orbitron + per-scene gradient (`SceneTheme.numeral`).
- Trophy case uses `all_badges` (not `badges`) so locked badges render as
  silhouettes; earned tiles are always gold/amber regardless of scene.
- Spec checklist was rewritten in place as the design evolved (trophy case
  superseded the badges strip; Continue Learning is a card below the hero).

## Gotchas discovered
- **Emma's XP was manually set to 2800 (Lv 8)** in the dev DB
  (`student1@demo.com`, was 330/Lv 3) to unlock all cosmetics for testing.
  Students 2–5 left at Lv 1 for locked/silhouette states. Revert via shell:
  `GameProfile` for that user → `total_xp = 330`.
- Theme-token surfaces (`bg-background/*`, `bg-muted`) look muddy over
  vivid scenes — scene scrims and surfaces must use scene-palette colors
  (see `backdrop.ts` / scrim divs in `BackdropScene`).
- Gradient text (`bg-clip-text text-transparent`) + inherited `text-shadow`
  double-renders: set `textShadow: 'none'` and use `drop-shadow-*` instead.
- Tailwind classes in `backdrop.ts` are generated fine (content glob covers
  `src/**/*.ts`), but they must stay full literal strings.
- The user's custom user model has **no `username`** — query `user__email`.
- `head` is shadowed locally (use `/usr/bin/head`); frontend checks run via
  `docker compose exec -T frontend npx tsc --noEmit` / `npm run lint`.
- PR #18 merged via merge commit, but docs commit `f01e8cd` landed after —
  it's included in this PR rather than left stranded.

## Files to read first
- `docs/specs/phase-34-student-dashboard.md` (checklist reflects revisions)
- `frontend/src/components/gamification/backdrop.ts` (scene palettes)
- `frontend/src/components/gamification/DashboardHero.tsx`
- `frontend/src/components/gamification/BackdropScene.tsx`
- `frontend/src/pages/DashboardPage.tsx`
