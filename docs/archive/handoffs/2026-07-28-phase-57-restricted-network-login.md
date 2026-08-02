# Handoff: Phase 57 — restricted-network login fix

## Current state

Phase 57 implemented on `feat/phase-57-restricted-network-login`;
**PR #75 open, NOT merged**: https://github.com/Cesar6060/LMS/pull/75

Root cause diagnosed: school/work web filters intercept the generic
`stemquest-api-va.onrender.com` host and return responses without CORS
headers — the backend itself is healthy (preflight + POST verified 200
with correct ACAO from a clean network). Fix = serve the API at
`api.stemquests.com` via a DNS-only CNAME (grey cloud, deliberately —
see Decisions).

Shipped: `CorsMiddleware` moved to top of `MIDDLEWARE`
(backend/config/settings.py) so SSL-redirect 301s carry CORS headers;
3 new tests in backend/config/tests/test_production_settings.py; CSP in
frontend/public/_headers gains `worker-src 'self' blob:` (unblocks the
Sentry Replay worker) + `api.stemquests.com` in connect-src; runbook
docs/runbooks/phase-57-api-domain-steps.txt; docs updated (README,
deployment-overview.md, deployment-tools.txt).

`/verify-stack` PASS: **618 backend tests** (was 615), tsc 0 errors,
eslint clean, coverage 94%. Review pass: code-reviewer findings fixed;
adversarial-tester **0 BROKEN** (2 documented SUSPICIOUS in PR body).

## In progress / not done

- **PR #75 awaiting user merge.** Never merge from a session.
- **The entire dashboard cutover** — every step of
  `docs/runbooks/phase-57-api-domain-steps.txt` (Render ALLOWED_HOSTS +
  custom domain, Cloudflare grey-cloud CNAME, VITE_API_URL build var,
  disable Web Analytics injection, UptimeRobot monitor). Docs already
  describe the post-cutover state; DNS record does not exist yet.
- Spec verification items unchecked: curls against api.stemquests.com,
  browser click-through (incl. phase 56's carried one), Sentry check,
  **final school-device login test** (phase does not close without it).
- Carried: demo-reset.yml first dispatch (56), Dependabot triage (55).

## Next steps

1. User merges PR #75, then executes the runbook top to bottom.
2. Check off the spec's remaining verification items as each passes.
3. School-device login test → closes the phase.
4. Phase 58: Django 4.2 → 5.2 LTS (slipped from 57).

## Decisions made

- **DNS-only, not CF-proxied**: orange-clouding would make Render's edge
  stamp CF-Connecting-IP with Cloudflare egress IPs, collapsing per-IP
  throttles. Origin-lock stays deferred with it.
- Old onrender.com host stays valid indefinitely (fallback).
- CF Web Analytics beacon: disable injection, not CSP-allowlist.
- Preflights now skip security-header middleware (CorsMiddleware
  short-circuits at index 0) — accepted + documented in settings.py.

## Gotchas discovered

- Runbook ordering matters: ALLOWED_HOSTS must be extended BEFORE the
  DNS record exists, else the first health check 400s (DisallowedHost)
  and looks like a broken cutover.
- django-cors-headers matches Origin loosely (trailing slash, uppercase
  scheme) and echoes it verbatim — pre-existing, unreachable from real
  browsers, noted in PR #75.

## Files to read first

1. docs/specs/phase-57-restricted-network-login.md — remaining unchecked
   verification items.
2. docs/runbooks/phase-57-api-domain-steps.txt — the cutover, in order.
3. backend/config/settings.py MIDDLEWARE block — the reorder + comment.
4. frontend/public/_headers — the CSP line.
