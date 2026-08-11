"""
Django settings for gamedev_platform project.
"""

import tempfile
from datetime import timedelta
from pathlib import Path
from decouple import config, Csv
from django.core.exceptions import ImproperlyConfigured
import dj_database_url
import sentry_sdk

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# Hoisted to a constant so the DEBUG=False guard below can detect it.
INSECURE_SECRET_KEY = 'django-insecure-dev-key-change-in-production'
SECRET_KEY = config('SECRET_KEY', default=INSECURE_SECRET_KEY)

# SECURITY WARNING: don't run with debug turned on in production!
# Defaults to False: an unconfigured boot should fail loudly, not run public.
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Fail fast rather than serve production traffic with dev credentials.
if not DEBUG:
    # `not SECRET_KEY` catches `SECRET_KEY=` in the environment, which decouple
    # reads as '' rather than falling back to the default.
    if not SECRET_KEY or SECRET_KEY == INSECURE_SECRET_KEY:
        raise ImproperlyConfigured(
            'SECRET_KEY must be set when DEBUG is False.')
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            'ALLOWED_HOSTS must be set when DEBUG is False.')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'dj_rest_auth',
    'dj_rest_auth.registration',

    # Local apps
    'accounts',
    'courses',
    'notifications',
    'quizzes',
    'discussions',
    'gamification',
]

MIDDLEWARE = [
    # First so every early response — including SECURE_SSL_REDIRECT 301s
    # from SecurityMiddleware — still carries CORS headers; without them
    # the browser reports an opaque CORS failure instead of the redirect.
    # Side effect, by design: CORS preflights short-circuit here, above the
    # security-header middlewares, so OPTIONS responses carry only CORS
    # headers (browsers never render or follow a preflight body anyway).
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    # Must sit directly after SecurityMiddleware so a static hit is served
    # before anything downstream can short-circuit the request.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'csp.middleware.CSPMiddleware',
    'config.middleware.PermissionsPolicyMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='gamedev_db'),
        'USER': config('DB_USER', default='gamedev_user'),
        'PASSWORD': config('DB_PASSWORD', default='devpassword'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# Production (Neon) overrides the DB_* dict when DATABASE_URL is set. Inert
# without it, so local compose keeps its short-lived, non-SSL connections.
DATABASE_URL = config('DATABASE_URL', default='')
if DATABASE_URL:
    DATABASES['default'] = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=True,
    )

# Caches
#
# Only throttling uses a cache in this project — there is no page caching, no
# session cache (sessions are database-backed), and no memoization. `default`
# is spelled out rather than left implicit so the contrast with `throttle` is
# visible: it is Django's stock per-process LocMemCache and nothing depends on
# it being shared.
#
# `throttle` exists because DRF stores rate-limit counters in a cache, and
# production runs `gunicorn --workers 2` (render.yaml). Under LocMemCache each
# worker kept its own counters, so every configured rate — THROTTLE_ANON,
# THROTTLE_USER, THROTTLE_PASSWORD_RESET and the rest — was enforced at roughly
# double its stated value, and would have drifted again with any worker-count
# change. A file-backed cache fixes that: both workers are processes in one
# container and share one filesystem.
#
# Why not a database cache on Neon: the `anon` and `user` scopes are checked on
# EVERY request, so routing them through Postgres would add several queries to
# the hottest path in the app — trading a limit-accuracy bug for a latency bug.
# Why not Redis: it would mean a new service, a new dependency, and a new
# failure mode for a counter store that tolerates loss.
#
# Two limits, both accepted:
#   - Counters reset when the container restarts (deploys). Unchanged from the
#     LocMemCache behaviour it replaces.
#   - It is shared per *container*, not globally. If the service is ever scaled
#     past one instance the per-process split returns as a per-instance split,
#     and this needs to become Redis. The same applies for the few seconds a
#     zero-downtime deploy runs two containers.
#
# MAX_ENTRIES is raised well above Django's default of 300: throttling holds one
# key per client IP plus one per user id, so a single class of 200 students can
# exceed 300 and culling would start discarding live counters — silently
# widening the limits this alias exists to enforce.
#
# No TIMEOUT: DRF passes its own per-key duration to cache.set().
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
    'throttle': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': config(
            'THROTTLE_CACHE_DIR',
            default=str(Path(tempfile.gettempdir()) / 'stemquest-throttle'),
        ),
        'OPTIONS': {
            'MAX_ENTRIES': 5000,
            'CULL_FREQUENCY': 4,
        },
    },
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    # Phase 73 (E3): the four stock validators above catch structural weakness
    # but not reuse of a password already in a public breach dump, which is what
    # credential stuffing runs on. The minimum length stays at 8 by decision —
    # breach screening is the stronger signal and raising the floor would only
    # lock out existing accounts. Fails open on any HIBP error; see
    # core/password_validation.py for why.
    {'NAME': 'core.password_validation.PwnedPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Chicago'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise serves /static/ straight from gunicorn in production, so no nginx
# is needed for /admin/ CSS. Manifest storage requires collectstatic to have
# run (it reads staticfiles.json), hence the plain backend under DEBUG.
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage'
            if DEBUG else
            'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}

# Media files (uploads)
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Cloudflare R2 media storage — opt-in via USE_R2, mirroring the USE_HTTPS
# idiom below: inert in dev/CI, and a missing R2_* var under USE_R2=true fails
# fast at boot (decouple raises UndefinedValueError — no defaults on purpose).
USE_R2 = config('USE_R2', default=False, cast=bool)
if USE_R2:
    STORAGES['default'] = {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'access_key': config('R2_ACCESS_KEY_ID'),
            'secret_key': config('R2_SECRET_ACCESS_KEY'),
            'bucket_name': config('R2_BUCKET_NAME'),
            'endpoint_url': f"https://{config('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
            # Private bucket (Phase 43): .url returns a presigned URL that
            # expires, so a shared attachment link can't bypass the enrollment
            # checks the API enforces. The bucket's public r2.dev access must
            # stay disabled — there is no custom_domain on purpose.
            'querystring_auth': True,
            'querystring_expire': config('R2_SIGNED_URL_TTL', default=3600, cast=int),
            'default_acl': None,
            'file_overwrite': False,
            'region_name': 'auto',
            'signature_version': 's3v4',
        },
    }

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Site ID for django-allauth
SITE_ID = 1

