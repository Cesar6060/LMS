# Handoff: Phase 47 close-out + Cloudflare throttle hotfix

## Current state
Phase 47 (prod email via Gmail SMTP) is FULLY CLOSED — all spec boxes
checked with evidence (docs/specs/phase-47-prod-email-smtp.md). Live
reset email round trip works: branded email delivered from/to
cesarvillarreal11@gmail.com, link opens the frontend /reset-password.
Rollout surfaced two platform bugs, both fixed this session:
1. Render FREE tier blocks ALL outbound SMTP ports (25/465/587) —
   service upgraded to Starter (paid) to unblock; that alone made SMTP
   reachable.
2. NO prod rate limit had ever fired (anon since phase 42, demo_login
   since 44, password_reset in 47): DRF keys anon throttle buckets on
   the full X-Forwarded-For chain, and Cloudflare (fronting
   *.onrender.com) rotates an edge IP in that chain → fresh bucket per
   request. Hotfix PR #40 (merged): backend/core/throttling.py
   ClientIPIdentMixin keys on CF-Connecting-IP, fallback to DRF default;
   swapped into settings DEFAULT_THROTTLE_CLASSES + both
   ScopedRateThrottle sites in accounts/views.py; regression test added.
Verified: pytest 425 passed, tsc 0 errors, lint 0 errors/22 warnings
(baseline). Live: 30-burst → 429s from request 4; Render logs clean.

## In progress / not done
- USER click-through remains for the reset form itself (set new
  password + login on the live site) — silence convention applies.
- This close-out commit (spec checkboxes + this handoff) needs its
  docs-only PR merged.

## Next steps
1. Merge the docs close-out PR (docs-only, deploy no-op).
2. PHASE 48 CANDIDATE — repair or retire the render.yaml Blueprint:
   env-var sync from render.yaml has been silently broken since ~the
   repo migration (values like EMAIL_*, THROTTLE_* never applied; had
   to be entered in the dashboard by hand). Either reconnect the
   Blueprint to Cesar6060/LMS or delete render.yaml's env claims and
   document the dashboard as the single source of truth. Also confirm
   the dashboard startCommand matches render.yaml (--workers 2).
3. Optional: verify THROTTLE_DEMO_LOGIN live (10/min on
   /api/auth/demo-login/) — same mechanism as the verified scopes.

## Decisions made
- Upgraded Render to Starter instead of switching to an email API:
  zero code change, Gmail SMTP works as built; user accepted ~$7/mo.
- Throttle ident prefers CF-Connecting-IP (authoritative behind
  Cloudflare, spoof-proof there) over NUM_PROXIES tuning: chain length
  through CF+Render is unverified, header approach needs no guess and
  degrades to stock DRF behavior when absent (local/tests unchanged).
- Dashboard env vars are currently the source of truth for prod
  (EMAIL_BACKEND, EMAIL_HOST, THROTTLE_ANON, THROTTLE_DEMO_LOGIN,
  THROTTLE_PASSWORD_RESET all hand-entered) — render.yaml lies.

## Gotchas discovered
- Render free tier: outbound 25/465/587 blocked entirely → OSError
  "Network is unreachable"; NOT a Gmail/credential issue.
- A stale dashboard EMAIL_BACKEND=console (phase-15b era) silently
  overrode render.yaml's smtp value — dashboard always wins.
- Gmail app password pasted with spaces → SMTP 535 BadCredentials.
- Per-worker LocMemCache throttle counters: live 429 needs a burst
  bigger than rate × workers; deploys/restarts reset counters.
- render CLI: set workspace tea-d9f74ndaeets73cj34d0; deploys list +
  logs work; ssh/blueprints/API-key reads are permission-blocked.

## Files to read first
- docs/specs/phase-47-prod-email-smtp.md — all boxes + evidence notes
- backend/core/throttling.py — the Cloudflare ident fix + rationale
- render.yaml — env claims that do NOT sync (phase 48 target)
- docs/handoffs/2026-07-22-phase-47-prod-email-smtp.md — build session
