# Phase 64 — Circuit avatar expansion

## Goal

Grow the Circuit avatar from a 5-slot / 28-item level-gated cosmetic system into an
8-slot / ~71-item system with three unlock axes. Add three new cosmetic slots
(**companion**, **aura**, **held item**), extend the existing five slots with items
reaching **Lv 15** (the catalog currently dead-ends at Lv 8 while levels are uncapped),
and introduce **badge-gated** and **streak-gated** unlocks alongside the existing
level gate. Along the way, restructure the SVG so cosmetic layers live in per-slot
modules instead of one 311-line `Mascot.tsx`, reorganize the customizer from 5 flat
tabs into 3 grouped tabs, surface newly-unlocked cosmetics inside the level-up and
badge-earned celebration modals, and open cosmetic equipping to the shared demo
account (rename stays blocked) so public visitors can actually use the feature.

## Out of scope

- **No dedicated character/profile page.** The customizer modal stays the only
  editing surface (widened + regrouped, not replaced).
- **No avatar in discussion posts, the header/nav bar, or a leaderboard.** Circuit
  stays self-only: dashboard hero, course map, quiz feedback, and (new) the two
  celebration modals. Nothing in this phase exposes one student's avatar config to
  another student, so no serializer touches `UserSerializer`/discussions and no new
  N+1 surface is created.
- **No change to the uploaded profile photo** (`UserPreferences.avatar` ImageField).
  Unrelated feature that shares the word "avatar".
- **No per-user unlock table.** Unlock stays a pure function of existing data
  (derived level, earned badge keys, `longest_streak`). No new model besides three
  `CharField`s on `GameProfile`.
- **No new badges** and no change to `catalog.py` / badge award logic.
- **No change to the leveling formula or XP values.**
- **No animation framework.** Aura effects use existing Tailwind animation utilities
  and SVG only — no new dependency.
- **Does not fix carried remainders**: XP double-award schema bug, `THROTTLE_SLIDE_IMPORT`
  ceiling, phase-61 real-deck slide-import smoke test, JAVA101 answer-rotation reseed,
  phase-56 regression click-through, Sentry LoginPage TypeError. All still open.

---

## Design decisions (settled in the interview — do not relitigate)

1. **Level ceiling → Lv 15.** New level-gated items land at Lv 9–15
   (`xp_for_level`: Lv9 = 3600, Lv10 = 4500, Lv12 = 6600, Lv15 = 10500 XP).
2. **Streak gating reads `longest_streak`, never `current_streak`.** Unlocks must be
   permanent, matching how level and badge unlocks already behave. A student who hits
   14 days and then misses a day keeps the item.
3. **Held items track the arm on all poses.** `Mascot` computes the right-hand
   coordinate per pose and passes it down; each held item draws relative to that point.
4. **Customizer = 3 grouped tabs**, not 8 flat ones: **Look** (color, eyes),
   **Gear** (headgear, accessory, held), **Extras** (companion, aura, backdrop).
   Modal widens; each tab scrolls with a labelled section per slot.
5. **Demo account may equip cosmetics; `mascot_name` stays 403 `demo_blocked`.**
   The name is free text on a profile every visitor shares; slot equips are cosmetic,
   self-scoped and reversible.
6. **New backdrops get the full three-layer treatment** (Mascot SVG panel +
   `BackdropScene` container-scale scene + `backdrop.ts` `SceneTheme`). Only 3 are
   added, so each is done properly. A backdrop with no `SceneTheme` entry is a bug.
7. **Cosmetic layers move into `frontend/src/components/gamification/mascot/`.**
   One module per slot, each exporting a pure component over a shared `LayerProps`.
   This is what makes the frontend work parallelizable — 43 new SVG layers cannot all
   be edited into one file by concurrent subagents. `Mascot.tsx` keeps the base body,
   pose math, and composition only.

---

## Unlock model

Catalog entries gain an optional gate. Exactly one gate per item; `required_level`
remains present on every item (badge/streak items set it to `1` so it never blocks).

```python
{'key': ..., 'slot': ..., 'name': ..., 'description': ...,
 'required_level': 1,              # always present
 'unlock_type': 'level' | 'badge' | 'streak',
 'required_badge': 'perfect_quiz',  # only when unlock_type == 'badge'
 'required_streak': 14}             # only when unlock_type == 'streak'
```