# Django REST Framework
# Whether CF-Connecting-IP may be trusted as the real client address
# (core.throttling.ClientIPIdentMixin). It is authoritative only when *every*
# request provably arrives through Cloudflare's edge, which overwrites any
# client-supplied value. That holds for the Render service behind Cloudflare;
# it does not hold for a local runserver or the test client, where anyone can
# set the header and mint themselves a fresh throttle bucket. Stating the trust
# boundary as a setting keeps it in code rather than implied by a docstring.
# Defaults to on wherever DEBUG is off (i.e. production), off in dev/tests.
TRUST_CF_HEADERS = config('TRUST_CF_HEADERS', default=not DEBUG, cast=bool)

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        # JWTCookieAuthentication also accepts plain `Authorization: Bearer`
        # headers (our only transport — no auth cookies are configured), so it
        # works for the localStorage token flow the frontend uses.
        'dj_rest_auth.jwt_auth.JWTCookieAuthentication',
        # Session auth stays for the Django admin.
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    # Throttle anonymous (pre-login) traffic by IP. This is the brute-force guard
    # for /api/auth/login|registration|password/reset. Off by default (rate=None
    # => unlimited) so tests and local dev are unaffected; set THROTTLE_ANON in
    # production, e.g. '30/min'. Authenticated demo traffic is under the 'user'
    # throttle like everyone else, but keyed per client IP rather than per
    # user id — every visitor shares one account, and a pk-keyed bucket would
    # let one visitor exhaust the whole demo's allowance (core/throttling.py).
    # ClientIPAnonRateThrottle (not the stock AnonRateThrottle): production
    # sits behind Cloudflare, whose rotating edge IP in X-Forwarded-For gives
    # every request a fresh throttle bucket under DRF's default ident. The
    # subclass keys on CF-Connecting-IP instead — see core/throttling.py.
    'DEFAULT_THROTTLE_CLASSES': [
        'core.throttling.ClientIPAnonRateThrottle',
        # Phase 51: real students mean authenticated traffic deserves a
        # ceiling too. Keyed on user id; same env-gated pattern (THROTTLE_USER
        # unset = unlimited, production ~120/min).
        'core.throttling.ClientIPUserRateThrottle',
    ],
    # Phase 73: every rate below used to default to None, and DRF reads None as
    # "unlimited". A scope whose env var was never set in the Render dashboard
    # was therefore silently unthrottled in production — which is how
    # THROTTLE_JOIN_CODE and THROTTLE_INVITE_LINK came to be live with no
    # ceiling at all. The defaults now carry the values the dashboard was meant
    # to hold, so a missing env var fails safe (protected) instead of open.
    # Env vars still override; tests neutralise these via conftest.py.
    'DEFAULT_THROTTLE_RATES': {
        'anon': config('THROTTLE_ANON', default='30/min'),
        'user': config('THROTTLE_USER', default='120/min'),
        # One-click demo login (accounts.views.demo_login).
        'demo_login': config('THROTTLE_DEMO_LOGIN', default='10/min'),
        # Anonymous password reset (accounts.views.ThrottledPasswordResetView)
        # sends real email in production (Phase 47), so it gets its own tight
        # rate on top of the general anon throttle.
        'password_reset': config('THROTTLE_PASSWORD_RESET', default='5/hour'),
        # Phase 73: the *confirm* half accepts the emailed reset token. Leaving
        # it on the general anon rate made the token itself brute-forceable, so
        # it gets the same tight ceiling as requesting a reset.
        'password_reset_confirm': config(
            'THROTTLE_PASSWORD_RESET_CONFIRM', default='5/hour'),
        # Phase 73: password guessing against dj-rest-auth's LoginView, keyed
        # on the client address.
        #
        # 30/min rather than the 10/min first written here: throttle idents are
        # the client IP, and a school NAT puts a whole classroom behind one
        # address. At 10/min the eleventh student to log in at the start of a
        # period gets a 429 — an outage indistinguishable from the site being
        # down. 30/min is still a hard ceiling on guessing from one source, and
        # the per-account 'login_email' scope below is what actually bounds an
        # attack on a specific victim.
        'login': config('THROTTLE_LOGIN', default='30/min'),
        # Phase 73: the per-account half, keyed on the submitted email rather
        # than the address, so a run distributed across many IPs is still
        # capped. Generous enough that a student re-entering a forgotten
        # password never notices it.
        'login_email': config('THROTTLE_LOGIN_EMAIL', default='20/hour'),
        # Course invites (Phase 51). Sending is instructor-triggered email;
        # accepting is an anonymous account-creation endpoint, so it is tighter.
        'invite_send': config('THROTTLE_INVITE_SEND', default='30/hour'),
        'invite_accept': config('THROTTLE_INVITE_ACCEPT', default='10/hour'),
        # Invite fallbacks (Phase 67). invite_link hands the instructor a live
        # token, so it gets its own ceiling on top of the per-user one.
        # join_code is the anonymous redemption endpoint — same shape and rate
        # as invite_accept, and the tight limit is what stops someone walking a
        # leaked code through an email list.
        'invite_link': config('THROTTLE_INVITE_LINK', default='60/hour'),
        # 60/hour, not the 10/hour the old comments suggested. join_code is
        # keyed on the client address and redeemed by a whole class at once
        # from behind one school NAT — at 10/hour the eleventh student cannot
        # join until the next hour. That value was only ever a suggestion in
        # render.yaml and was never actually set in production, which is why
        # nobody had discovered it breaks the flow it governs. Enumeration is
        # bounded primarily by the single generic error string (no oracle) and
        # the required code+email match, not by this number.
        'join_code': config('THROTTLE_JOIN_CODE', default='60/hour'),
        # Slide-deck import (Phase 61): one multipart upload per slide, so a
        # 100-page deck is 100 writes in quick succession — the rate must
        # allow a burst that size.
        'slide_import': config('THROTTLE_SLIDE_IMPORT', default='300/hour'),
        # Phase 73: lesson attachments. Instructor-only and capped at 10 per
        # lesson, so this is a ceiling on sustained upload volume, not a
        # per-lesson limit.
        'attachment_upload': config(
            'THROTTLE_ATTACHMENT_UPLOAD', default='60/hour'),
    },
}

