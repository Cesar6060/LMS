# Handoff: Stale Vite fix + phase 22 wrap-up

## Current state

Phase 22 (navigation & button usability) is **merged** — PR #10 landed on
`lms/main` (`f8afa2a`). This session diagnosed why the user's screenshot
still showed the old Manage UI: the Docker Vite dev server never saw host
file changes (macOS bind-mount events don't propagate), so it served
stale compiled code. The fixes existed in git the whole time.

- Modified `frontend/vite.config.ts`: `server.watch.usePolling: true`
  (interval 300ms). Verified live: a host edit reaches the
  container-served output in ~1s without a restart.
- PR #10 was merged before the last two branch commits, so they were
  cherry-picked onto `chore/vite-watch-polling` (cut from `lms/main`)
  and opened as **PR #11**
  (https://github.com/Cesar6060/LMS/pull/11) — vite polling fix +
  handoff gotcha note. Unmerged.
- `/verify-stack`: pytest 192 passed, tsc 0 errors, lint 0 errors
  (24 pre-existing `exhaustive-deps` warnings).
- Phase 22 spec addendum updated with post-merge status.

## In progress / not done

- `feat/phase-22-navigation-usability` branch (local + `lms` remote)
  still exists — deletion was permission-blocked. Safe to delete; its
  two unmerged commits are carried in PR #11.
- Phase 22 spec Verification: the two manual click-throughs and the
  mobile spot-check remain unchecked — and earlier screenshot rounds
  may have judged stale UI, so re-review with a hard refresh.

## Next steps

1. Merge PR #11 (docs + one-file vite config change; verify already run).
2. Delete `feat/phase-22-navigation-usability` and, after merge,
   `chore/vite-watch-polling` (local and `lms` remote).
3. Hard-refresh localhost:5173 and run the spec's manual click-through +
   mobile spot-check against the now-current build; check them off.
4. Pick next phase: phase 21 analytics (spec exists, deferred) or
   phase 22 stretch items. Scope with the user first.

## Decisions made

- Fixed the stale-serving root cause with Vite watch polling rather than
  documenting "restart after changes" — restarts don't help HMR, and
  stale UI already caused a false "fixes weren't done" report.
- Carried the two orphaned commits via cherry-pick onto a fresh branch
  from `lms/main` (not re-PRing the old branch) so history stays linear
  after the squash-free merge.

## Gotchas discovered

- Vite-in-Docker serves stale transforms silently when file events are
  lost; if UI contradicts committed code, suspect the dev server/tab
  before the code. `//` comments are stripped by esbuild — test watch
  propagation with a real export, not a comment.
- Merging a PR while follow-up commits are being pushed can orphan them
  on the branch; check `git merge-base --is-ancestor <sha> lms/main`.

## Files to read first

1. `docs/specs/phase-22-navigation-usability.md` — checklist + addendum.
2. `frontend/vite.config.ts` — the polling fix.
3. `docs/handoffs/2026-07-19-phase-22-implementation.md` — full phase 22
   context.
4. `docs/specs/phase-21-instructor-analytics-dashboard.md` — likely next.
