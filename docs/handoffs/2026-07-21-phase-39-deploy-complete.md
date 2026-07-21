# Handoff: Phase 39 COMPLETE — frontend live on Workers, media on R2

## Current state

**The platform is fully live, end to end.** A student can register,
enroll, and work through JAVA101 entirely in production:

- **Frontend**: `https://stemquest.cesarvillarreal11.workers.dev` —
  Cloudflare **Workers** static assets (NOT Pages; see pivot below),
  git-connected to `Cesar6060/LMS`, builds `main` on push.
- **API**: `https://stemquest-api.onrender.com` (Render free tier,
  virginia) — unchanged from Phase 38, now with `USE_R2=true`.
- **Media**: R2 bucket `stemquest-media`, public host
  `pub-28b0ff93eb7042c1870c82472bbbc771.r2.dev`. Avatar/attachment
  uploads write to R2 and serve from that host — the Phase 38
  ephemeral-disk 404 gap is closed.
- **DB**: Neon, untouched this phase. Deep health stayed green
  throughout: `{"status": "ok", "database": "ok"}`.

PRs **#26** (code) and **#27** (Workers pivot) both merged to `main`.
Final docs (this handoff + last checklist ticks) went up as the PR
this file ships in. The full deploy narrative — including every
misstep, in order — is in `docs/runbooks/phase-39-deploy-steps.txt`
(AS-RUN NOTES section).

## The Pages → Workers pivot (biggest deviation)

The spec said Cloudflare **Pages**; Cloudflare has retired the Pages
git-connect flow for new projects. The frontend deploys as an
**assets-only Worker** instead (`frontend/wrangler.jsonc`, name
`stemquest`, `assets.not_found_handling: "single-page-application"`).
Knock-ons:

- `frontend/public/_redirects` was **removed** — Workers assets
  rejects `/* /index.html 200` as an infinite-loop rule (error
  100324, observed live). `not_found_handling` replaces it; deep-link
  hard refresh verified working.
- Site URL is `*.workers.dev`, not `*.pages.dev`.
- Dashboard settings that matter: build command `npm run build`,
  deploy command `npx wrangler deploy`, path `frontend`, and
  `VITE_API_URL` must be a **build variable** (Settings > Build), not
  a runtime Worker variable — the first failed build was exactly the
  vite guard refusing to build without it (guard working as designed).

## Verification evidence (2026-07-21)

- Site `/` → 200; `/courses` fetched directly → 200 serving
  index.html (SPA fallback).
- CORS: `access-control-allow-origin` present for the workers.dev
  origin AND `http://localhost:5173` (both kept, comma-separated).
- R2 media round-trip, tested via a throwaway API account: avatar
  upload → 200 with `avatar_url` on `pub-28b0ff93….r2.dev` → object
  serves 200 `image/png` → delete → 200 → object 404. Test account
  `r2-check@example.com` (plain student) left in prod; delete via
  `/admin/` or ignore.
- **Full click-through: user-verified** on the live site (register,
  enroll, course map, deep-link hard refresh, avatar, attachment,
  CSV export; console clean).
- `/verify-stack` PASS at completion: pytest 372, tsc 0 errors,
  lint 0 errors / 22 warnings (baseline).

## Gotchas discovered (all also in the runbook AS-RUN NOTES)

- **Workers build vs runtime variables are separate stores.** Vite
  needs build variables; the creation form's variable fields land in
  the wrong one.
- **`R2_ACCOUNT_ID` trap**: the R2 API-token page shows a token-ID
  hash that looks exactly like an account ID. Pasting it produces
  `SSLV3_ALERT_HANDSHAKE_FAILURE` from
  `<wrong-id>.r2.cloudflarestorage.com` — a bogus subdomain fails TLS
  entirely rather than 403ing. The real account ID is in dashboard
  URLs (`c47a5512…`). Diagnosis pattern: curl both hostnames; wrong
  ID → curl exit 35/000, right ID → HTTP 400.
- **CORS formatting trap hit again** (third phase running): first
  paste of the workers.dev origin matched nothing — after the fix the
  value holds prod + localhost comma-separated, no spaces, no
  trailing slash.
- R2-served Content-Type mirrors whatever the *uploading* client
  sent: browser uploads → `image/png`; bare `curl -F` →
  `application/octet-stream`. Not a bug.
- (From the code session, still true: host `frontend/node_modules`
  needs `npm install --no-save @rollup/rollup-darwin-arm64` after a
  linux-generated lockfile install, and the directory itself is a
  Docker mount point that can't be `rm -rf`'d.)

## In progress / not done

- **Cold-start timing figure**: still unrecorded (deferred twice
  now). Grab it opportunistically: time the first API request after
  ~15 min idle.
- `PHASE-39-USER-ACTIONS.txt` (repo root, untracked) is fully done —
  Cesar can delete it.
- Phase 38's leftover: local dev frontend container still has the
  stale pre-recharts `node_modules` volume.

## Next steps

1. **Phase 40: observability** — Sentry wiring exists backend-side
   (`SENTRY_DSN` unset); decide frontend Sentry (`VITE_SENTRY_DSN`)
   here. Also a good home for the cold-start measurement and uptime
   monitoring of `/api/health/`.
2. Custom domain + real email provider: still deferred, still paired
   (revisit when the platform goes in front of students).
3. Optional cleanup: delete `r2-check@example.com` from `/admin/`;
   consider code-splitting the 1.29 MB JS bundle (Vite warns).

## Files to read first

- `docs/runbooks/phase-39-deploy-steps.txt` — the deploy as actually
  run, with AS-RUN NOTES
- `docs/specs/phase-39-frontend-pages-media-r2.md` — checklist fully
  ticked except cold-start; pivot annotations inline
- `frontend/wrangler.jsonc` — the Workers config, comments explain
  the pivot