# CORS Settings
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173,http://127.0.0.1:5173',
    cast=Csv()
)
CORS_ALLOW_CREDENTIALS = True

# HTTPS hardening — opt-in via USE_HTTPS, deliberately NOT keyed off `not DEBUG`
# so the test suite (and CI) can run under DEBUG=False without HTTPS redirects.
USE_HTTPS = config('USE_HTTPS', default=False, cast=bool)

# Phase 73: that opt-in had no guard, so eight settings — SSL redirect, HSTS,
# secure session and CSRF cookies, the proxy header — all hung off one variable
# that nothing verified was set. SECRET_KEY and ALLOWED_HOSTS already fail fast
# when DEBUG is off; this closes the same gap for transport security, where the
# failure is silent rather than loud: the site keeps serving, just over plain
# HTTP with cookies that are not marked Secure.
#
# CI genuinely runs DEBUG=False without HTTPS, so it needs a way through that is
# explicit rather than implied by a missing variable.
ALLOW_INSECURE_NON_DEBUG = config(
    'ALLOW_INSECURE_NON_DEBUG', default=False, cast=bool)
if not DEBUG and not USE_HTTPS and not ALLOW_INSECURE_NON_DEBUG:
    raise ImproperlyConfigured(
        'USE_HTTPS must be set when DEBUG is False. Set '
        'ALLOW_INSECURE_NON_DEBUG=True only for CI or a non-public host.')

