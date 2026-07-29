# Phase 57 — Restricted-network login fix (API custom domain + CSP hygiene)

## Goal

Login from the user's school/workplace network fails: the network filter
intercepts requests to `stemquest-api-va.onrender.com` (a generic
`onrender.com` hosting host) and returns a response with no CORS headers,
so the browser reports `demo-login` as a CORS failure while
`stemquests.com` itself loads fine. Fix by serving the API at
**`api.stemquests.com`** via a **DNS-only** (grey-cloud) CNAME to Render —
filters then see only the already-allowed `stemquests.com` domain, and the
traffic path through Render's edge is unchanged, so `CF-Connecting-IP`
throttle keying keeps working exactly as today. While in the area, clean
up the two real CSP defects the same screenshot exposed: no `worker-src`
(blocks Sentry Session Replay's blob compression worker on every page
load) and the Cloudflare Web Analytics beacon auto-injection (dashboard
toggle; we're disabling it — Sentry already covers frontend telemetry).
Also harden CORS-on-redirect: `CorsMiddleware` currently sits below
`SecurityMiddleware`, so `SECURE_SSL_REDIRECT` 301s carry no CORS headers.

Diagnosis evidence (2026-07-28): from an unfiltered network, preflight
`OPTIONS /api/auth/demo-login/` with `Origin: https://stemquests.com`
returns `access-control-allow-origin: https://stemquests.com` and the
POST returns 200 in ~150 ms. Backend CORS config is correct; the failure
is interception on the school network.

Phase 55's slot plan shifts: Django 4.2 → 5.2 moves to phase 58.

## Decisions

- **DNS-only, not Cloudflare-proxied.** Orange-clouding `api` would put a
  second Cloudflare hop in front of Render's own Cloudflare edge; Render's
  edge would then stamp `CF-Connecting-IP` with *Cloudflare egress IPs*,
  collapsing every per-IP throttle onto a handful of shared IPs. The
  origin-lock idea from the phase 56 handoff stays deferred with it.
- **Old host stays valid indefinitely.** `stemquest-api-va.onrender.com`
  remains in `ALLOWED_HOSTS` and the CSP `connect-src` as a fallback; only
  `VITE_API_URL` cuts over.
- **Cloudflare Web Analytics injection disabled** rather than allowlisted
  in CSP.

## Out of scope

- Cloudflare-proxied API subdomain / origin-lock between Cloudflare and
  Render (deferred again, deliberately — see Decisions)
- Same-origin `/api` proxy inside the stemquests.com Worker
- Django 4.2 → 5.2 upgrade (now phase 58), react-router 8 / React 19
- Allowlisting `static.cloudflareinsights.com` in CSP
- Retiring the `onrender.com` host or the workers.dev fallback URL
- Dependabot triage; first `demo-reset.yml` dispatch (both still carried
  from phases 55/56)
- Any change to demo-sandbox policy, throttling rates, or CORS origins

## Backend tasks

- [x] Move `corsheaders.middleware.CorsMiddleware` to the top of
      `MIDDLEWARE` in `backend/config/settings.py` (above
      `SecurityMiddleware`), so responses generated before the view —
      notably `SECURE_SSL_REDIRECT` 301s — still get CORS headers.
      `WhiteNoiseMiddleware` must remain immediately after
      `SecurityMiddleware` (existing test pins that).
- [x] Add a test in `backend/config/tests/test_production_settings.py`
      asserting `CorsMiddleware` precedes `SecurityMiddleware` (same
      pattern as `test_whitenoise_middleware_follows_security_middleware`).
- [x] No code change for hosts: `ALLOWED_HOSTS` is env-driven
      (`settings.py:24`); the new hostname is appended on the Render
      dashboard (runbook step).

## Frontend tasks

- [x] [P] `frontend/public/_headers` CSP changes (one line):
      - add `worker-src 'self' blob:` (unblocks the Sentry Replay
        compression worker — `replayIntegration()` in `src/main.tsx`)
      - add `https://api.stemquests.com` to `connect-src`, keeping
        `https://stemquest-api-va.onrender.com` for fallback/transition
- [x] No TS/service changes: API base URL is the build-time
      `VITE_API_URL` (`src/services/api.ts:6`), set in the Cloudflare
      Workers Build variables (runbook step).

## Infra / runbook tasks

- [x] [P] Write `docs/runbooks/phase-57-api-domain-steps.txt` (plain
      text) covering, in order:
      1. Render dashboard → service `srv-d9go1em1a83c73f50r2g` → Custom
         Domains → add `api.stemquests.com`; note the verification target.
      2. Cloudflare dashboard → stemquests.com zone → DNS → CNAME `api` →
         `stemquest-api-va.onrender.com`, **proxy status DNS-only (grey
         cloud)**. Wait for Render to issue the certificate.
      3. Render env: append `,api.stemquests.com` to `ALLOWED_HOSTS`
         (comma list, no spaces); service restarts on save.
      4. Cloudflare Worker `stemquest` → Builds → variable
         `VITE_API_URL=https://api.stemquests.com/api`; trigger a
         frontend redeploy (picks up the `_headers` change too).
      5. Cloudflare → stemquests.com zone → Analytics → Web Analytics →
         disable automatic script injection.
      6. UptimeRobot: add a monitor for
         `https://api.stemquests.com/api/health/`; keep the existing
         `-va.onrender.com` monitor.
- [x] [P] Docs touch-ups after cutover: API URL in `README.md`,
      `docs/specs/deployment-overview.md` (its "no custom domain" line is
      already flagged stale).

## Verification

- [x] `/verify-stack` PASS (backend pytest incl. new middleware-order
      test, `tsc --noEmit` 0 errors, eslint 0 errors)
- [x] `curl -i -X OPTIONS https://api.stemquests.com/api/auth/demo-login/
      -H 'Origin: https://stemquests.com' -H 'Access-Control-Request-Method:
      POST'` → 200 with `access-control-allow-origin: https://stemquests.com`
      (passed 2026-07-28, post-cutover)
- [x] `curl -X POST https://api.stemquests.com/api/auth/demo-login/` →
      200; same POST against the old
      `stemquest-api-va.onrender.com` host still → 200 (fallback intact)
      (passed 2026-07-28: new host 200 + ACAO, old host 200)
- [x] `curl -D - https://stemquests.com/` → CSP header contains
      `worker-src 'self' blob:` and both API hosts in `connect-src`
      (passed 2026-07-28)
- [x] Browser click-through on https://stemquests.com (clean network):
      DevTools console shows **zero** CSP violations on the login page;
      demo login succeeds; Network tab shows calls hitting
      `api.stemquests.com`. While there, complete phase 56's outstanding
      click-through: demo banner visible, one blocked write shows the
      friendly toast, Settings controls disabled.
      (Done 2026-07-28 post-cutover: demo login succeeds, console clean
      across login → dashboard → settings → course → quiz → discussions;
      the deployed bundle contains only `api.stemquests.com` as API host,
      so all calls hit the new domain. Demo banner visible; Settings
      fields disabled with "The demo account can't be edited."; blocked
      write proven via avatar-upload curl → 403 `demo_blocked`. Note:
      the tester machine had cached the pre-record NXDOMAIN and needed
      ~30 min for the negative-cache TTL to expire — irrelevant to real
      users, who never resolved the name before it existed.)
- [x] Sentry `stemquest-react`: today's (2026-07-28) failed-login /
      network-error events are visible; after the cutover, no new
      CORS-failure events for `demo-login`.
      (Verified 2026-07-28: AxiosError "Network Error" issue on /login
      shows today's pre-cutover school-network events; the only
      post-cutover event was the tester machine's stale-DNS attempt. No
      CORS-failure events after the cutover.)
- [ ] **Final, user-performed:** log in from the school device on the
      school network and confirm success. This item stays open until
      done; the phase does not close without it.