`avatar_payload` computes two derived fields per item and sends them to the frontend
so the UI never re-implements gate logic:

- `unlocked: bool`
- `unlock_label: str` — `"Lv 9"` / `"Sharpshooter badge"` / `"14-day streak"`

`unlock_label` for badge items uses the badge's **display name**, resolved from
`BADGE_CATALOG` in `gamification/catalog.py` (not the raw key). A `required_badge`
that is not in `BADGE_CATALOG` must raise at import time, not render as a blank chip.

**Query discipline (phase-63 rule).** `avatar_payload(profile)` gains an optional
`earned_badge_keys` argument. When omitted it does one `values_list` query; callers
that already have the badge set (`gamification_profile` view builds `earned_badges`
already) pass it in. A test pins the profile endpoint's total query count so a future
caller can't reintroduce a per-item query.

---

## Backend tasks

### Model + migration
- [x] `GameProfile`: add `avatar_companion`, `avatar_aura`, `avatar_held` —
      `CharField(max_length=30, default='none', db_default='none')`.
      Extend the Phase-33 comment block to mention the three unlock axes.
      **`db_default` is load-bearing**, see Deviations #1: without it the
      migration drops the DB default and old code 500s during the deploy window.
- [x] `makemigrations gamification` → one migration adding all three fields. Three
      `AddField`s with literal defaults: additive, reversible, no data migration, no
      table rewrite risk. **Do not apply to Neon** — dev/CI only in this phase.
- [x] `makemigrations --check` clean at the end.

### Catalog (`backend/gamification/avatar_catalog.py`)
- [x] Extend `SLOTS` to the 8-tuple `('color','headgear','eyes','accessory','backdrop','companion','aura','held')`.
      Keep the existing five first — the tuple order drives iteration in `update_avatar`
      and `avatar_payload`.
- [x] Extend `SLOT_DEFAULTS` with `companion: 'none'`, `aura: 'none'`, `held: 'none'`.
- [x] Add `unlock_type` to all 28 existing entries (all `'level'`). Existing
      `required_level` values are unchanged — no student loses access to anything.
- [x] Add `is_unlocked(item, level, earned_badge_keys, longest_streak) -> bool` and
      `unlock_label(item) -> str` helpers. These are the single source of gate truth.
- [x] Add a module-level validation pass (runs at import): every item has a valid
      `slot`, a known `unlock_type`, a `required_badge` present in `BADGE_CATALOG`
      when badge-typed, a positive `required_streak` when streak-typed, and every
      slot has an entry matching its `SLOT_DEFAULTS` key at `required_level` 1 with
      `unlock_type == 'level'`. Raise `ImproperlyConfigured` on violation.
- [x] Add the new items below (43 new; catalog 28 → 71).

**color** — 5 new (existing: classic/1, ember/2, ocean/3, bubblegum/5, gold/7)
| key | name | gate |
|---|---|---|
| `mint` | Mint Circuit | Lv 4 |
| `violet` | Violet Surge | Lv 9 |
| `crimson` | Crimson | Lv 12 |
| `chrome` | Chrome | Lv 15 |
| `aurora` | Aurora Alloy | badge `course_done` |

**headgear** — 5 new (existing: none/1, cap/2, headphones/3, wizard_hat/5, crown/6, halo/8)
| key | name | gate |
|---|---|---|
| `beanie` | Beanie | Lv 4 |
| `hard_hat` | Hard Hat | Lv 9 |
| `space_helmet` | Space Helmet | Lv 11 |
| `laurel` | Laurel Wreath | badge `course_done` |
| `flame_crest` | Flame Crest | streak 14 |

**eyes** — 5 new (existing: none/1, visor/2, glasses/4, starry/6, shades/7)
| key | name | gate |
|---|---|---|
| `sleepy` | Sleepy Eyes | Lv 3 |
| `heart` | Heart Eyes | Lv 9 |
| `scanner` | Scanner Beam | Lv 12 |
| `laser` | Laser Eyes | badge `perfect_quiz` |
| `focus` | Focus Eyes | streak 7 |

**accessory** — 4 new (existing: none/1, bowtie/2, scarf/3, medal/4, cape/6, jetpack/8)
| key | name | gate |
|---|---|---|
| `backpack` | Quest Backpack | Lv 4 |
| `sash` | Champion Sash | Lv 10 |
| `wings` | Circuit Wings | Lv 13 |
| `marksman_pin` | Marksman Pin | badge `perfect_quiz` |

