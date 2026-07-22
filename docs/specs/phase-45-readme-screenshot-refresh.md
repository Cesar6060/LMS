# Phase 45 — README screenshot refresh

## Goal

Replace the README's stale screenshot set with the nine new curated
screenshots already sitting in the working tree (`docs/screenshots/`,
7 old files deleted, 9 new `Instructor-*`/`Student-*` files added,
uncommitted). The README currently references all seven deleted files, so
every image on the GitHub landing page is broken. Update the hero image,
the Student Experience section, and the collapsible instructor section to
use the new set with short factual captions. Docs-only phase — keep it
lean: no new prose sections, no README restructure beyond the
screenshot-touching lines.

## Out of scope

- Any frontend or backend code changes.
- Retaking, editing, or renaming screenshots — the nine files are final
  as provided by the user.
- Updating historical docs that mention old filenames
  (`docs/specs/phase-41-portfolio-polish.md`, old handoffs) — they are
  records, leave them.
- Prod rollout of PRs #34/#35 (Render env var, reseed, live verify) —
  separate close-out per the phase 44 handoff.
- Rewriting README prose (Features, Try it, Production Architecture)
  except where a caption or image line is replaced.

## Branching

Branch `feat/phase-45-readme-screenshots` off
`feat/phase-44-demo-auto-login` (third PR in the stack — PR #35's README
edits would conflict with a branch off main). Open the PR with base
`feat/phase-44-demo-auto-login`; GitHub retargets as the stack merges.

## Backend tasks

None.

## Frontend tasks

None.

## Docs tasks

- [x] Create branch `feat/phase-45-readme-screenshots` off
      `feat/phase-44-demo-auto-login`.
- [x] Commit the screenshot rework: stage `docs/screenshots/` (7 deletions
      + 9 additions) — this is the user's curated set, commit as-is.
- [x] **Before writing any caption, Read each new PNG** so captions state
      what the image actually shows. One line each, factual, no marketing.
- [x] Hero image (README ~line 26): `Dashboard.png` →
      `Student-Dashboard.png`.
- [x] Student Experience section: replace the two old images
      (`Student_Courses.png`, `Student_Learning_Mode.png`) with the three
      new student shots: `Student-Dashboard.png` is the hero, so use
      `Student-Course-Roadmap.png` and `Student-Assessments.png` here.
      Adjust captions to match content.
- [x] Instructor `<details>` block: keep the collapse and its summary
      line. Replace the four old images with the six new instructor
      shots in a sensible order (suggested: Dashboard → Course Overview →
      Assessment Management → Gradebook → Course Roster → Analytics).
      Update the per-image `###` headings and captions to match.
- [x] Grep the repo for the seven old filenames — no live references may
      remain outside `docs/specs/` and `docs/handoffs/` (historical).
- [x] Open PR (base `feat/phase-44-demo-auto-login`), conventional
      commit format, no Co-Authored-By.

## Verification

- Every `docs/screenshots/*.png` path referenced in README.md resolves to
  an existing file:
  `grep -o 'docs/screenshots/[^)]*' README.md | while read f; do [ -f "$f" ] || echo "MISSING $f"; done`
  → no output.
- `git status` clean for `docs/screenshots/` after the commit (no
  stray deletions/additions left unstaged).
- `/verify-stack` still passes (no code touched: backend 415 passed, tsc
  0 errors, lint 0 errors / 22 warnings baseline).
- Manual: open the PR branch's README on GitHub — all images render, the
  instructor `<details>` block expands, captions match the images.
  (Silence-means-done convention applies.)
