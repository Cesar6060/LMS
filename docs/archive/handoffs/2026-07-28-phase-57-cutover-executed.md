# Handoff: Phase 57 cutover executed + Dependabot triage

## Current state

Phase 57: PR #75 merged; the **entire api.stemquests.com cutover is
done** (executed 2026-07-28 via browser automation + user's Cloudflare
SSO): Render ALLOWED_HOSTS extended, custom domain Verified + cert
issued, grey-cloud CNAME live, VITE_API_URL flipped + bundle rebuilt
(`index-Ca9qcx6a.js` targets api.stemquests.com), CF Web Analytics
injection disabled, UptimeRobot monitor `STEM Quest Api
(api.stemquests.com)` UP. All spec verification items checked off in
docs/specs/phase-57-restricted-network-login.md except the final
school-device test. Deep health 200 on both hosts.

Phase 56 carried items closed: demo-reset.yml first run happened via
nightly cron (run 30353105264, success; post-state spot-checked),
browser click-through done (banner, quiz write, settings disabled,
discussions no composer, avatar curl 403 demo_blocked).

Dependabot: merged #61-64, #66, #69, #70, #72 (CI actions, backend
minor/patch group incl. allauth 65.18, dj-database-url 3, tailwind-merge
3, react-markdown 10). Neon migrate-check equivalent: no missing
migrations. `/verify-stack` PASS post-merges: **618 backend tests**,
tsc 0 errors, eslint exit 0 (run in rebuilt Docker backend).

## In progress / not done

- **School-device login test** — user-performed; phase 57's last item.
- **#71 (pytest-cov 7), #73 (gunicorn 26)**: rebase requested after
  requirements.txt conflicts; merge when green. After #73 deploys,
  re-check https://api.stemquests.com/api/health/?deep=1 (gunicorn is
  the prod server; CI doesn't exercise it).
- Held Dependabot PRs: #67 (Django 6 — superseded by phase 58's 4.2→5.2
  plan), #65 (TS 7), #68 (react-dom/React 19) — failing CI, deferred.
- Phase 56 normal-student regression (reply/profile/avatar with a real
  account) — needs real credentials, user-performed.
- Sentry: new TypeError "reading 'LoginPage'" on /login (1 event,
  pre-cutover) — worth a look, unrelated to cutover.

## Next steps

1. User: school-device login on school wifi → closes phase 57.
2. Merge #71/#73 when green (watch prod health after #73).
3. Phase 58: Django 4.2 → 5.2 LTS.

## Decisions made

- Cutover executed via Claude-in-Chrome instead of user-manual; runbook
  order held (ALLOWED_HOSTS before DNS record — no DisallowedHost 400s).
- Merged only green low-risk Dependabot PRs; majors with failing CI held
  because phases 58+ do those upgrades deliberately.
- demo-reset first run: accepted the nightly cron's green run as the
  "first dispatch" instead of a redundant manual workflow_dispatch.

## Gotchas discovered

- Querying api.stemquests.com before the CNAME existed poisoned the dev
  machine's resolver (VPN/router negative cache) for ~30 min — looked
  like a broken cutover; external resolvers (UptimeRobot, 1.1.1.1) were
  fine the whole time. Real users are unaffected.
- Serial Dependabot backend PRs re-conflict on requirements.txt after
  each merge; rebase + merge them one at a time.
- Render "Retry build" on the Cloudflare worker lives on Build history
  rows, not the deployments Version History "…" menu.

## Files to read first

1. docs/specs/phase-57-restricted-network-login.md — one open item.
2. docs/runbooks/phase-57-api-domain-steps.txt — what was executed.
3. docs/specs/phase-56-demo-sandbox-security.md — closed carried items.