**backdrop** — 3 new (existing: plain/1, none/1, grid/2, stars/4, sunset/5, galaxy/7)
| key | name | gate |
|---|---|---|
| `forest` | Emerald Forest | Lv 6 |
| `arcade` | Arcade Neon | Lv 10 |
| `aurora_sky` | Aurora Borealis | Lv 14 |

**companion** — 7 new slot
| key | name | gate |
|---|---|---|
| `none` | No Companion | Lv 1 (default) |
| `drone` | Scout Drone | Lv 2 |
| `chip` | Chip Sprite | Lv 5 |
| `robo_cat` | Robo-Cat | Lv 8 |
| `owl` | Byte Owl | Lv 12 |
| `dragon` | Pixel Dragon | Lv 15 |
| `phoenix` | Streak Phoenix | streak 30 |

**aura** — 7 new slot
| key | name | gate |
|---|---|---|
| `none` | No Aura | Lv 1 (default) |
| `sparkle` | Sparkles | Lv 3 |
| `pulse` | Energy Pulse | Lv 6 |
| `electric` | Static Arc | Lv 10 |
| `rainbow` | Rainbow Shimmer | Lv 14 |
| `flame_ring` | Flame Ring | streak 7 |
| `golden` | Golden Glow | badge `course_done` |

**held** — 7 new slot
| key | name | gate |
|---|---|---|
| `none` | Empty Hands | Lv 1 (default) |
| `wrench` | Wrench | Lv 2 |
| `controller` | Game Controller | Lv 4 |
| `codex` | Codex | Lv 7 |
| `debug_blade` | Debug Blade | Lv 11 |
| `torch` | Streak Torch | streak 14 |
| `trophy` | Trophy | badge `perfect_quiz` |

### Services (`backend/gamification/services.py`)
- [x] `avatar_payload(profile, earned_badge_keys=None)`: iterate the 8-tuple `SLOTS`;
      resolve each equipped key through `is_unlocked(...)` (not the old
      `level >= required_level`) with fallback to `SLOT_DEFAULTS[slot]`; emit
      `unlocked` + `unlock_label` on every catalog item. When `earned_badge_keys`
      is None, fetch it once with a single `values_list('badge__key', flat=True)`.
- [x] `profile_payload(profile, earned_badge_keys=None)`: thread the argument through
      to `avatar_payload` so the profile view's existing badge query is reused.
- [x] `gamification/views.py::gamification_profile`: pass the already-computed earned
      badge keys into `profile_payload`.

### Endpoint (`backend/gamification/views.py::update_avatar`)
- [x] Move `require_not_demo(user)` off the view body and **into the `mascot_name`
      branch only**. Slot equips become demo-allowed. Keep the instructor 403 at the top.
- [x] Replace the `profile.level < item['required_level']` check with
      `is_unlocked(item, level, earned_badge_keys, profile.longest_streak)`; the 400
      message becomes `f"'{item['name']}' unlocks at {unlock_label(item)}."`
- [x] Fetch the earned badge key set **once** before the slot loop, not per slot.
- [x] All-or-nothing behaviour is unchanged: any invalid/locked field short-circuits
      to 400 before `save()`, including a valid rename in the same body. A demo-account
      body carrying `mascot_name` + valid slots must persist **nothing** and 403.
- [x] Docstring update: 8 slots, three gate types, demo policy.

### Backend tests (`backend/gamification/tests.py`, extend `TestAvatar`)
- [x] `[P]` Defaults: a fresh profile reports all 8 slots at their `SLOT_DEFAULTS`.
- [x] `[P]` Level gate boundary at Lv 9 (3599 XP locked / 3600 XP unlocked) and at
      Lv 15 (10499 / 10500) — proves the extended ladder works, not just Lv 8.
- [x] `[P]` Badge gate: without `perfect_quiz`, `laser` eyes are `unlocked: false` and
      PATCH 400s; after awarding the badge, `unlocked: true` and PATCH 200s.
- [x] `[P]` Streak gate reads `longest_streak`: profile with `current_streak=0`,
      `longest_streak=30` can equip `phoenix`; profile with `current_streak=30`,
      `longest_streak=0` cannot. This is the regression guard for decision #2.
- [x] `[P]` A streak/badge unlock is never revoked: equip `phoenix`, then set
      `current_streak=0`, and `equipped.companion` still reports `phoenix`.
