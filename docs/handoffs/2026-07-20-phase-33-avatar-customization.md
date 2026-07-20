# Handoff: Phase 33 — Circuit avatar customization

## Current state
Phase 33 **implemented + verified + committed** on branch
`feat/phase-33-avatar-customization` (branched from the merged Phase 32 HEAD
`a8d00b3`; PR #17 carrying Phases 29–32 has since **merged into `lms/main`**).
Commits: `e4688d0` feat (Phase 33 code), plus this docs commit.

Backend:
- `GameProfile` gains six fields in migration `gamification/0004` (applied in
  dev): `mascot_name` (default `'Circuit'`), `avatar_color` (`'classic'`),
  `avatar_headgear`/`avatar_eyes`/`avatar_accessory` (`'none'`), and
  `avatar_backdrop` (`'plain'`).
- `gamification/avatar_catalog.py`: code catalog (no DB table), 28 items over
  **five** slots — color, headgear, eyes, accessory, backdrop — spread levels
  1–8. Keys unique per slot (`'none'` repeats), so the helper is
  `get_item(slot, key)`.
- `profile_payload()` now embeds an `avatar` block: `{mascot_name, equipped,
  catalog}` with `unlocked` derived from level; a stale equipped key resolves
  to the slot default server-side. Instructor GET stays `{is_gamified: false}`.
- `PATCH /api/gamification/avatar/` (students only; instructors 403): partial
  body of `mascot_name` and/or slot keys; all-or-nothing — any invalid field
  is a 400 `{'detail': ...}` and nothing persists. Name trimmed 1–20 chars;
  key must exist, match the slot, and be unlocked at the current level.
- 15 new tests in `gamification/tests.py` (`TestAvatar`): defaults, unlock
  boundary at 99/100 XP, equip persist, locked/unknown/slot-mismatch 400s,
  rename + trim + invalid, stale-key fallback, 401/403 boundaries.

Frontend:
- `contexts/AvatarContext.tsx` — loads the avatar block for students
  (instructors: null), exposes `{avatar, refresh, update}`; mounted in
  `App.tsx` around the routes. `useAvatarContext` is safe outside the
  provider (returns null avatar).
- `Mascot.tsx` — optional `customization` prop defaulting to context, so
  QuizSessionFlow / LessonQuizSection / QuizDetailPage picked up the custom
  look with zero changes. Cosmetics are code-drawn SVG layers: 5 palette
  swaps, 5 headgear, 4 eye styles, 5 accessories, 5 backdrops (backdrop
  default `plain` panel; `none` opts out). Gradient ids use `useId` so the
  customizer grid's many mascots don't collide.
- `AvatarCard.tsx` (dashboard, replaces the Phase 32 greeting line): big
  mascot, rename-aware greeting, level chip, Customize button.
- `AvatarCustomizerModal.tsx`: five slot tabs, per-item live-preview tiles,
  locked items greyed w/ lock + "Lv N" chip, "Next unlock at Lv N" hint,
  rename input w/ validation + reset-to-Circuit, save → context update →
  toast.
- Types (`AvatarSlot/AvatarItem/AvatarState/AvatarUpdatePatch`) +
  `gamificationService.updateAvatar`.

Verified: **pytest 341 passed** (326 baseline + 15 new); **tsc 0 errors**;
**lint 0 errors / 22 warnings** (= baseline; AvatarContext carries a targeted
eslint-disable for the same react-refresh warning its sibling contexts have).

## In progress / not done
- **Manual click-through** — the only unchecked spec section (§Verification):
  avatar card + customizer, locked-item 400 via curl, persistence, rename,
  level-threshold unlock, all four poses in quiz flows, instructor inertness.
- Phase 31/32 manual click-throughs were also still open per their handoffs.

## Next steps
1. Manual click-through per spec §Verification; check off in
   `docs/specs/phase-33-avatar-customization.md`.
2. Review + merge the Phase 33 PR (branch `feat/phase-33-avatar-customization`
   → `lms/main`).
3. Local branch cleanup: merged phase branches 29–32 can be deleted.

## Decisions made
- **Backdrop slot added mid-phase** (user request): fifth slot rendered as a
  container inside the mascot SVG; default `plain` so Circuit always sits in
  a backdrop, `none` item opts out.
- Catalog keys unique per slot → `get_item(slot, key)` (deviation from the
  spec's `get_item(key)` signature, noted in the spec).
- PATCH is all-or-nothing (single 400 short-circuits before save) — matches
  "equip locked item → nothing persists" including a valid rename in the
  same body.
- One migration for all six fields (0004 was rolled back and regenerated when
  backdrop landed mid-phase — safe because nothing had been committed).
- Per-phase PRs going forward: PR #17 (Phases 29–32) had already merged as a
  single PR, so retroactive per-phase PRs aren't possible; Phase 33 starts
  the one-PR-per-phase convention.

## Gotchas discovered
- `ToastOptions` uses `message` (variants: default/xp/success — no error
  variant); errors surface as default-variant toasts with a ⚠️ icon.
- The local `feat/phase-31-instructor-analytics` branch pointer had drifted
  onto a Phase 32 commit (`c45087a`) — irrelevant now that everything merged,
  but don't trust old phase branch tips.
- DRF test client can't multipart-encode `None` values — use `format='json'`
  for null-field requests.
- Backend runs tests via `docker compose exec -T backend pytest`; `head` is
  shadowed locally (use `/usr/bin/head`); frontend node_modules is a
  container volume.

## Files to read first
- `docs/specs/phase-33-avatar-customization.md` (only manual section open)
- `backend/gamification/avatar_catalog.py` + `views.py::update_avatar`
- `frontend/src/components/gamification/Mascot.tsx` (slot layer rendering)
- `frontend/src/contexts/AvatarContext.tsx`
- `frontend/src/components/gamification/AvatarCustomizerModal.tsx`
