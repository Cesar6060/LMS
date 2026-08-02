# Phase 50: Loose-Ends Hardening

## Goal

Close the small items deferred across the production track (phases 36-49)
so the backlog is empty before any new product work: move the Django admin
off the default `/admin/` path in production (env flip only — the
`ADMIN_URL` mechanism has existed since phase 42/43 but was never applied),
retire the stale PLAN.md (roadmap ends at phase 33; phases 34-49 ran
without it), split the frontend bundle so the 1.29 MB Vite warning
(deferred since phase 38) goes away, burn the 22 baseline lint warnings to
zero, and verify the phase 42 leftover that `instructor@demo.com` does not
exist in prod Neon.

## Out of scope

- Custom domain (still deferred; the email half was done in phase 47)
- httpOnly-cookie JWT transport (explicitly deferred while in demo mode)
- New product features or a roadmap refresh — PLAN.md is retired, not
  replaced; the next roadmap is its own future planning session
- Any `envVars` block in render.yaml (env vars stay dashboard-only — the
  Blueprint re-adopted the service at phase 49 close and shape fields are
  live; see 2026-07-22-phase-49-closeout.md)
- New admin gating/honeypot/logging code — no backend code changes at all
- Fixing or suppressing warnings by disabling lint rules file-wide

## Pre-flight

- [x] PR #46 (`chore/phase-49-final-cleanup`) must be merged to main first;
      branch phase 50 off fresh main. (Merge was attempted at spec time but
      blocked by tool permissions — USER merges.)

## Backend tasks

No models, no migrations, no endpoint or settings changes. This section is
operator action + verification only.

- [x] Write `docs/runbooks/phase-50-admin-url-steps.txt` (plain text):
      generate a random slug (e.g. `openssl rand -hex 8` → `<slug>-console/`),
      set `ADMIN_URL` env var on `stemquest-api-va` in the Render dashboard
      (env change auto-restarts the service), where the slug is recorded
      (password manager — NOT committed to the repo), and rollback (delete
      the env var).
- [ ] USER action: set `ADMIN_URL` in the Render dashboard per the runbook.
- [ ] Verify: `https://stemquest-api-va.onrender.com/<slug>-console/` serves
      the admin login; `https://stemquest-api-va.onrender.com/admin/`
      returns 404.
- [x] Verify `instructor@demo.com` absent from prod Neon: read-only
      `SELECT COUNT(*) FROM accounts_user WHERE email='instructor@demo.com'`
      (adjust table name to the actual accounts user table). Expect 0.
      If present: STOP and report — removal is a user decision, not part of
      this phase.

## Frontend tasks

- [x] Add a small `PageLoader` fallback component reusing the existing
      inline Tailwind `animate-spin` pattern (see
      `components/layout/Header.tsx` for the idiom) — full-page centered,
      consistent with existing loading states.
- [x] Convert page-level route imports in `App.tsx` (~31 eager imports) to
      `React.lazy` + one `<Suspense fallback={<PageLoader />}>` around the
      route outlet. Keep contexts, layout components, and `ErrorBoundary`
      eager.
- [x] `npm run build`: the 500 kB chunk warning is gone (or main chunk
      dramatically reduced) and per-page chunks are emitted. Record the
      before/after main-chunk sizes in the handoff.
- [x] Fix the 14 `react-hooks/exhaustive-deps` warnings (missing `loadData`
      / `loadGrades` / `loadSettings` / `loadSections` / `loadRoster` /
      `loadGradebook` / `loadEvents` / `loadCourse` / `loadConfig` /
      `loadAttachments` / `loadAnnouncement` / `course` deps). Standard fix:
      wrap the loader in `useCallback` and add it to the dep array. DANGER:
      adding deps can create refetch loops — after each fix, click through
      the affected page and watch the network tab for repeated calls.
- [x] Fix the 4 `react-refresh/only-export-components` warnings by moving
      shared constants/functions into separate files.
- [x] `npm run lint`: 0 errors / 0 warnings.
- [x] Delete the stray empty `frontend/frontend/` directory tree.

## Docs / planning tasks

- [x] `git mv PLAN.md docs/archive/PLAN.md`; prepend a header note:
      retired at phase 50, roadmap ended at phase 33, specs in
      `docs/specs/` + handoffs in `docs/handoffs/` are the source of truth.
- [x] Update `CLAUDE.md` workflow rules: remove the "Do NOT read all of
      PLAN.md" line / replace with the specs+handoffs rule.
- [x] Update PLAN.md references in `.claude/skills/start-phase/SKILL.md`
      and `.claude/skills/finish-phase/SKILL.md`.

## Verification

- [x] `/verify-stack` passes: pytest all green (425 expected — no backend
      changes), tsc 0 errors, lint **0 errors / 0 warnings** (new baseline).
- [x] `npm run build` output pasted as evidence: no chunk-size warning,
      page chunks listed.
- [ ] Manual flow on the live site after deploy (demo auto-login): navigate
      Dashboard → a course → Learning Mode → Gradebook → Settings. Zero
      console errors; network tab shows lazy chunks loading; no page stuck
      on the PageLoader; no refetch loops on the pages whose hooks changed.
- [ ] Admin: new slug path serves login, `/admin/` 404s (curl output).
- [x] Neon query result for `instructor@demo.com` = 0 rows.
- [x] `grep -rn "PLAN.md" CLAUDE.md .claude/` returns only intentional
      references (archive pointer).
