# Handoff: STEM Quest pivot — PLAN.md revision

## Current state
Planning/docs session (no code phase). Revised the top-level plan to reflect a
direction change, driven by user Q&A this session:
- `PLAN.md` — retitled "STEM Quest — Platform Plan v3"; rewrote top matter (dropped
  Prosper ISD / video-game-only framing; noted assignments removed permanently);
  appended **Part 9: STEM Quest Pivot** with ADR-017–021 and a Phase 26–33 sequence;
  bumped footer to v4.0.
- `CLAUDE.md` — title → "STEM Quest"; description → "Computer Science (incl. video
  game development) and Robotics."
- ⚠️ Both `PLAN.md` and `CLAUDE.md` are **gitignored** (.gitignore lines 2–3) — edits
  are saved to disk but will never appear in `git status`/commits. This is by design.

No code changed. No pytest/tsc/lint run (docs-only). Phase 25 code from prior session
is still uncommitted (see below).

## In progress / not done
- Phase 25 UI work (Header.tsx, ManageCoursePage.tsx, QuizEditorPage.tsx) still
  **modified + uncommitted** on branch `feat/phase-24-management-editor-ui-polish`.
  Untracked: `docs/handoffs/2026-07-19-phase-25-ui-cleanup.md`,
  `docs/specs/phase-25-course-management-ui-cleanup.md`. This is now Phase 26's job.
- No per-phase specs written yet for Phases 26–33 (written just-in-time per workflow).

## Next steps
1. **Phase 26 (close-out):** commit verified Phase 25 changes (margin consistency +
   "Teach" dropdown removal), do the deferred manual instructor click-through, and
   resolve the branch-name mismatch (branch says phase-24, content is phase-25).
   Details in `docs/specs/phase-25-course-management-ui-cleanup.md` (Verification section).
2. **Phase 27 (rebrand):** write spec, then execute ADR-017 — swap "GameDev" → "STEM
   Quest" in user-facing files only (`frontend/index.html`, `Header.tsx` x2 wordmark,
   `README.md`, `frontend/package.json` name, `backend/templates/emails/*.html`). Do
   NOT rename `gamedev_db`/`gamedev_user`, Docker envs, or Python docstrings.
3. Then Phases 28 (catalog: CS + Robotics) → 29 (authoring efficiency, top priority) →
   30 (gamification stage 1) → 31 (analytics) → 32 (Duolingo-style) → 33 (redesign).

## Decisions made
- Kept Phases 1–25 in PLAN.md unedited — historical record, already caveated as stale.
  New direction lives in Part 9 only, avoids a 1900-line rewrite.
- Rebrand scoped to cosmetic/user-facing text only — renaming DB/Docker/docstrings is
  infra churn + migration risk for zero user benefit (ADR-017).
- Assignments stay permanently removed (ADR-020, confirmed by user); game dev folds into
  CS as a track, not a separate subject (ADR-018); gamification staged lightweight-first
  (ADR-019); full visual redesign deliberately sequenced last (ADR-021).

## Gotchas discovered
- `head` is aliased to an HTTP tool in this shell — `head -3 file` and `| head` fail.
  Use `sed -n`/Read instead. (Recurring across sessions.)
- `PLAN.md` + `CLAUDE.md` are gitignored — don't expect them in diffs/PRs.
- PLAN.md already had Parts 7 (Docker) and 8 (Principles), so the new section is
  **Part 9**, not Part 7 — watch cross-references if editing further.

## Files to read first
- `PLAN.md` Part 9 (lines ~1912+) — the whole new direction.
- `docs/specs/phase-25-course-management-ui-cleanup.md` — the immediate next work.
- `docs/handoffs/2026-07-19-phase-25-ui-cleanup.md` — prior session's uncommitted state.
- `.claude/plans/lucky-sniffing-spindle.md` — the approved plan behind this revision.
