"""
Health check endpoint for deploy gates and uptime monitoring.

Deliberately a plain Django view rather than a DRF one: DRF's global
IsAuthenticated default (see REST_FRAMEWORK in settings.py) would otherwise
make this 403 for the very monitors that need it.
"""

import logging

from decouple import config
from django.db import connection
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache

logger = logging.getLogger(__name__)

# Phase 73: read once at import, not per request. This gates an unauthenticated
# route whose entire job is to raise an exception, and a per-request read meant
# it could be switched on from the Render dashboard with no deploy and no diff —
# the change would leave no trace in the repository. Requiring a restart makes
# enabling it a visible event.
SENTRY_DEBUG_ENDPOINT_ENABLED = config(
    'SENTRY_DEBUG_ENDPOINT', default=False, cast=bool)


@never_cache
def health(request):
    """Shallow by default; ?deep=1 also proves the database is reachable.

    The shallow path skips the DB on purpose — a cold Neon branch must not be
    able to fail a Render deploy gate.
    """
    if request.GET.get('deep') != '1':
        return JsonResponse({'status': 'ok'})

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:  # noqa: BLE001 - report any DB failure, never crash
        # Log the detail server-side, but never return it: the raw exception can
        # leak the Neon host/user/SSL config to an anonymous caller.
        logger.exception('Health deep-check DB probe failed')
        return JsonResponse(
            {'status': 'error', 'database': 'unavailable'}, status=503)

    # SELECT 1 proves the connection, not the schema — during the phase-65
    # outage a missing column returned 200 through a total content failure.
    # So read real columns through the ORM. Deliberately tolerant of zero rows:
    # a missing column raises ProgrammingError even on an empty table, while
    # requiring rows would break every fresh database and prove nothing extra.
    try:
        _content_probe()
    except Exception:  # noqa: BLE001 - a broken schema must not 500 the monitor
        logger.exception('Health deep-check content probe failed')
        return JsonResponse(
            {'status': 'error', 'content': 'unavailable'}, status=503)

    # `"database": "ok"` must appear verbatim: UptimeRobot monitor 803564235
    # keyword-matches that exact string, and a reshaped body would show up as
    # a silent monitoring outage rather than an alert.
    return JsonResponse({'status': 'ok', 'database': 'ok', 'content': 'ok'})


def _content_probe():
    """Read named columns off the two tables the whole app is built on.

    Imported lazily so this module stays importable before the app registry is
    ready, and kept separate so tests can force the failure path.
    """
    from courses.models import Course, Lesson

    Course.objects.values('id', 'code', 'join_code').first()
    Lesson.objects.values('id', 'content_key', 'unit_id').first()


@never_cache
def sentry_debug(request):
    """Deliberately crash so a production Sentry event can be forced on demand.

    Render's free tier has no shell, so this is the only way to smoke-test the
    Sentry pipeline in prod. Inert (404) unless SENTRY_DEBUG_ENDPOINT is set at
    boot — changing it now requires a restart, by design (see the constant).
    """
    if not SENTRY_DEBUG_ENDPOINT_ENABLED:
        raise Http404
    1 / 0  # noqa: B018 - the ZeroDivisionError IS the smoke test
