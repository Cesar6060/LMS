# Handoff: Phase 27 — Rebrand to "STEM Quest" (ADR-017)

## Current state
Phase 27 (mechanical rebrand, user-facing copy only) is **implemented, verified, and
up for review as PR #15** (https://github.com/Cesar6060/LMS/pull/15, base
`Cesar6060/LMS:main`, open). The one remaining checklist item is the manual
click-through, which is handed to the user (no browser automation in the agent env).

- **Branch:** `feat/phase-27-rebrand-stem-quest` (tracks `lms/feat/phase-27-rebrand-stem-quest`).
- **Commits ahead of `lms/main`:** `b666268 docs:` (phase 27 spec, pre-existing),
  `6136a33 feat:` (rebrand code + config), plus this `docs:` commit (handoff + spec checklist).
- **Shipped (code/config):**
  - Email templates `base.html` (tab title, masthead `<h1>`, footer) + `course_invitation.html` → "STEM Quest".
  - Frontend `index.html` tab `<title>`, `Header.tsx` wordmark (desktop + mobile `SheetTitle`) → "STEM Quest".
  - Icon swap `Gamepad2` → `Rocket` in `Header.tsx` **and** all four auth pages
    (Login / Register / ForgotPassword / ResetPassword). No `Gamepad2` remains in `src/`.
  - `package.json` name → `stem-quest-frontend`; `README.md` H1 → `# STEM Quest`.
  - Commented `DEFAULT_FROM_EMAIL` display name in `.env.example` + `docker-compose.yml`.
- **Verified:** pytest **196 passed**; tsc **0 errors**; lint **0 errors / 23 warnings**
  (baseline). Grep sweep: no `"GameDev Platform"` / `"GameDev"` in scope; out-of-scope
  `gamedev_db` / `gamedev_user` / `gamedev_platform` infra strings confirmed **present**.
  Backend restarted so email-template changes render.

## In progress / not done
- **PR #15 is open, not yet merged.**
- **Manual click-through unchecked** in the spec — reviewer confirms: tab title, desktop
  wordmark + rocket icon, mobile `SheetTitle`, login-page rocket, invitation-email masthead/footer.

## Next steps
1. User does the click-through; then merge **PR #15** into `lms/main`.
2. Start **Phase 28 — catalog re-scoping (ADR-018)**: the "video game development"
   subject-matter copy in seed/populate commands, tests, `CreateCoursePage.tsx` placeholder,
   and the README tagline was deliberately left for this phase.

## Decisions made
- **Icon = `Rocket`** (spec's recommended option; motivating / "quest" feel, fits the
  ADR-019 gamification direction). Confirmed present in the installed `lucide-react@0.469.0`.
- **Extended the icon swap to the four auth pages** beyond the spec's header-only scope,
  at user request (screenshot showed the gamepad above "Welcome back"). Consistency win,
  no behavior change.
- **Infra left untouched** per ADR-017 — DB creds, Docker/env values, `gamedev_platform`
  module + docstrings are not user-facing and carry migration/env risk.
- Split `feat:` (code/config) from `docs:` (spec checklist + this handoff, needs the PR URL),
  per the repo's separate-`docs:` pattern.

## Gotchas discovered
- No browser automation in the agent env — visual click-throughs are handed to the user; don't fake them.
- `head` is shadowed in this shell (aliased to an HTTP tool) — `ls | head` / `grep | head` fail.
- Backend changes need `docker compose restart backend`; pytest runs via `docker compose exec -T backend pytest`.

## Files to read first
- `docs/specs/phase-27-rebrand-stem-quest.md` (this phase; all items checked except manual click-through).
- `PLAN.md` Part 9, Phase 28 row (catalog re-scoping, ADR-018) — gitignored, on disk.
- `docs/handoffs/2026-07-19-stem-quest-pivot-plan-revision.md` (pivot context).