- [x] `[P]` `unlock_label` shape for all three types: `"Lv 9"`, `"Sharpshooter badge"`,
      `"14-day streak"`.
- [x] `[P]` Stale-key fallback for the three new slots (equip, then monkeypatch the
      key out of the catalog → payload reports the slot default, no 500).
- [x] `[P]` Catalog integrity: every `required_badge` exists in `BADGE_CATALOG`; every
      slot has a level-1 default; keys unique within each slot.
- [x] Query-count guard (phase-63 style): `GET /api/gamification/profile/` issues the
      same number of queries with 71 catalog items as with 28 — i.e. the badge set is
      fetched once, not per item.
- [x] Demo policy: demo account PATCHing `{'headgear': 'cap'}` → **200 and persists**;
      PATCHing `{'mascot_name': 'Vandal'}` → 403 `demo_blocked`; PATCHing both in one
      body → 403 **and the headgear is unchanged**.
- [x] Confirm `core/tests/test_demo_lockdown.py::test_gamification_avatar_blocked`
      (line ~204) still passes unchanged — it already sends `mascot_name`.
- [x] Instructor still 403s on the whole endpoint.

---

## Frontend tasks

### Types + service
- [x] `types/index.ts`: extend `AvatarSlot` to the 8-member union; add
      `unlock_type: 'level' | 'badge' | 'streak'`, `unlock_label: string`,
      `required_badge?: string`, `required_streak?: number` to `AvatarItem`.
      `AvatarEquipped` / `AvatarUpdatePatch` follow automatically from `AvatarSlot`.
- [x] No `services/gamification.ts` change needed — `updateAvatar(patch)` is already generic.

### Mascot layer extraction (do this **first** — it unblocks the parallel SVG work)
- [x] Create `frontend/src/components/gamification/mascot/types.ts` exporting
      `LayerProps { itemKey: string; primary: string; surface: string; outline: string;
      gold: string; pose: MascotPose; gradientId: string }` and a `HandPoint {x, y}`.
- [x] Refactor `Mascot.tsx`: keep the base body (antenna, head, base eyes, mouth, arms,
      body, feet), pose math, `COLOR_SCHEMES`, `useId`, and composition. Compute
      `rightHand: HandPoint` / `leftHand: HandPoint` from the same expressions that
      already position the arm `<line>` endpoints (lines 266–277) — one source of truth,
      so the hand and the held item can never drift.
- [x] Move existing layers out verbatim into the new modules (no visual change in this
      step): `Backdrops.tsx`, `Headgear.tsx`, `Eyes.tsx`, `Accessories.tsx`.
      `Accessories.tsx` exports **two** components — `BehindBodyAccessory` (cape,
      jetpack) and `ChestAccessory` (bowtie, scarf, medal) — because they sit on
      opposite sides of the body in the draw order.
- [x] Preserve the existing draw order exactly: backdrop → behind-body accessory →
      **aura (new, behind Circuit)** → antenna → head → eyes → eye cosmetics → mouth →
      headgear → arms → body → chest accessory → **held (new)** → feet →
      **companion (new, drawn last, front-most)**.
- [x] Preserve `useId`-namespaced gradient ids in every new module — the customizer
      grid renders dozens of mascots at once and colliding ids will silently swap fills.

