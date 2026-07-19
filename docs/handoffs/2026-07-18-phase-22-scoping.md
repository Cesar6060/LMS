# Handoff: Phase 22 scoping (navigation & button usability)

## Current state

Scoping session only — NO implementation has been done. Branch
`feat/phase-22-navigation-usability` is cut from `lms/main` at `cb8f653`
(the PR #9 / phase-20 merge). Uncommitted on it:

- `docs/specs/phase-22-navigation-usability.md` — the full phase spec,
  ready to implement. **User approved FULL scope (sections A–E, stretch
  items excluded).**
- `docs/specs/phase-21-instructor-analytics-dashboard.md` — analytics
  phase, scoped then DEFERRED by the user (header note inside). Do not
  implement.
- `frontend/index.html` — title "GameDev Platform - Prosper ISD" →
  "GameDev Platform" (user no longer works at Prosper ISD; site is now
  their general classroom platform). Commit this with phase 22.

CLAUDE.md's Prosper mention was also removed (file is gitignored, local
only).

## How the spec was produced

Two parallel audit agents inventoried every entry point, exit, and
friction finding across all student pages and all instructor pages, with
file:line citations. The spec's tasks carry those citations — line numbers
are as of `cb8f653` and should be re-verified when editing.

## In progress / not done

- Nothing half-finished; a briefly started implementation was fully
  reverted. The three shared components in spec section A
  (ConfirmDialog, BackLink, CourseToolsNav) do NOT exist yet.

## Next steps

1. Implement `docs/specs/phase-22-navigation-usability.md`, sections A–E,
   in order (shared components first — later sections depend on them).
2. Check off spec items as they land; run `/verify-stack` before done.
3. Commit the index.html title fix and both spec files with the phase.
4. PR against `main` on `Cesar6060/LMS` (remote `lms`).

## Decisions made

- User's goal reframed: the site is for real classroom use going forward
  (their own students, no school affiliation), so student/instructor
  usability outranks portfolio features.
- Analytics dashboard (old PLAN.md phase 14) deferred, not dropped.
- Phase 22 vocabulary decision: "Continue Learning" always → the player,
  "View Course" always → course detail; one BackLink pattern; instructor
  tools get a shared CourseToolsNav tab bar; native confirm()/alert()
  replaced by a shared styled ConfirmDialog.
- Quiz round trip fixed with a `?from=learn&lesson={id}` URL param, not
  global state.

## Gotchas discovered

- The host shell's `head` is shadowed by a Perl tool — use `sed -n` or
  `/usr/bin/head` (carried over from prior sessions; bit again today).
- PLAN.md's phase table is stale (lists phase 13 discussions as Pending;
  it shipped). Trust `docs/specs/` + handoffs over PLAN.md status marks.
- `aria-sort` belongs on the `<th>`, not the button inside it (came up
  while drafting the roster header rework).

## Files to read first

1. `docs/specs/phase-22-navigation-usability.md` — the whole phase.
2. `frontend/src/components/layout/Header.tsx` — nav-pill styling to
   mirror in CourseToolsNav (`navLinkClass`, line ~38) plus most of
   section B's edit sites.
3. `frontend/src/pages/instructor/StudentRosterPage.tsx:481-506` — the
   styled remove-student Dialog that ConfirmDialog generalizes.
4. `frontend/src/components/ui/Button.tsx` + `ui/Dialog.tsx` — primitives
   the new shared components build on.
