# Handoff: Phase 38 — API live on Render + Neon

## Current state

**The API is live**: `https://stemquest-api.onrender.com`, Render free tier
(native Python, region **virginia**), talking to Neon Postgres over SSL.
Bootstrapped, verified over HTTPS, and click-through-tested from a local
frontend. PR **#24** open on `Cesar6060/LMS` from
`feat/phase-38-api-live-render-neon`, CI green (backend 2m41s, frontend 40s).
Commits: `2d0ee05` (render.yaml edits), `3fa8701` (region fix), `dfc97e6`
(spec checklist + runbook). **Not merged** — user's call, as in prior phases.

Infrastructure facts (correcting the Phase 37/38 spec's identifier):

- Neon **project `shy-cloud-68280619`** ("LMS"), branch `br-falling-art-avcu47in`,
  db `neondb`, role `neondb_owner`, region **aws-us-east-1**, Postgres 16.
  The spec's `ep-falling-frog-avzgk4ed` is the *compute endpoint hostname*
  under this project, not a project ID.
- Region mismatch found and fixed: `render.yaml` said `oregon`, Neon is
  us-east-1. **Render moved to `virginia`** (one-line change) rather than
  recreating Neon — the ~70 ms/query cross-country tax is gone.
- `render.yaml`: `SECRET_KEY` is now `generateValue: true` (minted in Render's
  vault, never seen by anyone); 6 `sync: false` secrets; header + migration
  comments rewritten (free tier has **no shell** — bootstrap runs from a
  laptop against Neon).

Database state (Neon):

- 31 project migrations across 6 apps applied (70 total with Django/allauth);
  `gamification.0002_seed_badges` → 7 badges.
- Superuser `cesarvillarreal11@gmail.com` (allauth lowercased it), fixed up to
  `first_name='Cesar', last_name='Villarreal', is_instructor=True` — required
  because `populate_java_course` looks the instructor up by that hardcoded name.
- `populate_java_course` run **exactly once** (2026-07-20): JAVA101, 5 units,
  20 lessons. `Cleared existing content: (0, {})` — nothing pre-existing.
  **Do not run again** — it deletes and rebuilds units, cascading away all
  student progress.
- Post-click-through the DB has **2 users** (instructor + the test student).

## Verification evidence

- `/verify-stack` PASS before any deploy work: pytest **354 passed**,
  tsc **0 errors**, lint **0 errors / 22 warnings** (= baseline);
  `makemigrations --check` clean; `render.yaml` parses via js-yaml.
- `GET /api/health/` → 200 `{"status": "ok"}` (0.32s warm).
- `GET /api/health/?deep=1` → 200 `{"status": "ok", "database": "ok"}` —
  Neon wired end-to-end.
- `http://` → **301** → `https://`, no loop. HSTS `max-age=3600;
  includeSubDomains`, `nosniff`, `referrer-policy: same-origin` all present.
- WhiteNoise manifest: `/admin/login/` references
  `/static/admin/css/base.523eb49842a7.css` which serves 200 `text/css`
  21460 bytes.
- `/admin/` login over HTTPS: **user-verified** (proves `CSRF_TRUSTED_ORIGINS`
  + secure cookies).
- Click-through from local Vite → prod API: **user-verified** — instructor
  login, JAVA101 Learning Mode pagination, new student registration +
  enrollment + lesson + quiz with XP/course-map updates, zero CORS errors.
  Avatars/attachments 404 as expected (known, Phase 39).

## Deviations from the spec

- **Bad-`Host` test cannot work from outside**: expected 400 from Django, got
  **403 from Cloudflare** — Render fronts services with Cloudflare, which
  rejects unknown Hosts at the edge before Django sees them. `ALLOWED_HOSTS`
  is evidenced indirectly (real host serves 200s everywhere; a wrong value
  would 400 everything). Drop or rewrite this check in future specs.
- **JWT-login-via-curl not run** — needs the superuser password, which the
  assistant deliberately never has. Covered transitively by the click-through.
- **Cold-start timing skipped** — user's call. No figure recorded; measure
  opportunistically in Phase 39.
- Connection strings from Neon now end `?sslmode=require&channel_binding=require`
  — the extra param is fine with the container's psycopg2 (proven by migrate).

## In progress / not done

- **PR #24 not merged**; the `main`-push CI run and Render's auto-deploy of the
  merged `render.yaml` (region change) haven't happened yet. Note: the live
  service was created from the branch's blueprint at apply time; merging is
  what makes `main` and the dashboard agree.
- **Neon password rotation — now REQUIRED, not hygiene.** Deferred twice, and
  during this session the connection string (password included) was printed
  into the chat transcript at the user's request. Rotate before Phase 39 ships:
  (1) Neon console → Roles → `neondb_owner` → reset; (2) update `DATABASE_URL`
  in Render env (site is down between these two steps); (3) re-check
  `/api/health/?deep=1`.
- **Neon MCP server added but unauthenticated** — registered in project config
  (`claude mcp add`), appears after a Claude Code restart; `/mcp` → neon →
  authenticate. Buys direct SQL + password reset (which `neonctl` lacks —
  that's what blocked the in-session rotation attempt).

## Environment / tooling set up this session

- `neonctl` 2.35.1 (npm global; **symlinked** into `/opt/homebrew/bin` because
  npm's prefix is the version-pinned Cellar path — a Node upgrade breaks it;
  reinstall with `npm i -g neonctl` if "command not found") — OAuth'd.
- Render CLI 2.21.0 (`brew install render-oss/render/render`) — logged in, but
  **no workspace set**: run `render workspace set` interactively before first
  use. Also: the CLI cannot apply blueprints; that stays dashboard-only.
- Deploy runbook (plain text, user preference — not markdown):
  `docs/runbooks/phase-38-deploy-steps.txt`.

## Gotchas discovered

- **`CORS_ALLOWED_ORIGINS` was mis-entered in Render** at blueprint-apply time
  — prod emitted *no* `access-control-allow-origin` while local (same code)
  did. Diagnosis pattern: curl local vs prod with `Origin:` header. Fixed in
  the env editor. **Phase 39 must update this same var** to the Pages URL —
  same formatting traps (scheme, no trailing slash).
- **`docker compose run frontend` gets a stale `node_modules`**: compose mounts
  an *anonymous volume* over `/app/node_modules`, and `run` provisions a fresh
  one from the image, which predates `recharts`/`@dnd-kit/*`. Vite serves 200
  but pages die on unresolved imports. Fix: `sh -c "npm install && npm run dev
  -- --host"`. Also stop the dev `frontend` container first — it holds 5173,
  and the CORS origin pins the port.
- `createsuperuser` email case: allauth normalizes to lowercase on save —
  `Cesarvillarreal11@…` became `cesarvillarreal11@…`.
- Render env-var saves trigger automatic redeploys (~2 min) — expect a brief
  window where old values still serve.
- zsh still shadows `head` (HTML tool) — bit this session again despite the
  Phase 37 warning; use `sed -n '1,Np'` / `tail`.

## Next steps

1. Review + merge **PR #24**; confirm the `main`-push CI run is green and
   Render's auto-deploy stays healthy.
2. **Rotate the Neon password** (see above — transcript exposure makes this
   required, and rotation order matters: Neon first, Render immediately after).
3. Write the Phase 39 spec: Cloudflare Pages (frontend) + R2 (media),
   `_redirects`, `VITE_API_URL` prod guard, django-storages, and the
   `CORS_ALLOWED_ORIGINS`/`FRONTEND_URL` swing from `localhost:5173` to the
   Pages URL. Keys needed: R2 access key ID + secret, account ID,
   `pub-<hash>.r2.dev` host.
4. Custom domain: explicitly deferred (roadmap decision) — revisit when the
   platform goes in front of students; pairs with picking a real email
   provider (Render free tier blocks outbound SMTP).

## Files to read first

- `docs/specs/phase-38-api-live-render-neon.md` — checklist fully annotated
  with what was verified and how
- `docs/runbooks/phase-38-deploy-steps.txt` — the deploy as it was actually run
- `docs/specs/deployment-overview.md` — Phases 39–40 roadmap
- `render.yaml` — now describes the live service
