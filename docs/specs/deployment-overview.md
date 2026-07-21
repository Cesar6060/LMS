# Deployment track overview — Phases 36–40

STEM Quest moves from local-only docker-compose to a live deployment:
**Cloudflare Pages** (frontend) + **Render** (Django API) + **Neon**
(Postgres) + **Cloudflare R2** (media) + **Grafana Cloud** (observability via
OpenTelemetry). Split into five phases so each lands with its own
verification. Per the workflow rule, each phase gets its own detailed spec in
`docs/specs/` written just before it starts — this overview is the roadmap
and holds the shared decisions.

## Shared decisions (scoping interview, 2026-07-20)

- **Render free tier**, native Python runtime (not Docker). Accept ~1 min
  cold start after 15 min idle; upgrade later if it bites during class.
- **Default subdomains** (`*.pages.dev`, `*.onrender.com`). No custom domain;
  all origins env-driven so a domain later is config-only.
- **R2 public-read bucket** (`pub-<hash>.r2.dev`). Media links are public;
  not auth-enforced (accepted for avatars + lesson attachments).
- **Email stays console backend** in prod — no real email provider yet.
- **Prod data**: clean DB + one real superuser/instructor +
  `populate_java_course` (JAVA101). **Never run `seed_data` in prod** (demo
  accounts with known passwords).
- **CI/CD**: GitHub Actions (pytest + tsc + lint) on PRs and `main`;
  Render + Pages auto-deploy from `main` on `Cesar6060/LMS`. Deploys are not
  hard-gated on CI — merge discipline is the gate.
- **Observability**: OTel traces (Django + psycopg spans) + Django logs →
  Grafana Cloud OTLP gateway. Metrics/dashboards deferred. Sentry stays
  wired and env-gated.
- Accounts already exist: Neon project (`ep-falling-frog-avzgk4ed`, db
  `neondb`), Cloudflare, Render, Grafana Cloud.
- Secrets live **only** in provider dashboards (Render/Pages env vars) —
  never in the repo or chat. Rotate the Neon password before first use (the
  old one sat in local `.env`; gitignored, never committed, rotate anyway).

## Phase breakdown

| Phase | Scope | Done when |
|-------|-------|-----------|
| **36. GitHub Actions CI** | `.github/workflows/ci.yml`: backend pytest vs a Postgres 16 service container; frontend tsc + lint + prod build. No deploy work. | CI green on a PR and on `main` |
| **37. Backend production readiness (code only)** | `dj-database-url` + SSL Neon support, WhiteNoise static, `SECURE_*`/`CSRF_TRUSTED_ORIGINS` hardening, `/api/health/` endpoint, pinned gunicorn, `render.yaml` blueprint, `.env.example` refresh, local `.env` cleanup + Neon password rotation. All new settings inert without their env vars. | `/verify-stack` + CI green; dev docker-compose unchanged |
| **38. API live on Render + Neon** | Create Render Blueprint service from `render.yaml`, set env vars (DATABASE_URL, fresh SECRET_KEY, hosts/origins), auto-deploy on. Render shell: `createsuperuser` + `populate_java_course`. Media still on ephemeral disk (uploads deferred to 39). | `curl /api/health/` 200 over HTTPS; `/admin/` renders with CSS; login works; no demo accounts |
| **39. Frontend on Pages + media on R2** | `frontend/public/_redirects`, prod guard for missing `VITE_API_URL`, django-storages → R2 (`STORAGES['default']`, `querystring_auth=False`, `default_acl=None`), create bucket + public subdomain + scoped API token, create Pages project (root `frontend`, build `npm run build`, out `dist`, Node 22, `VITE_API_URL`), CORS/FRONTEND_URL loop-back on Render. | Full prod click-through: register, enroll JAVA101, map deep-link refresh, avatar upload renders from `r2.dev`, attachment download, zero CORS/mixed-content errors |
| **40. Observability: Grafana Cloud via OTel** | OTel deps + `config/otel.py` (gated on `OTEL_EXPORTER_OTLP_ENDPOINT`): DjangoInstrumentor, PsycopgInstrumentor, LoggingHandler → OTLP HTTP; Grafana token + endpoint into Render; README "Production deployment" section; mark `docker-compose.prod.yml` superseded. | Click-through requests visible as traces (with DB spans) in Tempo and logs in Loki under `service.name=stemquest-api` |

Ordering rationale: CI first so every later phase merges behind a green
check; code-readiness (37) before any dashboard work so the deploy phase is
config-only; API live (38) before the frontend needs a URL to point at; R2
with the frontend phase (39) because avatars/attachments are only exercised
through the UI; observability last (40) once there's real traffic to see.

## Out of scope for the whole track

- Custom domain / DNS
- Real email provider (SMTP/Resend)
- Grafana metrics exporters and dashboards (traces + logs only)
- Redis in production (nothing uses it; Channels still commented out)
- Celery/queues, autoscaling, staging environment
- Private media / presigned URLs
- Migrating local dev-DB data to Neon
- Deleting `docker-compose.prod.yml` / `nginx/` (comment as superseded in
  Phase 40; removal is later cleanup)

## Keys/credentials needed per phase (user-provided, dashboards only)

- 36: none (GitHub Actions enabled on `Cesar6060/LMS` is all)
- 37: none (Neon password rotation happens in Neon's console; new string is
  *noted*, used in 38)
- 38: Neon `DATABASE_URL`; fresh Django `SECRET_KEY` (generated during setup)
- 39: R2 access key ID + secret, account ID, `pub-<hash>.r2.dev` host;
  optional `VITE_SENTRY_DSN`
- 40: Grafana OTLP endpoint + instance ID + API token; optional `SENTRY_DSN`
