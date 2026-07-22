---
name: finish-phase
description: Close out a completed phase — verify everything, update progress docs, push the feature branch, open the PR to main, and write the handoff. Run when the phase checklist is done.
disable-model-invocation: true
argument-hint: [phase-number-or-name]
---

You are finishing phase: $ARGUMENTS

Work through these steps in order. Do not skip ahead — each step gates the next.

1. **Branch check.** Run `git branch --show-current`. You must be on a feature branch, NEVER main — merging to main auto-deploys the backend to Render (stemquest-api.onrender.com) and rebuilds the frontend on Cloudflare Pages. If you're on main, stop and tell the user; do not create a branch and move commits yourself without asking.

2. **Verify.** Run `/verify-stack`. It must end in PASS. If it fails, fix the root cause and re-run — do not proceed to a PR with red checks. (CI additionally runs `npm run build` with `VITE_API_URL` set; if this phase touched vite.config.ts or build-time env handling, run the production build locally too.)

3. **Migration check.** If this phase added or modified files in `backend/*/migrations/`, run the `db-migration-checker` agent on them. Migrations are NOT applied automatically on deploy — Render's free tier has no shell and no preDeployCommand. They must be run manually against Neon from a dev machine (see docs/specs/phase-38-api-live-render-neon.md). List every new migration so the user knows exactly what needs applying.

4. **Spec completeness.** Read the phase spec in `docs/specs/` and confirm every checklist item is actually done. Anything not done either gets finished now or explicitly moved to the next phase — call it out, don't silently drop it.

5. **Update progress docs.** Check off the completed items in the phase spec and the corresponding phase section of PLAN.md (only that section — do not read the whole file).

6. **Commit and push.** Commit any remaining changes using conventional commit format (feat:, fix:, chore:) with NO Co-Authored-By lines, then `git push -u origin <branch>`.

7. **Open the PR** against main with `gh pr create`. The PR body must include:
   - **Summary** — what the phase delivers, one short paragraph
   - **Spec** — path to `docs/specs/phase-<N>-<name>.md`
   - **Verification** — the actual `/verify-stack` results (paste the verdict and key output, not just "tests pass")
   - **Migrations** — list any new migration files and state plainly that they must be applied to Neon manually (`DATABASE_URL=<neon> python manage.py migrate` from a dev machine) — or "None" if no schema changes
   - **Deploy note** — merging auto-deploys the backend via Render and the frontend via Cloudflare Pages; note anything that needs a new env var in the Render or Pages dashboard first

8. **Handoff.** Run `/handoff` so the next session starts clean.

9. **Tell the user** the PR URL and the merge sequence. If there are new migrations, the order matters: apply them to Neon BEFORE merging (db-migration-checker should have confirmed they're additive-safe, so old code runs fine against the new schema — the reverse is not true). Then merge, let CI/Render/Pages do their thing, and check https://stemquest-api.onrender.com/api/health/?deep=1 after deploy.

Never merge the PR yourself — merging deploys to production. That decision is the user's.
