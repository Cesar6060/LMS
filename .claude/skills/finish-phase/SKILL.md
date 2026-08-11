---
name: finish-phase
description: Close out a completed phase — verify, adversarial review, update progress docs, push the feature branch, open the PR to main, and write the handoff. Run when the phase checklist is done.
disable-model-invocation: true
argument-hint: [phase-number-or-name]
---

You are finishing phase: $ARGUMENTS

Work through these steps in order. Do not skip ahead — each step gates the next.

1. **Branch check.** Run `git branch --show-current`. You must be on a feature branch, NEVER main — merging to main auto-deploys the backend to Render (`api.stemquests.com` — the pre-phase-57 host is retired, do not health-check it) and rebuilds the frontend on Cloudflare Pages. If you're on main, stop and tell the user; do not create a branch and move commits yourself without asking.

2. **Verify.** Run `/verify-stack`. It must end in PASS. If it fails, fix the root cause and re-run — do not proceed with red checks. (CI additionally runs `npm run build` with `VITE_API_URL` set; if this phase touched vite.config.ts or build-time env handling, run the production build locally too.)

3. **Review pass.** Launch THREE subagents in parallel, all against the full phase diff (`git diff main...HEAD`):
   - the `code-reviewer` agent — reviews the changes against the phase spec in docs/specs/
   - the `adversarial-tester` agent — actively tries to break the new feature (unit-lock bypass, course scoping across instructors, invite gating, demo lockdown, upload verification, inert throttles, IDOR)
   - the `frontend-reviewer` agent — the `api.ts` interceptor contract, `any`, missing vitest coverage, demo/role gating. Skip it only if `git diff main...HEAD --stat -- frontend/` is empty.

   Only ONE of them may run pytest at a time — parallel runs collide on the shared `test_gamedev_db`. Fix anything code-reviewer or frontend-reviewer flags as a correctness gap and anything adversarial-tester reports as BROKEN, then re-run `/verify-stack`. SUSPICIOUS findings may be deferred, but must be listed in the PR body — never silently dropped.

   Review agents leave probe and scratch files behind. Read `git status` before staging anything — never `git add -A` here.

4. **Migration check.** If this phase added or modified files in `backend/*/migrations/`, run the `db-migration-checker` agent on them, then work the **Migrations** section at the bottom of this file before opening the PR. Do not treat "the agent said it's fine" as sufficient — that section is the checklist.

5. **Spec completeness.** Read the phase spec in `docs/specs/` and confirm every checklist item is actually done. Anything not done either gets finished now or explicitly moved to the next phase — call it out, don't silently drop it.

6. **Update progress docs.** Check off the completed items in the phase spec in `docs/specs/`. (PLAN.md was retired at phase 50 — specs + handoffs are the source of truth; there is no roadmap file to update.)

7. **Commit and push.** Commit any remaining changes using conventional commit format (feat:, fix:, chore:) with NO Co-Authored-By lines, then `git push -u origin <branch>`.

8. **Open the PR** against main with `gh pr create`. It must target **`Cesar6060/LMS`** — confirm with `gh repo set-default --view` before running it. (Two earlier phases opened PRs on the retired `dev-learning-platform` repo because no default was set.) The PR body must include:
   - **Summary** — what the phase delivers, one short paragraph
   - **Spec** — path to `docs/specs/phase-<N>-<name>.md`
   - **Verification** — the actual `/verify-stack` results (paste the verdict and key output, not just "tests pass")
   - **Review** — code-reviewer's verdict, adversarial-tester's HELD/BROKEN summary, and any deferred findings
   - **Migrations** — list every new migration file and state plainly whether the running OLD code survives the new schema (see the **Migrations** section below). "None" if no schema changes
   - **Deploy note** — merging auto-deploys the backend via Render and the frontend via Cloudflare Pages; note anything that needs a new env var in the Render or Pages dashboard first

9. **Handoff.** Run `/handoff` so the next session starts clean.

10. **Tell the user** the PR URL and the merge sequence. If the phase has migrations, restate the two lines from the Migrations section that matter: whether old code survives the new schema, and how to verify after deploy.

Never merge the PR yourself — merging deploys to production. That decision is the user's, and they make it in the GitHub UI. This applies doubly in unattended runs: opening the PR is the finish line.

This is now enforced, not just asked for: `Bash(gh pr merge:*)` is in `permissions.deny` in `.claude/settings.json`, and `.claude/hooks/guard-bash.sh` blocks it again even when wrapped in `sh -c`. If you find yourself reaching for it, the answer is to tell the user the PR is ready.

---

## Migrations

Applies whenever the phase touches `backend/*/migrations/`.

`render.yaml` runs `migrate` as a `preDeployCommand` — after the build, before the new
version takes traffic, and a failure aborts the deploy. So never hand-apply before
merging. But it runs **while the old code is still serving**, so every migration must be
old-code-safe:

- New columns nullable, or `db_default=` — never plain `default=`, which backfills and
  then DROPs the database default.
- Nothing dropped in the same deploy as the code that stops using it. Mark it DORMANT,
  drop the column in a later change.
- No `NOT NULL` without a default. NOT NULL → NULL is safe; the reverse is not.
- A callable default needs three operations: bare `AddField` → `RunPython` stamping per
  row → `AlterField` adding unique/default. One `AddField(default=callable)` evaluates it
  **once** and writes the same value to every row.
- New unique constraint: prove the backfill cannot produce a duplicate.
- Reverse migrations leave a working schema.

If a migration cannot pass all of that, split it across two deploys — compatible half
first — and say so in the PR.

**Verify after deploy with two checks, not one:** `/api/health/?deep=1`, AND a real
content read (`POST /api/auth/demo-login/` for a token, then
`GET /api/courses/courses/DEMO101/units/`). Deep health only runs `SELECT 1`, so it cannot
see a missing column.

Note: `.claude/hooks/guard-bash.sh` blocks write-method requests at the production
hosts, so that `POST` will be refused from a session. The GET half runs fine. Ask the
user to run the POST, or drive the check through the browser — do not work around the
hook.
