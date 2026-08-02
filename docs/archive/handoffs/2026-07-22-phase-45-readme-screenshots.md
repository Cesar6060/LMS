# Handoff: Phase 45 — README screenshot refresh

## Current state
Phase 45 DONE on branch `feat/phase-45-readme-screenshots`, PR
https://github.com/Cesar6060/LMS/pull/36 — **third PR in the stack**
(base = `feat/phase-44-demo-auto-login` / PR #35, which sits on PR #34;
GitHub retargets as the stack merges). Two commits: (1) the user's
curated screenshot set committed as-is — 7 old files deleted, 9 new
`Instructor-*`/`Student-*` PNGs added under `docs/screenshots/`;
(2) README.md rewired — hero → `Student-Dashboard.png`, Student
Experience → `Student-Course-Roadmap.png` + `Student-Assessments.png`,
instructor `<details>` block → all six instructor shots (Dashboard →
Course Overview → Assessment Management → Gradebook → Course Roster →
Analytics) with factual one-line captions written after reading each
PNG. Spec checklist fully ticked. verify-stack PASS: backend 415
passed, tsc 0 errors, lint 0 errors / 22 warnings (baseline). Spec's
grep checks pass: all README screenshot paths resolve; no live old-name
references outside docs/specs/ + docs/handoffs/.

## In progress / not done
- Manual GitHub render check of the PR branch README (images render,
  details block expands) — silence-means-done convention applies.
- Prod rollout of the stack (Render `DEMO_ACCOUNT_PASSWORD`, reseed,
  live verify) — belongs to PRs #34/#35 close-out, not this phase.

## Next steps
1. Merge PR #34 (phase 43) per its deploy sequence, then #35 (phase 44,
   sets Render env var first), then #36 retargets to main and merges
   clean — docs-only, no deploy steps of its own.
2. After the stack lands: phase 44 handoff's post-deploy steps
   (seed_demo_account against Neon, live demo-login verify).

## Decisions made
- Screenshots committed exactly as provided (spec: user-curated, final).
- Captions written from the actual image contents, not the old caption
  text — e.g. old "Grading Interface" had no direct replacement; the
  six new instructor shots got their own `###` headings per the spec's
  suggested order.
- PLAN.md not touched — its phase table intentionally stops at Phase 33;
  phases 34+ are tracked spec-by-spec in docs/specs/.

## Gotchas discovered
- `head` is shadowed by a perl URL tool in this zsh env — use
  `sed -n '1,Np'` instead.
- Grepping for old names like `Dashboard.png` false-positives on new
  names (`Instructor-Dashboard.png` contains it) — anchor the grep to
  `screenshots/<exact-name>` or a non-hyphen boundary.
- `pytest` isn't on the host PATH — run it via
  `docker compose exec -T backend pytest`.

## Files to read first
- docs/specs/phase-45-readme-screenshot-refresh.md — spec, all ticked
- README.md — the rewired screenshot sections
- docs/handoffs/2026-07-22-phase-44-demo-auto-login.md — stack + rollout
- PR #36 body — verification evidence and stack notes