# Read unconditionally: /admin/ needs trusted origins even before redirects are
# on, and CORS_ALLOW_CREDENTIALS above makes CSRF origin checks matter.
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

if USE_HTTPS:
    # Render terminates TLS and forwards X-Forwarded-Proto; without this
    # SECURE_SSL_REDIRECT sees plain HTTP forever and loops.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year — the real domain is live and stable
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'

# Content-Security-Policy (django-csp 4.x) — applied to every Django-served
# response. This host only serves JSON API responses and the Django admin, so
# the policy is strict: nothing loads from anywhere but self. style-src keeps
# 'unsafe-inline' as headroom: the pages this host serves render with no inline
# styles under the Django 5.2 admin, but admin/change_list.html still emits a
# conditional <style> block (changelists with no actions) and third-party admin
# widgets may inline styles. Admin scripts are all static files, so script-src
# stays 'self'.
# The React app is served by Cloudflare and carries its own CSP
# (frontend/public/_headers) — this policy never applies to it.
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ("'none'",),
        'script-src': ("'self'",),
        'style-src': ("'self'", "'unsafe-inline'"),
        'img-src': ("'self'",),
        'font-src': ("'self'",),
        'connect-src': ("'self'",),
        'form-action': ("'self'",),
        'frame-ancestors': ("'none'",),
        'base-uri': ("'none'",),
    },
}

# Public self-registration. The live site runs as a demo (visitors log in as the
# shared jdoe@demo.com student only), so registration is OFF by default and must
# be explicitly enabled — set ALLOW_REGISTRATION=True for local development.
ALLOW_REGISTRATION = config('ALLOW_REGISTRATION', default=False, cast=bool)

# The shared public demo account. Visitors log in through the one-click
# /api/auth/demo-login/ endpoint (tokens issued server-side), so the password is
# never shown to them — but changing it is still forbidden, otherwise a visitor
# could break the seed baseline until an operator re-runs seed_demo_account.
#
# Normalized once here so the write guards (core.demo.is_demo_email, which
# compares case-insensitively) and the exact-match lookups (demo_login,
# seed_demo_account) can never disagree about which row is the demo account.
DEMO_ACCOUNT_EMAIL = config(
    'DEMO_ACCOUNT_EMAIL', default='jdoe@demo.com').strip().lower()
# Password used by seed_demo_account when (re)creating the demo user. The
# default keeps local dev and tests working with no extra setup; production
# sets a generated secret so raw-credential login is impossible for visitors.
DEMO_ACCOUNT_PASSWORD = config('DEMO_ACCOUNT_PASSWORD', default='Admin123!')

# Django admin mount path. Production can move it off the default to shrink the
# brute-force surface. No leading slash; must end with '/' (it's a url prefix).
# Guard against an empty env value (which would mount admin at '/') and a
# missing trailing slash.
ADMIN_URL = (config('ADMIN_URL', default='admin/').strip().lstrip('/') or 'admin/')
if not ADMIN_URL.endswith('/'):
    ADMIN_URL += '/'

# Largest avatar image a user may upload (enforced in accounts.views.upload_avatar).
# Django's DATA_UPLOAD_MAX_MEMORY_SIZE deliberately excludes file fields, so the
# only real cap on an uploaded file is a view-level size check.
AVATAR_MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# Largest lesson attachment an instructor may upload, per file (enforced in
# courses.views.lesson_attachments — same view-level pattern as avatars).
ATTACHMENT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024

