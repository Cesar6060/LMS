# Handoff: Phase 64 shipped to prod; aura slot retired

## Current state
**Phase 64 is LIVE on production.** PR #82 merged as `4cab8177`.
- Migration `gamification/0005` **applied to Neon 2026-07-31 05:52 UTC** (three
  defaulted CharFields on `GameProfile`). Verified after: `column_default` is
  `'none'::character varying` on all three — the `db_default` fix held, which is
  what kept the old code alive during the deploy window. Proven, not assumed:
  the then-deployed phase-63 code served its 5-slot/28-item payload fine
  against the new schema.
- Verified live: profile API returns 8 slots / 71 items; demo account equips
  cosmetics (200) but 403s `demo_blocked` on rename; served `Mascot-*.js`
  contains `viewBox:"-20 -20 160 160"`.

**Post-merge fix, also live:** `1a1ce4d` "declutter the avatar composition".
Aura rings sat at r 42–50 from centre while Circuit's arms reach r=42 and feet
r=53 — so they cut *through* the robot. viewBox extended to `-20 -20 160 160`,
all call sites scaled 4/3, companion offset into the new margin, customizer
tiles now mute dominant slots.

**Dependency PRs merged** (#83 `setup-python` 5→7, #84 `checkout` 4→7,
#85 frontend minor/patch group). All CI-only or frontend-only — no
`requirements.txt`, so no Neon work. CI green on main.

## In progress / not done
- **PR #89 `chore/retire-aura-slot` — OPEN, CI green, ready to merge.**
  https://github.com/Cesar6060/LMS/pull/89
  Removes the aura slot (catalog 71 → 64 items, 8 → 7 slots). **Needs NO
  database migration** — `avatar_aura` column deliberately left in place;
  `makemigrations --check` clean; 0 migration files in the diff.
- **Dependabot majors left open, all failing or unassessed:** #86 eslint 9→10
  (lint job fails), #68 react-dom, #87 vite 6→8, #88 tailwind 3→4.
- **Manual click-through for phase 64 never done** — the 8 items in the spec.
  Layers were verified in isolation and the hero/customizer checked live, but
  course map, quiz-feedback poses and both themes were not walked through.
- Carried: `THROTTLE_SLIDE_IMPORT` ceiling; phase-61 real-deck slide-import
  smoke test; XP double-award; JAVA101 answer-rotation reseed; phase-56
  regression click-through; Sentry LoginPage TypeError.

## Next steps
1. Merge PR #89 (no DB action needed).
2. **XP double-award** — the recommended next phase. `XPEvent.source_id` is a
   bare int keyed on lesson/quiz PKs, so rebuilding course content re-awards XP.
   The "needs a migration" claim is inherited from the phase-58 handoff and has
   **never been verified** — check that against the models first.
3. vite 6→8 and tailwind 3→4 majors (tailwind 4 is a config rewrite).
4. Phase-61 real-deck import smoke test — still the only flow never exercised
   against R2 signed URLs.

## Decisions made
- **Retired the aura by removing it from `SLOTS`, not by dropping the column.**
  Dropping is irreversible and breaks still-running old code; this project
  migrates Neon by hand *before* deploying. Absent from `SLOTS` it is never read
  or served. `test_retired_aura_slot_is_not_served` pins that, including that
  `PATCH {"aura": ...}` can't equip it through the back door.
- **Local dev students pruned to one.** `student2-5@demo.com` deleted (88 rows).
  `student1@demo.com` / `Admin123!` is the single test student, XP set to Lv 15
  with `longest_streak=30` and both gating badges, so every item is unlocked.
  Kept `admin@demo.com` (superuser) and `jdoe@demo.com` (`DEMO_ACCOUNT_EMAIL` —
  deleting it breaks the demo sandbox).

## Gotchas discovered
- **`AddField(default=...)` drops the DB default** (`ALTER COLUMN ... DROP
  DEFAULT`). With migrate-then-deploy ordering and lazily created `GameProfile`
  rows, that would 500 every profile-less student. Use `db_default=`. The
  phase-33 avatar fields still carry this latent hazard.
- **Never run pytest concurrently** with review subagents — shared test DB gives
  hundreds of bogus errors. A clean serial run is 766 passed.
- **`frontend/node_modules` is a container volume** — `rm -rf` fails with
  permission denied from the host. Run npm inside `docker compose exec frontend`.
  After a lockfile change, rollup's native binary needs a relink there.
- Aura/companion placement must clear the **silhouette** (arms r=42, feet r=53),
  not just the head.

## Files to read first
1. `docs/specs/phase-64-circuit-avatar-expansion.md` — checklist + Deviations.
2. `backend/gamification/avatar_catalog.py` — 7 slots, gates, import validator.
3. `frontend/src/components/gamification/Mascot.tsx` — viewBox margin, draw order.
4. `frontend/src/components/gamification/AvatarCustomizerModal.tsx` — tile muting.
