# Phase 33: Circuit Avatar Customization

Extends ADR-019 gamification with a customizable mascot-avatar. (ADR-021's
visual-redesign pass, previously penciled in as "Phase 33", shifts after
this.) **Branch note:** PR #17 (Phases 29–32) is open — branch from
`feat/phase-32-duolingo-quiz-ux` HEAD, or from `lms/main` once it merges.

## Goal

Give every student their own "Circuit": a customizable avatar built from
the existing mascot SVG, with unlockable cosmetics gated by level (more
lessons/quizzes → more XP → higher level → more gear). Items auto-unlock
permanently on level-up — no currency, no spending, XP only ever goes up
(level stays derived from `total_xp`). Students can rename their Circuit.
The avatar lives in a prominent dashboard card with a customizer modal,
and the customized look renders everywhere the mascot already appears
(quiz feedback banners, completion screens, dashboard). Instructors keep
seeing none of it.

## Decisions (interview 2026-07-20)

1. **Unlocks:** level-gated auto-unlock only. No coin currency, no
   badge-tied exclusives (candidate for a later phase). Unlocked set is a
   pure function of level — no per-user unlock rows, fully retroactive.
2. **Slots (all four):** color schemes, headgear, eyes/face styles,
   accessories. All drawn in code as SVG layers/palette swaps on the
   existing `Mascot.tsx` — no asset pipeline, no image uploads.
3. **UI:** dashboard avatar card (replaces the Phase 32 greeting line) +
   customizer modal with slot tabs, live preview, and rename input.
4. **Reach:** customized look renders everywhere the mascot appears.
   Implementation: an `AvatarContext` loaded for students at login;
   `Mascot` reads it by default so existing call sites (QuizSessionFlow,
   LessonQuizSection, QuizDetailPage, Dashboard) pick up the custom look
   with no prop-threading.
5. **Rename:** `mascot_name`, default "Circuit", trimmed, 1–20 chars,
   visible only to the student themself (no moderation surface needed;
   revisit if leaderboards ever land). Reset-to-default affordance in the
   modal.
6. **Catalog in code** (like the badge catalog but no DB table):
   `gamification/avatar_catalog.py`. Each slot has a level-1 default
   ("classic" color, "none" for the rest) plus ~4–5 unlockables spread
   across levels 2–8 so early levels pay off fast.
7. **Backdrop slot** (added mid-phase, user request 2026-07-20): a fifth
   slot `backdrop` — a container/background drawn behind Circuit inside
   the mascot SVG, editable like any other slot. Default `plain` (a subtle
   panel, so the mascot always sits in a backdrop container); a `none`
   item at Lv1 opts out. Unlockables: grid (Lv2), stars (Lv4), sunset
   (Lv5), galaxy (Lv7).
8. **Implementation note:** catalog keys are unique per slot, not globally
   (`none` exists in several slots), so the helper is `get_item(slot, key)`
   rather than the spec's `get_item(key)`.

## Out of scope

- Coin/currency systems, spending XP, badge-tied or event-exclusive items.
- Uploaded/AI/image-based avatars — the photo avatar in Settings→Profile
  (`UserPreferences.avatar`) is untouched and unrelated; the header keeps
  showing the photo avatar, NOT Circuit.
- Mascot name appearing outside the student's own views; leaderboards.
- New poses/animations, seasonal items, instructor-facing anything.
- Showing the avatar in Settings→Achievements (dashboard card is the home).

## Data model notes

- `GameProfile` gains: `mascot_name` (CharField 20, default `'Circuit'`),
  `avatar_color` (default `'classic'`), `avatar_headgear`,
  `avatar_eyes`, `avatar_accessory` (CharFields 30, default `'none'`),
  and `avatar_backdrop` (CharField 30, default `'plain'`).
  Equipped keys are validated against the code catalog on write; a stale
  key (item removed from catalog later) renders as the slot default.
- No new tables. Unlock state = `profile.level >= item.required_level`.

## Backend tasks

- [x] Migration: five new `GameProfile` fields (defaults as above —
      existing rows need no backfill).
- [x] `gamification/avatar_catalog.py`: `SLOTS = ('color', 'headgear',
      'eyes', 'accessory')`; `CATALOG` list of items
      `{key, slot, name, description, required_level}` including the
      level-1 defaults (`classic`, `none` per slot); helpers
      `items_for_slot()`, `get_item(key)`. ~18–22 items total, spread
      levels 1–8.
