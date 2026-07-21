"""
Health check endpoint for deploy gates and uptime monitoring.

Deliberately a plain Django view rather than a DRF one: DRF's global
IsAuthenticated default (see REST_FRAMEWORK in settings.py) would otherwise
make this 403 for the very monitors that need it.
"""

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache


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
    except Exception as exc:  # noqa: BLE001 - report any DB failure, never crash
        return JsonResponse(
            {'status': 'error', 'database': str(exc)}, status=503)

    return JsonResponse({'status': 'ok', 'database': 'ok'})
