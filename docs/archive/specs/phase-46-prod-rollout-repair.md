# Phase 46 — Production rollout repair (phases 43–45 stack)

## Goal

PRs #34/#35/#36 merged to main on 2026-07-22 without following the deploy
sequence in PR #34, leaving production half-rolled-out: the phase 43 JWT
backend went live on Render without its `token_blacklist` tables (every
login 500'd), and Render never picked up the phase 44 commit (demo-login
endpoint 404s on the live API — most likely blocked on the required
`DEMO_ACCOUNT_PASSWORD` env var, `sync: false` in render.yaml). This phase
finishes the rollout: get Render onto latest main, rotate the demo
password out of public knowledge, complete the phase 43 R2 lockdown, and
verify the whole login + demo + media flow live. **The most urgent piece
is already done** — during phase scoping (2026-07-22) the `token_blacklist`
migrations were applied to Neon and live email/password login verified
working again (200 with JWT pair).

## Out of scope

- Any login page visual/UX changes — user confirmed "fixed the login UI"
  meant "login failed on the live site", which the rollout fixes. No
  frontend code changes in this phase.
- New features of any kind; this is ops + verification only.
- httpOnly-cookie JWT transport (phase 43 out-of-scope list still stands).
- PLAN.md updates (its table intentionally stops at Phase 33).
- Dropping the orphaned `authtoken_token` table on Neon.

## Ops tasks (no code — runbook + commands)

- [x] Apply `token_blacklist` migrations to Neon
      (`docker compose exec -T -e DATABASE_URL=<neon> backend python
      manage.py migrate` — done during scoping; plan showed only
      token_blacklist 0001–0012, all applied OK; live login now 200).
- [x] Discovered during implementation (2026-07-22): the stack merged in
      the wrong direction — #35 landed on the phase-43 branch and #36 on
      the phase-44 branch, so main only ever got phase 43. Repair PR #37
      (feat/phase-44-demo-auto-login → main) opened with the full 44+45
      content; verify-stack passed on that exact tree (415 backend, tsc
      0 errors, lint 0 errors/22 warnings). Merging it is runbook step 1.
- [x] Write `docs/runbooks/phase-46-rollout-steps.txt` (plain text, per
      user convention) covering the dashboard-only steps below, in order,
      with a "tell Claude when done" checkpoint after each.
- [x] Generate a random demo password (e.g.
      `python -c "import secrets; print(secrets.token_urlsafe(24))"`).
      Show it to the user once for the Render step; it is never committed.
- [x] USER (Render dashboard, from runbook) — done 2026-07-22:
      1. Set `DEMO_ACCOUNT_PASSWORD` = generated secret on the
         stemquest-api service (unblocks the render.yaml blueprint sync).
      2. Delete the now-unused `R2_PUBLIC_HOST` env var.
      3. Confirm a deploy of latest main triggers (manual deploy if not).
- [x] After Render deploy is live: verify the phase 44 code is actually
      deployed — `GET /api/auth/demo-login/` returns 405 JSON. Confirmed
      2026-07-22 (405, content-type application/json).
- [x] Reseed the demo account against Neon to rotate the stored hash —
      done 2026-07-22. Gotcha: the first reseed ran with pre-phase-44
      code (branch was cut from main before repair PR #37) whose seed
      command hardcoded `Admin123!`; rebased onto main, restarted the
      backend container, re-ran — old password now rejected (400).
- [ ] USER (Cloudflare dashboard, from runbook, ONLY after the Render
      deploy is confirmed): R2 bucket → Settings → disable public
      `pub-*.r2.dev` access (phase 43 rollout step 4).

## Backend tasks

None — no backend code changes. (Local stack untouched; Render deploys
existing main.)

## Frontend tasks

None — no frontend code changes. (Cloudflare Workers app already
auto-deployed from main.)

## Verification

All against production, in this order:

- [x] `curl -s "https://stemquest-api.onrender.com/api/health/?deep=1"`
      → `{"status": "ok", "database": "ok"}`. Confirmed 2026-07-22.
- [x] `POST /api/auth/demo-login/` → 200 with `access`/`refresh`/`user`
      for jdoe@demo.com; `GET` on the same URL → 405. Confirmed.
- [x] `POST /api/auth/login/` with jdoe@demo.com / Admin123! → 400
      (old public password no longer works after reseed). Confirmed.
- [x] Bearer access token from demo-login authenticates
      `GET /api/auth/user/` → 200, Jordan Doe. Confirmed.
- [x] Live media URL contains `X-Amz-Signature`/`X-Amz-Expires` and
      serves 200; signature-stripped URL → 400. NOTE: prod has zero
      lesson attachments and zero avatars, so this was exercised by
      uploading a 1px avatar on the demo account via the live API,
      checking the returned URL, then deleting it (bucket back to
      pre-test state).
- [ ] Direct `pub-*.r2.dev` URL errors — pending the Cloudflare flip
      (runbook step 5, user). The pub host hash was never recorded in
      the repo, so the dashboard toggle itself is the confirmation;
      silence-means-done applies after the user reports the flip.
- [ ] Browser click-through on https://stemquest.cesarvillarreal11.workers.dev
      (phase 44 manual items, still unticked): header "Try the demo"
      button and login-card demo button both land on the dashboard
      logged in as Jordan Doe; logout works (JWT blacklist path — this
      exercises the new tables). Silence-means-done applies if the user
      clicks through instead. (API side verified via curl 2026-07-22.)
- [x] Phase 45 leftover: README renders on GitHub main — all 9 screenshot
      paths verified to exist on lms/main; `<details>` block present.
      Visual render check: silence-means-done.
- [x] `/verify-stack` run twice 2026-07-22 (pre-merge tree and rebased
      phase-46 branch): backend 415 passed, tsc 0 errors, lint 0
      errors/22 warnings both times.
- [x] Update this checklist + tick the corresponding unticked rollout
      items in docs/specs/phase-43 and phase-44 specs, then `/handoff`.