- [x] `profile_payload()` (or the profile view) adds an `avatar` block:
      `{mascot_name, equipped: {color, headgear, eyes, accessory},
      catalog: [{key, slot, name, description, required_level, unlocked}]}`
      with `unlocked` derived from the profile's level. Instructor
      response stays exactly `{is_gamified: false}`.
- [x] `PATCH /api/gamification/avatar/` — students only (instructors
      403 with `{'detail': ...}`). Partial body: `mascot_name` and/or any
      slot key. Validation (400 on failure): name trimmed, 1–20 chars;
      item key exists; item belongs to the named slot; item unlocked at
      current level. Returns the refreshed `avatar` block.
- [x] Tests (`gamification/tests.py`): profile payload contains the
      avatar block with correct `unlocked` flags at level boundaries
      (e.g. Lv2 item locked at 99 XP, unlocked at 100); equip unlocked
      item persists; equip locked item → 400 and nothing persists; bad
      key / slot-mismatch key → 400; rename happy path + empty/too-long
      → 400; unauth 401; instructor 403 on PATCH and inert payload on
      GET; defaults present for a fresh profile.

## Frontend tasks

- [x] Types (`types/index.ts`): `AvatarSlot`, `AvatarItem`
      (`key, slot, name, description, required_level, unlocked`),
      `AvatarState` (`mascot_name, equipped, catalog`);
      `GamificationProfile.avatar?: AvatarState`.
- [x] `services/gamification.ts`: `updateAvatar(patch)` → PATCH
      `/gamification/avatar/`.
- [x] **`contexts/AvatarContext.tsx`**: loads the gamification profile's
      avatar block for logged-in students (instructors: null), exposes
      `{avatar, refresh, update}`. Mount in `App.tsx` inside auth.
- [x] **`Mascot.tsx`**: render the four slots from new optional
      `customization` prop, defaulting to `useAvatarContext()` values so
      every existing call site gets the custom look for free. Color
      schemes = palette swap (keep theme-awareness); headgear, eyes,
      accessories = additional SVG layers per item key. Unknown/stale
      key → slot default. All four poses keep working with all items.
- [x] **`components/gamification/AvatarCard.tsx`** (dashboard): replaces
      the greeting line — large customized Mascot, `mascot_name` +
      greeting ("{name} says: Welcome back, {first_name}!"), level chip,
      "Customize" button. Student-only, `is_gamified` gated.
- [x] **`components/gamification/AvatarCustomizerModal.tsx`**: slot tabs,
      item grid (locked items greyed with a "Lv N" chip + lock icon,
      big real-button targets per UI readability prefs), live preview of
      pending selection, rename input with validation + reset-to-Circuit,
      Save → `update` on context → toast on success. Unlock hint line
      ("Next unlock at Lv N").
- [x] `DashboardPage.tsx`: swap greeting line for `AvatarCard`; card
      opens the modal; refresh card after save.
- [x] Quiz flow: no code changes expected beyond Mascot reading context —
      verify QuizSessionFlow / LessonQuizSection / QuizDetailPage render
      the customized mascot via the provider.
- [x] `npm install` nothing new expected; if anything is added, install
      in the container too (node_modules is a container volume).

## Verification

- [x] `docker compose exec -T backend pytest` — all green (Phase 32
      baseline 326 + new avatar tests).
- [x] `cd frontend && npx tsc --noEmit` — 0 errors.
- [x] `npm run lint` — no new errors/warnings vs 22-warning baseline.
- [x] `/verify-stack` output shown as evidence.
- [ ] Manual click-through (seeded course, student account):
  - [ ] Dashboard shows the avatar card with default Circuit + name;
        Customize opens the modal; slot tabs + live preview work.
  - [ ] Locked items show "Lv N" and can't be equipped from the UI;
        a forced PATCH for a locked item (devtools/curl) returns 400.
  - [ ] Equip an unlocked item in each slot → card updates; reload
        persists; quiz feedback banner + completion screen show the
        customized Circuit.
  - [ ] Rename to "Sparky" → card greeting uses it; empty and 21-char
        names rejected; reset restores "Circuit".
  - [ ] Cross a level threshold (complete lessons or backdate XP in
        dbshell) → newly unlocked item becomes equippable without any
        manual claim step.
  - [ ] Mascot renders correctly in light + dark themes with items
        equipped, in all four poses (take a quiz, miss one on purpose).
  - [ ] Instructor account: no avatar card, no customizer, GET profile
        still `{is_gamified: false}`, PATCH avatar → 403.
