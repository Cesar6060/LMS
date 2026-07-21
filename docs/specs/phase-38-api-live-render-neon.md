# Phase 38 — API live on Render + Neon

## Goal

Take the production-ready backend built in Phase 37 and actually run it: a live
Django API on Render (free tier, native Python runtime) talking to a live Neon
Postgres over SSL, reachable over HTTPS at `https://<service>.onrender.com`.
The database is bootstrapped **from this laptop** — Render's free tier has no
shell — with `migrate`, one real superuser/instructor, and `populate_java_course`
for JAVA101. Verification goes past `curl`: the local Vite dev server is pointed
at the live API and a real login + JAVA101 browse is clicked through, which also
de-risks Phase 39's CORS work. The only repo changes are three small edits to
`render.yaml`; everything else is dashboard configuration and one-off commands.

## Interview decisions (2026-07-20)

1. **No Render shell exists on the free tier.** Confirmed in Render's docs:
   free web services get neither the dashboard Shell tab nor SSH, and
   `preDeployCommand` is likewise paid-only. The Phase 37 plan ("run migrate +
   createsuperuser + populate_java_course by hand in the Render shell") is
   therefore **void**. All bootstrap commands run locally against Neon, which
   is publicly reachable over SSL. `render.yaml` still runs **no** `migrate`.
2. **Instructor bootstrap is a manual `manage.py shell` fix-up**, not new code.
   `createsuperuser` cannot set `first_name`/`last_name` (the User model has
   `REQUIRED_FIELDS = []`) and never sets `is_instructor`, but
   `populate_java_course` looks the instructor up by hardcoded
   `first_name='Cesar', last_name='Villarreal'`. A three-line shell one-liner
   closes the gap. Keeps Phase 38 config-only; the fragility is accepted and
   recorded below.
3. **Local frontend against the prod API.** `CORS_ALLOWED_ORIGINS` /
   `FRONTEND_URL` point at `http://localhost:5173` so the click-through is real
   rather than `curl`-only.
4. **`render.yaml` gets three edits**: `SECRET_KEY` becomes
   `generateValue: true` (the key never touches clipboard or chat), the
   "NOT LIVE YET" header is rewritten, and a comment records that migrations run
   from the laptop, not the (nonexistent) shell.
5. **Neon region is checked against Render's `oregon`** before anything is
   created; a cross-country pairing adds ~70 ms to *every* query.
6. **Media is knowingly broken in production this phase** — see Out of scope.

## Out of scope

- **Media / uploads (Phase 39).** Three independent reasons avatars and lesson
  attachments will 404 in production, all accepted and none a Phase 38
  regression: `config/urls.py:36` only serves `MEDIA_URL` when `DEBUG` is true;
  `MEDIA_URL = 'media/'` (`settings.py:158`) is missing its leading slash; and
  Render's free filesystem is ephemeral, so `MEDIA_ROOT` is wiped on every
  deploy, restart, and spin-down. WhiteNoise covers `staticfiles` only.
  Do **not** "fix" any of this here — R2 replaces it wholesale in Phase 39.
- Cloudflare Pages, `frontend/public/_redirects`, the `VITE_API_URL` prod guard,
  django-storages/R2 — all Phase 39.
- OpenTelemetry / Grafana / Sentry `environment=` tags — Phase 40.
- Custom domain, real email provider (Render's free tier also blocks outbound
  SMTP on 25/465/587 — the console backend stays).
- Upgrading off the free instance type. The ~1 min cold start after 15 min idle
  is accepted for now.
- Adding `migrate` to `buildCommand`, or any new management command
  (`bootstrap_instructor`, an `--instructor-email` flag). Explicitly rejected in
  the interview to keep this phase config-only.
- `makemigrations --check` in CI (a real gap — no CI step catches model drift —
  but it is not this phase's job).
- Migrating any local dev-DB data to Neon. Neon starts empty.
- Editing `docker-compose.prod.yml`, `nginx/`, `backend/Dockerfile.prod`
  (Phase 40 marks them superseded). Note `Dockerfile.prod:29` runs
  `collectstatic` with no `SECRET_KEY` and so now trips the Phase 37 guard —
  leave it; nothing in this phase builds that image.

## Backend tasks

No models, no migrations, no Python changes. Three `render.yaml` edits only.

- [x] `render.yaml`: change `SECRET_KEY` from `sync: false` to
      `generateValue: true`. Render mints a strong key in its vault; it is never
      pasted anywhere. Leaves **6** `sync: false` secrets.
      *(Done — `grep -c 'sync: false'` → 6.)*
- [x] `render.yaml`: rewrite the header comment block. Drop "NOT LIVE YET /
      Nothing here has been applied to a Render account" — describe the live
      service instead.
- [x] `render.yaml`: replace the "run by hand in the Render shell" comment with
      the truth — the free tier has no shell; `migrate`, `createsuperuser`, and
      `populate_java_course` are run from a developer machine with
      `DATABASE_URL` pointed at Neon.
- [x] Confirm `makemigrations --check` is still clean and `/verify-stack`
      passes. The diff is YAML-only, so both should be untouched — run them
      anyway before the PR. *(Both confirmed — see Verification below.)*

## Deployment tasks (dashboards + local one-off commands)

Order matters: bootstrap the DB **before** the first Render deploy, so the
service's first boot lands on a schema that already exists.

### A. Neon

- [x] Check the region of project `ep-falling-frog-avzgk4ed` (db `neondb`).
      **Actual: `aws-us-east-1`** — a mismatch with `render.yaml`'s `oregon`.
      **Decision: moved Render to `virginia`** (one-line YAML change) rather
      than recreating Neon. Note the spec's `ep-falling-frog-avzgk4ed` is the
      *compute endpoint*, not the project; the project is `shy-cloud-68280619`
      ("LMS"), branch `br-falling-art-avcu47in`, db `neondb`, role
      `neondb_owner`.
- [ ] ~~Rotate the Neon password~~ — **deliberately deferred to the end of the
      phase** (user's call, 2026-07-20). Rotating after Render exists costs an
      extra `DATABASE_URL` update + redeploy + deep-health re-check; accepted.
      Still open — carry into the handoff. `neonctl` has no `reset-password`
      subcommand; use the Neon console (Branches → production → Roles) or the
      REST `reset_password` endpoint.
- [x] Confirm the connection string ends in `?sslmode=require`.
      **Deviation:** Neon now returns
      `...?sslmode=require&channel_binding=require`. SSL is still required, so
      `settings.py:114`'s `ssl_require=True` is satisfied, and psycopg2 in the
      container accepts `channel_binding` — the `migrate` run below proves it.
      No DSN editing needed.

### B. Bootstrap the database from this laptop

Run against Neon by overriding `DATABASE_URL` on the existing dev container.
`DEBUG=True` is passed only to skip the Phase 37 `SECRET_KEY`/`ALLOWED_HOSTS`
guard for these CLI calls; it does not touch the deployed service.

- [x] `docker compose exec -T -e DATABASE_URL="<neon>" -e DEBUG=True backend python manage.py migrate`
      — expect all **31** migrations across 6 apps to apply, including the
      `gamification.0002_seed_badges` data migration.
      **Confirmed:** 31 across 6 apps (accounts 3, courses 15, quizzes 3,
      discussions 1, gamification 4, notifications 5); 70 total incl.
      Django/allauth/socialaccount. `Badge.objects.count()` → **7**.
      Users 0, Courses 0.
- [x] `docker compose exec -it -e DATABASE_URL="<neon>" -e DEBUG=True backend python manage.py createsuperuser`
      — a **real** email and a strong password. Not `@demo.com`.
      Created as `cesarvillarreal11@gmail.com` (allauth normalized the
      address to lowercase on save).
- [ ] Fix up the superuser so it is a usable instructor **and** matches what
      `populate_java_course` searches for:
      ```
      docker compose exec -e DATABASE_URL="<neon>" -e DEBUG=True backend \
        python manage.py shell -c "
      from accounts.models import User
      u = User.objects.get(email='<your-email>')
      u.first_name, u.last_name = 'Cesar', 'Villarreal'
      u.is_instructor = True
      u.save()
      print(u.email, u.first_name, u.last_name, u.is_instructor, u.is_staff, u.is_superuser)"
      ```
      Without this, the next step prints `Instructor "Cesar Villarreal" not
      found!` and **silently no-ops**.
      **Done** — verified `Cesar Villarreal`, `is_instructor=True`,
      `is_staff=True`, `is_superuser=True`, `is_active=True`.
- [x] `docker compose exec -e DATABASE_URL="<neon>" -e DEBUG=True backend python manage.py populate_java_course`
      — expect "JAVA101 population complete". **Run this exactly once.**
      **Run once, 2026-07-20.** Output: `Found instructor:
      cesarvillarreal11@gmail.com` / `Course: JAVA101 ... (created)` /
      `Cleared existing content: (0, {})` / `Created 5 units`. The `(0, {})`
      confirms nothing pre-existing was destroyed. **Do not run again.** Despite
      its "NON-DESTRUCTIVE" docstring it does
      `course.units.all().delete()` and rebuilds, which cascades away every
      `LessonProgress` / `LessonQuizAttempt` / `QuizAttempt` on JAVA101.
      Non-destructive to *users and other courses* only. Re-running it after
      students exist wipes their progress.
- [ ] **Never run `seed_data` against Neon.** It hardcodes `Admin123!` on six
      pre-verified `@demo.com` accounts, and `--clear` deletes every course
      globally, JAVA101 included.
- [x] Verify the bootstrap: exactly one user, no `@demo.com` addresses, JAVA101
      present with its units, and the badge catalog seeded.
      **Verified:** 1 user / 0 demo / JAVA101 5 units 20 lessons / 7 badges.
      (After the click-through's student registration the user count is 2 —
      expected.)

### C. Render service

- [x] Create the service via **New → Blueprint** (not "New Web Service") so
      `render.yaml` governs it and `generateValue` actually applies.
      **Done by user 2026-07-20; live at `stemquest-api.onrender.com`.**
- [x] Fill the 6 `sync: false` secrets at blueprint-apply time
      *(done; `CORS_ALLOWED_ORIGINS` was initially mis-entered and fixed
      post-deploy — see Click-through)*:
      | Key | Value |
      |---|---|
      | `DATABASE_URL` | the rotated Neon string, `?sslmode=require` |
      | `ALLOWED_HOSTS` | `stemquest-api.onrender.com` — **bare host, no scheme, no path** |
      | `CSRF_TRUSTED_ORIGINS` | `https://stemquest-api.onrender.com` — **scheme required** (Django 4+) |
      | `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` — scheme + port, **no trailing slash** |
      | `FRONTEND_URL` | `http://localhost:5173` |
      | `SENTRY_DSN` | leave empty (gated on non-empty; Phase 40) |
- [x] After the first deploy, check the **actual** hostname Render assigned.
      **No suffix — `stemquest-api.onrender.com` as specced**, so
      `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` were correct as entered.
      (`CORS_ALLOWED_ORIGINS` was the one that was mis-entered — see
      Click-through below.)
- [x] Confirm auto-deploy from `main` on `Cesar6060/LMS` is on. *(User set up
      via Blueprint; env-var saves observed to trigger redeploys.)*
- [x] Watch the build log: `pip install` then `collectstatic`. **Verified by
      outcome** rather than log-watching: hashed `base.523eb49842a7.css`
      serves 200 as `text/css` (21460 bytes), which only works if
      `collectstatic` ran and the WhiteNoise manifest exists.

## Frontend tasks

No committed frontend changes. One throwaway local run, pointed at prod.

- [x] Start a second Vite dev server against the live API without editing
      `docker-compose.yml` (which hardcodes `VITE_API_URL`):
      ```
      docker compose run --rm -e VITE_API_URL="https://<host>.onrender.com/api" \
        -p 5173:5173 frontend npm run dev -- --host
      ```
      Note the `/api` suffix — `frontend/src/services/api.ts:3` expects the base
      URL to already include it. Whatever port you land on must match
      `CORS_ALLOWED_ORIGINS` exactly.
      **Two gotchas hit:** (1) the dev `frontend` container must be stopped
      first — it holds 5173; (2) `docker compose run` creates a *fresh
      anonymous volume* for `/app/node_modules` seeded from the stale image, so
      newer deps (`recharts`, `@dnd-kit/*`) were missing — fixed by prefixing
      the command with `npm install &&`. Vite 6.4.1 ready on 5173, 0 unresolved
      imports.

## Verification

The phase is done when all of the following are demonstrated with pasted output.

**Repo (before the deploy work):**
- [x] `/verify-stack` PASS — pytest **354 passed** in 45.90s, `tsc --noEmit`
      **0 errors**, lint **0 errors / 22 warnings** (= baseline). 2026-07-20.
- [x] `makemigrations --check` → "No changes detected".
- [x] `render.yaml` still parses as YAML after the three edits (js-yaml via the
      frontend container; `SECRET_KEY` reads back as `{"generateValue":true}`).
- [x] CI green on the PR (#24, run `29791833554`: backend **pass** 2m41s,
      frontend **pass** 40s). `main`-push run still pending merge.

**API over HTTPS:**
Host assigned with **no suffix**: `stemquest-api.onrender.com`, so the spec's
`ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` values were correct as written.

- [x] `curl -si https://stemquest-api.onrender.com/api/health/` → **200**,
      `{"status": "ok"}` (0.32s, warm).
- [x] `curl -si '.../api/health/?deep=1'` → **200**,
      `{"status": "ok", "database": "ok"}` (0.71s) — Neon wired up over SSL.
- [x] `curl -si http://.../api/health/` → **301** →
      `https://stemquest-api.onrender.com/api/health/`. No redirect loop.
- [x] `Strict-Transport-Security: max-age=3600; includeSubDomains` present.
      Also `x-content-type-options: nosniff`, `referrer-policy: same-origin`.
- [ ] A JWT login for the superuser returns 200 with tokens; an authenticated
      `GET /api/courses/` lists JAVA101. **Not run — requires the superuser
      password, which is deliberately not shared with the assistant.** Covered
      transitively by the browser click-through.
- [~] `curl -si -H 'Host: evil.example.com' .../api/health/` → expected **400**,
      **got 403 from Cloudflare** (`Server: cloudflare`, HTML error body).
      Render fronts services with Cloudflare, which rejects an unknown `Host`
      at the edge — the request never reaches Django, so **this test cannot
      verify `ALLOWED_HOSTS` from outside**. Positive evidence instead: a wrong
      `ALLOWED_HOSTS` would 400 *every* request, and all requests to the real
      host return 200. Rewrite this check in a future phase or drop it.

**Admin + static:**
- [x] Hashed filename check: `/admin/login/` references
      `/static/admin/css/base.523eb49842a7.css`, which serves **200**,
      `text/css; charset="utf-8"`, **21460 bytes**. WhiteNoise manifest storage
      is working; `collectstatic` ran. (`/admin/login/` itself → 200.)
- [x] Superuser login through `/admin/` succeeds — proves `CSRF_TRUSTED_ORIGINS`
      and the secure-cookie settings work together over HTTPS.
      *(User-verified 2026-07-20.)*

**Data hygiene:**
- [x] `User.objects.count()` → **1** (`cesarvillarreal11@gmail.com`);
      `@demo.com` addresses → **0**.
- [x] JAVA101 exists: **5 units**, **20 lessons** (spec said ~19),
      instructor `cesarvillarreal11@gmail.com`, `Course.objects.count()` → 1.
      `Badge.objects.count()` → **7**.

**Click-through (local frontend → prod API):**

> First attempt was blocked outright: the deployed `CORS_ALLOWED_ORIGINS` on
> Render emitted **no** `access-control-allow-origin` header (misformatted
> value — blank, trailing slash, or `https://`). Diagnosed by curling local vs
> prod with an `Origin:` header; local (same code) emitted the header, prod
> didn't. Fixed in Render's env editor; after redeploy the header is present.
> Exactly the Phase 39 CORS de-risk this section existed to buy.

- [x] Log in as the instructor at `http://localhost:5173`; the dashboard loads.
      *(User-verified 2026-07-20.)*
- [x] Open JAVA101 → a unit → a lesson in Learning Mode; sections paginate.
      *(User-verified.)*
- [x] Register a brand-new student account, enroll in JAVA101, complete one
      lesson, take one quiz — XP awards and the course map updates.
      *(User-verified — note the Neon DB now has 2 users, not 1.)*
- [x] Browser console shows **zero** CORS errors and zero mixed-content
      warnings. *(User-verified after the CORS fix above.)*
- [x] Confirm avatar/attachment URLs 404 as expected — known, Phase 39.

**Free-tier behaviour:**
- [ ] ~~Leave the service idle >15 min, then time the first request.~~
      **Skipped — user's call, 2026-07-20.** No cold-start figure recorded;
      expect ~1 min per Render's docs. Measure opportunistically in Phase 39
      (the first request after any idle gap is the same experiment for free).

## Known landmines (carry into the handoff)

- `populate_java_course` is a **one-shot** in production. Second run = every
  JAVA101 student's progress gone.
- `seed_data --clear` deletes all courses globally, not just demo data.
- `ALLOWED_HOSTS` unset ≠ crash: it falls back to `localhost,127.0.0.1` and
  400s all real traffic. Only an *explicitly empty* value trips the guard.
- `DEBUG` / `USE_HTTPS` use decouple's strict bool cast — a stray space or a
  value like `TRUE!` raises at import and the boot fails.
- The DRF Browsable API renderer is still enabled in production (no
  `DEFAULT_RENDERER_CLASSES` is set). Not a Phase 38 blocker; worth a later look.
- `/api/health/?deep=1` echoes the raw DB exception string to unauthenticated
  callers, which can leak host/user details. Consider narrowing in Phase 40.
- LocMem cache is per-process and `render.yaml` runs 2 gunicorn workers, so any
  future cache use will be inconsistent across workers.