### New + extended SVG layers — all `[P]`, one file each
- [x] `[P]` `mascot/Colors.ts` — add `mint`, `violet`, `crimson`, `chrome`, `aurora`
      to `COLOR_SCHEMES` (moved out of `Mascot.tsx` so it isn't a merge point).
- [x] `[P]` `mascot/Headgear.tsx` — add `beanie`, `hard_hat`, `space_helmet`,
      `laurel`, `flame_crest`.
- [x] `[P]` `mascot/Eyes.tsx` — add `sleepy`, `heart`, `scanner`, `laser`, `focus`.
      Each must handle the `happyEyes` variant (cheer/celebrate) the way `visor`
      already does, or explicitly render identically in both.
- [x] `[P]` `mascot/Accessories.tsx` — add `backpack` (behind body), `sash` (chest),
      `wings` (behind body), `marksman_pin` (chest).
- [x] `[P]` `mascot/Companion.tsx` — new; `drone`, `chip`, `robo_cat`, `owl`,
      `dragon`, `phoenix`. Drawn in the lower-right of the 120×120 viewBox, sized so
      it stays legible at `size={72}` (course map) and doesn't collide with the
      jetpack/cape at `size={150}` (hero).
- [x] `[P]` `mascot/Aura.tsx` — new; `sparkle`, `pulse`, `electric`, `rainbow`,
      `flame_ring`, `golden`. Renders **behind** Circuit and must not obscure the face.
      Use existing Tailwind `animate-pulse`/`animate-ping` only; respect
      `prefers-reduced-motion` via Tailwind's `motion-reduce:` variant.
- [x] `[P]` `mascot/Held.tsx` — new; `wrench`, `controller`, `codex`, `debug_blade`,
      `torch`, `trophy`. Takes `hand: HandPoint` and draws relative to it, so it tracks
      idle / cheer / celebrate arm positions (decision #3).
- [x] `mascot/Backdrops.tsx` — add `forest`, `arcade`, `aurora_sky` SVG panels.
      **Not `[P]`** with the two below: the same three scenes must be authored
      consistently across all three files.
- [x] `BackdropScene.tsx` — container-scale versions of `forest`, `arcade`,
      `aurora_sky`, following the existing dead-zone rule (accents only in the narrow
      top-center strip and side edges below the corner HUD).
- [x] `backdrop.ts` — a `SceneTheme` entry for each of the three. `forest` is a dark
      scene (`dark: true`); `arcade` is dark with neon accents; `aurora_sky` is dark.
      Every field (`numeral`, `accent`, `label`, `track`, `bubble`, `button`) must be
      filled — falling through to `DEFAULT_THEME` on a dark scene makes the hero text
      unreadable.

### Customizer (`AvatarCustomizerModal.tsx`)
- [x] Replace `SLOT_TABS` with a `TAB_GROUPS` structure:
      `Look` → [color, eyes]; `Gear` → [headgear, accessory, held];
      `Extras` → [companion, aura, backdrop].
- [x] Widen the dialog and give each tab a scrollable body with a labelled section per
      slot. Preview stays pinned and visible while scrolling.
- [x] `itemsBySlot` currently hard-codes the five slot keys as an object literal
      (line ~57) — rebuild it from the `AvatarSlot` union so adding a slot can't
      silently drop items.
- [x] Locked chip renders `item.unlock_label` instead of a hard-coded `Lv {n}`.
- [x] "Next unlock at Lv N" hint generalizes to "Next unlock: {label}", choosing the
      cheapest locked item across all slots (level items ordered by `required_level`;
      badge/streak items listed after).
- [x] Item thumbnails keep the live `<Mascot size={56} customization={{...pending, [slot]: key}} />`
      pattern. With 71 items this is now ~71 SVG instances if all tabs mount at once —
      keep Radix `Tabs` lazy (unmounted inactive tabs) so only one group renders.
- [x] Demo account: the rename input + "Reset to Circuit" are disabled with a short
      "Not available in the shared demo" note; slot tabs stay fully usable. Save must
      omit `mascot_name` from the patch when it is unchanged, so a demo save of
      cosmetics-only succeeds.

### Celebration modals
- [x] `LevelUpModal`: add `<Mascot pose="celebrate" size={110} />` and, below it, any
      catalog items with `unlock_type === 'level' && required_level === level` —
      rendered as small preview tiles with names ("New: Hard Hat, Static Arc"). Derive
      from `useAvatarContext().avatar?.catalog`; the catalog is static so this is
      correct even before the context refreshes.
- [x] `BadgeEarnedModal`: alongside the badge icon, show any catalog items with
      `unlock_type === 'badge' && required_badge === badge.key`. Render nothing extra
      when a badge unlocks no cosmetics (`first_lesson`, `streak_7`, the three `xp_*`)
      — the modal must not grow an empty section.
- [x] `useGamificationFeedback`: call `useAvatarContext().refresh()` once after the
      celebration queue drains, so the customizer shows the new items as unlocked
      without a page reload. Must be a no-op for instructors and safe when the
      provider is absent (`useAvatarContext` already returns a null avatar outside it).

### Frontend tests
- [x] `[P]` Vitest: `Mascot` renders every catalog key for all 8 slots without
      throwing (table-driven over the key lists) — the cheap guard against a catalog
      entry with no matching SVG branch.
- [x] `[P]` Vitest: two `Mascot` instances mounted together produce **distinct**
      gradient ids (regression guard on the `useId` namespacing across the new modules).
- [x] `[P]` Vitest: `getSceneTheme` returns a fully-populated theme for every backdrop
      key in the catalog — fails if `forest`/`arcade`/`aurora_sky` fall through to
      `DEFAULT_THEME`.
- [x] `[P]` Vitest: `Held` places the item at the **celebrate**-pose hand coordinate,
      not the idle one. (Spec originally said `cheer`; that is unimplementable —
      `cheer` raises only the LEFT arm, so the right hand, and therefore the held
      item, is identical for idle/cheer/encourage. Corrected during implementation.)

---

## Verification

### Automated — `/verify-stack` must PASS
- [x] `cd backend && pytest` — 710 tests currently pass; expect ~+20. Named checks
      that must be green:
  - `gamification/tests.py::TestAvatar` — all 8 slot defaults, Lv 9 and Lv 15 gate
    boundaries, badge gate on/off, `longest_streak` vs `current_streak`, unlock never
    revoked, `unlock_label` strings, stale-key fallback on new slots, catalog integrity.
  - the profile-endpoint query-count guard (badge set fetched once).
  - demo: slot equip 200 + persists, rename 403, mixed body 403 with nothing persisted.
  - `core/tests/test_demo_lockdown.py::TestDemoBlockedWrites::test_gamification_avatar_blocked`
    unchanged and still passing.
- [x] `docker compose exec -T backend python manage.py makemigrations --check` clean.
- [x] `cd frontend && npx tsc --noEmit` → 0 errors. The `AvatarSlot` widening will
      surface every place a 5-key record is built — all must be fixed, not cast.
- [x] `cd frontend && npm run lint` → 0 errors (1 pre-existing warning is the baseline).
- [x] `cd frontend && npx vitest run` → 101 existing + the 4 new suites above.
- [x] **Measured:** pytest 737 (was 710, +27); vitest 116 (was 101, +15); tsc 0;
      lint 0 errors / 1 pre-existing warning. Bundle: total JS 618 → 623 kB gzip
      (+5 kB); the `Mascot` chunk itself 2.23 → 6.40 kB gzip (+4.17 kB), well
      under the ~15 kB threshold below. Baseline measured by building `main` in
      a throwaway worktree, not estimated.
- [x] `npm run build` succeeds (needs `VITE_API_URL`). Note the bundle delta: 43 new
      inline SVG layers land in the main chunk. Record the before/after gzip size in
      the handoff; investigate if it grows by more than ~15 kB gzip.

### Manual click-through

> Not performed by the implementation session — these need the running app
> and a live account. Unticked deliberately; see the handoff.
 (student account above Lv 15, or XP-boosted in dev)
- [ ] Dashboard → **Customize** → modal shows 3 tabs (Look / Gear / Extras), all
      8 slots reachable, preview pinned while scrolling.
- [ ] Equip a companion + an aura + a held item + a new backdrop → Save → toast →
      dashboard hero updates immediately, and the hero's numerals/buttons/bubble
      restyle to the new scene (not `DEFAULT_THEME` on a dark backdrop).
- [ ] Course map page: Circuit renders at `size={72}` with the companion and held item
      still legible and not overlapping the path node; page background is the new scene.
- [ ] Quiz feedback (`cheer`) and quiz pass (`celebrate`): the held item stays **in the
      hand** at both raised-arm positions — this is the specific check for decision #3.
- [ ] Locked-item chips read the right gate: a level item shows "Lv 12", `laser` eyes
      show "Sharpshooter badge", `phoenix` shows "30-day streak".
- [ ] Earn a level → LevelUpModal lists the cosmetics unlocked at that level.
      Earn `perfect_quiz` → BadgeEarnedModal lists Laser Eyes / Marksman Pin / Trophy.
      Earn `xp_100` → BadgeEarnedModal shows **no** cosmetics section.
- [ ] Both light and dark theme on the three new backdrops.
- [ ] **Demo account** (`stemquests.com`, or DEMO_ACCOUNT_EMAIL locally): Customize
      opens, a slot equip saves successfully, the rename input is disabled with the
      demo note. Caveat: the demo profile is low-level, so verify with an item unlocked
      at Lv 1–2 (`cap`, `wrench`, `drone`).

### Deploy
- [x] The migration adds three defaulted `CharField`s — additive and reversible, but
      it **must be applied to Neon** for the endpoint to work in prod. Per
      `CLAUDE.md`, do not apply it during implementation; open the PR and stop.

---

## Notes for the implementation session

- Backend changes need `docker compose restart backend`.
- `head` is shadowed locally — use `/usr/bin/head`.
- Backend tests run via `docker compose exec -T backend pytest`.
- The `[P]` SVG modules are only parallel-safe **after** the layer-extraction task
  lands. Do the extraction as a single sequential commit first, verify no visual
  change, then fan out.
- `Accessories.tsx` is touched by one `[P]` item but exports two components — don't
  split it across two subagents.
- The three backdrop files (`mascot/Backdrops.tsx`, `BackdropScene.tsx`, `backdrop.ts`)
  are deliberately **not** marked `[P]` relative to each other.

---

## Deviations and findings (recorded during implementation)

Found by the finish-phase review pass. Everything here was either fixed or is
consciously accepted — nothing was silently dropped.

### Fixed

1. **`db_default` on the three new fields** (found by `db-migration-checker`, and
   reproduced). `AddField(default=...)` backfills and then issues
   `ALTER COLUMN ... DROP DEFAULT`, leaving `NOT NULL` columns with no database
   default. Because migrations are applied to Neon by hand *before* the new code
   deploys, and `GameProfile` rows are created lazily by `get_or_create()` on the
   dashboard and in every XP award, a student without a profile row would have hit
   an `IntegrityError` 500 during the deploy window. The three fields now carry
   `db_default='none'` as well as `default='none'`, so the migration keeps the
   database default. Verified: the exact INSERT the old code generates (omitting
   all three columns) now succeeds and Postgres fills in `'none'`.
   **Note for future phases:** the phase-33 avatar fields have the same shape and
   the same latent hazard. Any new `NOT NULL` field on `GameProfile` should use
   `db_default`.

2. **NUL byte in `mascot_name` returned a 500, not a 400** (found by
   `adversarial-tester`, reproduced). The name branch only did `strip()` and a
   length check, so `'a\x00b'` passed validation and raised an unhandled
   `psycopg.DataError` inside `save()`. Added `clean_mascot_name()`, which NFKC-
   normalizes and rejects any Unicode "other" category (`Cc` control, `Cf` format,
   `Cs`/`Co`/`Cn`). This also closes the zero-width-space "blank name" bypass and
   the RTL-override display-spoof the same pass flagged as SUSPICIOUS. Pinned by
   `TestAvatarNameHardening`. Pre-existing since phase 33, fixed here because this
   phase touched the branch.

3. **The query-count guard did not guard anything** (found by `code-reviewer`,
   demonstrated). It compared a 0-badge request to a 2-badge request; a per-item
   badge query costs the same in both, so the N+1 it was meant to catch passed
   straight through. Replaced with an absolute query budget plus a second test that
   triples the catalog and asserts the query count is unchanged.

4. **Instructor boundary was untested on the cosmetic path.** The only instructor
   test sent `mascot_name` — but this phase's central edit moved the demo guard into
   that branch, leaving the role check as the sole gate for slot-only bodies. Added
   `test_instructor_403_on_cosmetic_only_body`.

5. **Rename-only PATCH paid for an unused badge query.** Now skipped, passing `None`
   (not an empty set — an empty set would render every badge-gated item as locked in
   the response). Guarded by `test_rename_only_patch_still_reports_badge_unlocks`.

6. **The "every catalog key has art" test could not fail.** Layers return `null` for
   unknown keys, so a key with no SVG branch rendered an invisible cosmetic and
   passed. Now compares each non-default key's render against the default, with
   `useId` values normalized out so the comparison isn't vacuous. All 71 keys pass.

### Accepted, not fixed

- ~~**Companions overlap the jetpack's right thruster at `size={150}`.**~~
  **FIXED after merge** (commit `1a1ce4d`, "declutter the avatar composition"). The
  fix for the crowded hero extended the viewBox to reserve a 20-unit margin and
  offset the companion group into it, which cleared this collision as a side effect —
  no creature had to be redrawn. Verified visually against jetpack, cape, wings and
  backpack. This entry is kept rather than deleted so the record shows it was
  accepted, then resolved.
- **`mascot_name` has no content moderation** beyond character-class validation.
  Out of scope by design: the name is self-only and never rendered on a shared
  surface, and React escapes it. Worth revisiting if it is ever surfaced to other
  users or into an HTML email.
