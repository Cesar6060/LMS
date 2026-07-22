"""
Django settings for gamedev_platform project.
"""

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
    'rest_framework.authtoken',
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
    'django.middleware.security.SecurityMiddleware',
    # Must sit directly after SecurityMiddleware so a static hit is served
    # before anything downstream can short-circuit the request.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
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

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
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
            # Public r2.dev host: makes .url return an absolute public URL
            # instead of a path under MEDIA_URL.
            'custom_domain': config('R2_PUBLIC_HOST'),
            'querystring_auth': False,
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
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    # Throttle anonymous (pre-login) traffic by IP. This is the brute-force guard
    # for /api/auth/login|registration|password/reset. Off by default (rate=None
    # => unlimited) so tests and local dev are unaffected; set THROTTLE_ANON in
    # production, e.g. '30/min'. Authenticated demo traffic is never throttled
    # (AnonRateThrottle only applies to anonymous requests), so a shared demo
    # login isn't collectively rate-limited.
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': config('THROTTLE_ANON', default=None),
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
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'

# Public self-registration. The live site runs as a demo (visitors log in as the
# shared jdoe@demo.com student only), so registration is OFF by default and must
# be explicitly enabled — set ALLOW_REGISTRATION=True for local development.
ALLOW_REGISTRATION = config('ALLOW_REGISTRATION', default=False, cast=bool)

# The shared public demo account. Its password is published in the README, so we
# forbid changing it — otherwise any visitor could lock every other visitor out
# of the demo until an operator re-runs seed_demo_account.
DEMO_ACCOUNT_EMAIL = config('DEMO_ACCOUNT_EMAIL', default='jdoe@demo.com')

# Django admin mount path. Production can move it off the default to shrink the
# brute-force surface. No leading slash; must end with '/' (it's a url prefix).
ADMIN_URL = config('ADMIN_URL', default='admin/')

# Largest avatar image a user may upload (enforced in accounts.views.upload_avatar).
# Django's DATA_UPLOAD_MAX_MEMORY_SIZE deliberately excludes file fields, so the
# only real cap on an uploaded file is a view-level size check.
AVATAR_MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# Django Allauth Settings
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = config('ACCOUNT_EMAIL_VERIFICATION', default='optional')
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True

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

# Frontend URL (for email links)
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5173')

# dj-rest-auth Settings
REST_AUTH = {
    'USE_JWT': False,
    'TOKEN_MODEL': 'rest_framework.authtoken.models.Token',
    'USER_DETAILS_SERIALIZER': 'accounts.serializers.UserSerializer',
    'REGISTER_SERIALIZER': 'accounts.serializers.RegisterSerializer',
    'PASSWORD_CHANGE_SERIALIZER': 'accounts.serializers.ProtectedPasswordChangeSerializer',
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