# Phase 73: ceiling on one multipart request. The per-file limit above bounded
# a single file but not a request carrying ten of them, so the real ceiling was
# 250MB. Set above a full lesson's worth of ordinary material and below
# anything worth using as a memory-pressure lever.
ATTACHMENT_MAX_REQUEST_BYTES = 60 * 1024 * 1024

# Largest slide image the client-side PDF rasterizer may upload, per slide
# (enforced in courses.views.lesson_section_import_slide — same view-level
# pattern as avatars). 1920px-wide WebP pages come in well under this.
SLIDE_IMAGE_MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# Django Allauth Settings
#
# allauth 65.4/65.5 replaced the old per-flag signup configuration with two
# settings. The pairs map as:
#   ACCOUNT_AUTHENTICATION_METHOD = 'email'  ->  ACCOUNT_LOGIN_METHODS = {'email'}
#   ACCOUNT_EMAIL_REQUIRED = True            -\
#   ACCOUNT_USERNAME_REQUIRED = False        -/-> ACCOUNT_SIGNUP_FIELDS
# The two must agree: logging in by email while email is not a required signup
# field raises an ImproperlyConfigured at startup.
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = config('ACCOUNT_EMAIL_VERIFICATION', default='optional')
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True

# Phase 73: there is deliberately no ACCOUNT_RATE_LIMITS here.
#
# It was configured with 'login_failed' and removed once it was shown to be
# dead config on this stack. allauth consumes that limit inside
# DefaultAccountAdapter.pre_authenticate(), which is reached only through
# adapter.authenticate() — and dj-rest-auth's LoginSerializer calls
# django.contrib.auth.authenticate() directly, never touching the adapter. Nine
# failed attempts against one account followed by a successful login proved it
# never fired. None of allauth's own views are mounted either.
#
# The per-account ceiling it was supposed to provide is real and now lives in
# core.throttling.LoginEmailRateThrottle, on the 'login_email' scope, where it
# runs in DRF's throttle pipeline and is actually exercised by a test.

# Email Backend
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@localhost')
# Reset/invite emails send synchronously inside the request; without a timeout
# a slow or blocked SMTP connection would hang the worker until gunicorn kills
# it. Seconds, applied by Django to the SMTP socket.
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=10, cast=int)

# Frontend URL (for email links)
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5173')

# dj-rest-auth Settings — JWT (Phase 43). Short-lived access tokens replace the
# old non-expiring DRF tokens so a leaked token dies on its own. Tokens travel
# in the response body / Authorization header only (no auth cookies): the
# frontend keeps them in localStorage, which is CSRF-free by construction.
REST_AUTH = {
    'USE_JWT': True,
    # False = refresh token is returned in the response body rather than set as
    # an httpOnly cookie. Deliberate while the app is a locked public demo; see
    # the phase 43 spec's out-of-scope note before changing.
    'JWT_AUTH_HTTPONLY': False,
    'TOKEN_MODEL': None,
    'USER_DETAILS_SERIALIZER': 'accounts.serializers.UserSerializer',
    'REGISTER_SERIALIZER': 'accounts.serializers.RegisterSerializer',
    'PASSWORD_CHANGE_SERIALIZER': 'accounts.serializers.ProtectedPasswordChangeSerializer',
    # Sends the branded reset email whose link points at the frontend's
    # /reset-password page instead of Django's backend-relative reset view.
    'PASSWORD_RESET_SERIALIZER': 'accounts.serializers.PasswordResetSerializer',
    # The demo account's password is fixed on BOTH write paths — change and
    # reset-confirm. Leaving this at the stock serializer left the reset path
    # unguarded (phase 56 adversarial finding).
    'PASSWORD_RESET_CONFIRM_SERIALIZER':
        'accounts.serializers.ProtectedPasswordResetConfirmSerializer',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    # Every refresh hands out a new refresh token and kills the old one, so a
    # stolen refresh token stops working as soon as the real client refreshes.
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# Sentry Error Tracking
SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        # Real students use this platform — never send usernames/emails/IPs.
        send_default_pii=False,
        environment=config('SENTRY_ENVIRONMENT', default='production'),
        # Render injects RENDER_GIT_COMMIT; local runs get no release tag.
        release=config('RENDER_GIT_COMMIT', default='') or None,
    )

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': config('DJANGO_LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
    },
}
