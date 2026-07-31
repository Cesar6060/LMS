# Handoff: Phase 64 — Circuit avatar expansion

## Current state
Phase 64 complete, **PR #82 open, NOT merged**:
https://github.com/Cesar6060/LMS/pull/82 on branch
`feat/phase-64-circuit-avatar-expansion` (commits `580df31` feat, `56c768f`
docs, `0c85c4f` review fixes).

Circuit went from **5 slots / 28 items** to **8 slots / 71 items**, and from a
single level gate to three (level / badge / streak).
- `GameProfile` gained `avatar_companion`, `avatar_aura`, `avatar_held`
  (migration `gamification/0005`, applied in dev only).
- `avatar_catalog.py`: `unlock_type` on every item, `is_unlocked()` /
  `unlock_label()` as the single source of gate truth, and an import-time
  `_validate_catalog()` that raises `ImproperlyConfigured`.
- New level items reach **Lv 15**; badge gates use `perfect_quiz` /
  `course_done`; streak gates read **`longest_streak`**, never `current_streak`.
- Demo account can now equip cosmetics; `mascot_name` still 403 `demo_blocked`.
- Frontend: cosmetic layers extracted out of `Mascot.tsx` into
  `components/gamification/mascot/` (one module per slot). Three new backdrops
  with all three layers. Customizer regrouped into 3 tabs. Level-up and
  badge-earned modals preview what was just unlocked.

Verified: **766 backend tests** (was 710), **124 vitest** (was 101), tsc 0,
lint 0 errors / 1 pre-existing warning, `makemigrations --check` clean, build
OK. Total JS 618 → 623 kB gzip (+5 kB); Mascot chunk 2.23 → 6.40 kB gzip.
All 71 keys were rendered and inspected visually at 120px and 72px.

## In progress / not done
- **PR #82 not merged.** Migration must be applied to Neon FIRST (see below).
- **Manual click-through not performed** — the 8 items under "Manual
  click-through" in the spec are deliberately left unticked. They need the
  running app and a live account: dashboard hero restyling per scene, course
  map at 72px, quiz feedback poses, both themes on the new backdrops, and the
  demo account on prod. The SVG layers themselves were verified in isolation.
- **Accepted deviation:** companions overlap the jetpack's right thruster at
  `size={150}`. Cape/wings/backpack are clean. Verified visually, not assumed;
  full separation would need all six creatures redrawn into a ~24-unit strip,
  costing more at 72px than the overlap costs at 150px. Revisit only if it
  looks wrong in the live hero.
- Still open, carried: `THROTTLE_SLIDE_IMPORT` ceiling decision; phase-61
  real-deck slide-import smoke test; XP double-award schema fix; JAVA101
  answer-rotation reseed; phase-56 regression click-through; Sentry LoginPage
  TypeError.

## Next steps
1. **Apply `gamification/0005` to Neon BEFORE merging** —
   `DATABASE_URL=<neon> python manage.py migrate gamification` from a dev
   machine. It is additive, reversible, and metadata-only on PG16. Order
   matters: the fields carry `db_default`, so old code keeps working against
   the new schema, but new code does NOT work against the old schema.
2. Merge PR #82, let Render + Pages deploy, then check
   `https://api.stemquests.com/api/health/?deep=1`.
3. Run the manual click-through in the spec (8 items). The one worth doing
   first is the demo account on stemquests.com — equip a Lv-1/2 item
   (`cap`, `wrench`, `drone`) and confirm the rename input is disabled.
4. Next phase candidate: **XP double-award** (carried since phase 58) —
   `XPEvent.source_id` is a bare int keyed on lesson/quiz PKs, so rebuilding
   course content re-awards XP. Verify the "needs a migration" claim against
   the gamification models before scoping; that assumption is inherited and
   still unchecked.

## Decisions made
- **Streak gates read `longest_streak`.** A revocable gate would silently
  downgrade an equipped item to the slot default the morning after a missed
  day — that reads as a bug to a 12-year-old, not as a consequence.
- **`db_default` on the three new fields, not just `default`.** See Gotchas.
- **Layers extracted into per-slot modules before any new art was drawn.**
  43 new SVG layers could not land in one file, and it's what made the work
  parallelizable across subagents.
- **Held items anchor to a hand point computed from the same expressions that
  draw the arm**, so art and arm cannot drift. Note `cheer` raises only the
  LEFT arm — the right hand is identical for idle/cheer/encourage, so
  `celebrate` is the only pose that actually moves a held item.
- **`unlock_label` is computed server-side.** The frontend renders a string;
  it never re-implements gate logic.
- **Demo guard narrowed rather than removed.** A body mixing a rename with
  valid cosmetics still 403s and persists nothing.

## Gotchas discovered
- **`AddField(default=...)` drops the DB default.** Django emits
  `ADD COLUMN ... DEFAULT x NOT NULL` then `ALTER COLUMN ... DROP DEFAULT`.
  Since migrations are applied to Neon by hand *before* the code deploys, and
  `GameProfile` rows are created lazily by `get_or_create()` in the dashboard
  and every XP award, old code's column-omitting INSERT would have 500'd for
  the whole deploy window. `db_default=` fixes it. **The phase-33 avatar fields
  have the same latent hazard** — any future `NOT NULL` field on `GameProfile`
  should use `db_default`.
- **A NUL byte in a CharField is a 500, not a 400.** `strip()` + a length check
  is not enough validation for free text headed to Postgres; psycopg raises
  `DataError` at `save()`. `clean_mascot_name()` now rejects all Unicode "other"
  categories, which also closes a zero-width-space blank-name bypass.
- **Before/after query-count tests can be vacuous.** Comparing 0 badges to 2
  badges does not catch a per-item query — it costs the same in both. Assert an
  absolute budget, or scale the thing that would drive the N+1 (the catalog).
- **"Renders without throwing" is not a guard.** Every layer returns `null` for
  unknown keys, so a catalog entry with no art passed. Compare against the
  default render — and normalize `useId` values out, or the comparison is
  vacuous in the other direction.
- **Do not run pytest concurrently** (e.g. while review subagents are running).
  They share one test database and you get hundreds of bogus errors. A clean
  serial run was 766 passed.
- `animate-ping`/`animate-spin` on SVG children apply `transform` with
  `transform-origin` at the viewBox origin, so elements fly off-canvas rather
  than scale in place. `animate-pulse` (opacity only) is safe.
- Bare `head` is shadowed locally — use `/usr/bin/head`.

## Files to read first
1. `docs/specs/phase-64-circuit-avatar-expansion.md` — checklist plus the
   "Deviations and findings" section at the end.
2. `backend/gamification/avatar_catalog.py` — the 71-item catalog, the gate
   helpers, and the import-time validator.
3. `backend/gamification/views.py::update_avatar` + `clean_mascot_name`.
4. `frontend/src/components/gamification/mascot/types.ts` — the `LayerProps`
   contract every cosmetic layer implements.
5. `frontend/src/components/gamification/Mascot.tsx` — composition order and
   the hand-point math.
