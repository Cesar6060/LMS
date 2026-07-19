# Phase 27 — Rebrand to "STEM Quest" (ADR-017)

## Goal
Rename the product from "GameDev Platform" to **STEM Quest** in user-facing
copy only. This is a cheap, mechanical rebrand sequenced early (per the Part 9
phase table) so every later phase builds under the correct name. Scope is the
handful of places the current brand string is shown to a user — page/tab title,
header wordmark, README, npm package name, and the two email templates that
carry brand text. Infrastructure identifiers (DB name, Docker service/env
values, Python module docstrings) are deliberately left untouched — renaming
them is migration/env risk for zero user-facing benefit (ADR-017).

One approved deviation from strict "text/copy only": the header wordmark's
`Gamepad2` game-controller icon is swapped for a neutral, subject-agnostic STEM
icon, because a gamepad reads as off-brand for a platform now spanning Computer
Science **and** Robotics (user decision, 2026-07-19).

## Out of scope (do NOT touch)
- **DB names / credentials:** `gamedev_db`, `gamedev_user` in
  `backend/config/settings.py`, `docker-compose.yml`, `.env`, `.env.example`.
- **Docker service/env values** generally.
- **Python module docstrings / internal project name:** `gamedev_platform` in
  `backend/config/{asgi,wsgi,settings,urls}.py` and the "gamedev platform"
  docstring in `backend/accounts/models.py`.
- **Course subject-matter copy** ("video game development", "game development")
  in seed/populate commands, tests, and the `CreateCoursePage.tsx` placeholder —
  this describes course content, not the product brand. Catalog re-scoping is
  Phase 28 (ADR-018).
- **README descriptive tagline** — only brand strings change this phase; the
  "video game development education" framing is left for Phase 28 (user
  decision, 2026-07-19).
- **`CLAUDE.md`** — already reads "# STEM Quest"; no change needed.
- **Historical docs/handoffs/specs** — planning artifacts, not product copy.
- Any new logo asset, favicon redesign, tagline/subtitle, or visual styling
  beyond the single icon swap (the dedicated redesign is Phase 33 / ADR-021).

## Backend tasks
No models, migrations, or endpoints. Templates only.

- [ ] `backend/templates/emails/base.html:6` — `<title>{% block title %}GameDev Platform{% endblock %}</title>` → `STEM Quest`
- [ ] `backend/templates/emails/base.html:82` — masthead `<h1>GameDev Platform</h1>` → `<h1>STEM Quest</h1>`
- [ ] `backend/templates/emails/base.html:88` — footer `<p>This email was sent from GameDev Platform.</p>` → `...from STEM Quest.`
- [ ] `backend/templates/emails/course_invitation.html:22` — `<li>Go to the GameDev Platform</li>` → `<li>Go to STEM Quest</li>` (drop "the" so it reads naturally)
- [ ] `announcement.html` — verify no brand string exists (it uses dynamic vars only); no change expected.
- [ ] Restart backend after template edits (`docker compose restart backend`) before verifying email render.

## Frontend tasks
- [ ] `frontend/index.html:7` — `<title>GameDev Platform</title>` → `<title>STEM Quest</title>` (browser tab title).
- [ ] `frontend/src/components/layout/Header.tsx` — desktop wordmark (~line 124–126): change the `<span>` text `GameDev` → `STEM Quest`, and replace the paired `Gamepad2` icon with the chosen neutral STEM icon.
- [ ] `frontend/src/components/layout/Header.tsx` — mobile `SheetTitle` (~line 253): same wordmark text `GameDev` → `STEM Quest` and the same icon swap, kept consistent with desktop.
- [ ] Update the `lucide-react` import in `Header.tsx`: remove `Gamepad2` if it's no longer used anywhere else in the file; add the chosen icon.
  - **Icon choice:** recommend `Rocket` (motivating / "quest" feel, fits the ADR-019 gamification direction). Acceptable alternatives: `Compass`, `GraduationCap`, `Sparkles`. Pick ONE and use it in both the desktop and mobile locations. Confirm the name exists in the installed `lucide-react` version before importing.
- [ ] `frontend/package.json:2` — `"name": "gamedev-platform-frontend"` → `"stem-quest-frontend"` (ADR-017 lists this in scope; it's an npm identifier, so keep it lowercase/kebab-case — NOT "STEM Quest").

## Docs / repo tasks
- [ ] `README.md:1` — H1 `# GameDev Learning Platform` → `# STEM Quest`.
- [ ] `README.md` — swap any other literal brand mentions of "GameDev Platform" to "STEM Quest". Leave the "video game development education" tagline and the `gamedev-platform/` directory reference in the ASCII project-tree block as-is (brand-only scope this phase).
- [ ] `.env.example:30` and `docker-compose.yml:56` — the commented `# DEFAULT_FROM_EMAIL=GameDev Platform <noreply@yourdomain.com>` examples: update the display name to `STEM Quest` for consistency (inactive/commented, but it's the user-facing From name if ever enabled). Low priority; include if trivially quick.

## Verification
Run `/verify-stack` and show the output. Expected:
- [ ] **pytest** — 196 passed (baseline; this phase adds no backend logic, only template copy). Email-template rendering tests, if any exist, still pass.
- [ ] **tsc** `npx tsc --noEmit` — 0 errors (icon import must resolve).
- [ ] **lint** `npm run lint` — 0 errors, ~23 warnings (baseline; no new warnings from the changed import).
- [ ] **Grep sweep** — `grep -rn "GameDev Platform" frontend/index.html frontend/src backend/templates README.md frontend/package.json` returns nothing; `grep -rn "GameDev" frontend/src/components/layout/Header.tsx` returns nothing (wordmark fully swapped). The out-of-scope `gamedev_*` infra strings should still be present (confirm they were NOT touched).
- [ ] **Manual click-through (hand to user — no browser automation in agent env):**
  1. Load the app — browser tab title reads **STEM Quest**.
  2. Header wordmark (desktop) reads **STEM Quest** with the new icon, not a gamepad.
  3. Open the mobile menu (narrow viewport / hamburger) — `SheetTitle` reads **STEM Quest** with the same icon.
  4. Trigger/preview a course-invitation email (or render the template) — masthead and footer say **STEM Quest**.
  5. No stray "GameDev" text anywhere in the shell (navbar, tab, footer).

## Notes
- Base branch: `feat/phase-27-rebrand-stem-quest` (cut from `lms/main` @ `a83a3d8`, which includes the merged Phase 26 PR #14).
- Keep commits conventional and split code (`feat:`/`chore:`) from docs (`docs:`) per repo convention. A rebrand is arguably `chore:` (no behavior change) — implementer's call, but be consistent.
- After implementing: `/handoff`, then open a PR into `Cesar6060/LMS:main`.
