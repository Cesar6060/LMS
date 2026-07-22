"""
URL configuration for gamedev_platform project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from config.health import health, sentry_debug

urlpatterns = [
    # Admin path is configurable so production can move it off the guessable
    # default (set ADMIN_URL, e.g. 'secret-console/'), shrinking the brute-force
    # surface. Defaults to 'admin/' for local dev.
    path(settings.ADMIN_URL, admin.site.urls),

    # API endpoints
    #
    # ORDERING DEPENDENCY: the 'api/courses/' include is evaluated before the
    # bare 'api/' includes below, yet quizzes and discussions serve
    # 'courses/<code>/quizzes/' and 'courses/<code>/threads/' via those bare
    # mounts. That only works because the courses app defines no competing
    # pattern under api/courses/ — a future courses route matching
    # 'courses/<code>/quizzes/' or 'courses/<code>/threads/' would shadow the
    # quizzes/discussions views. Guard tests: config/tests/test_url_conf.py.
    path('api/auth/', include('accounts.urls')),
    path('api/courses/', include('courses.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/gamification/', include('gamification.urls')),
    path('api/', include('quizzes.urls')),
    path('api/', include('discussions.urls')),

    # Health check
    path('api/health/', health, name='health'),

    # Sentry smoke test — 404 unless SENTRY_DEBUG_ENDPOINT is set (health.py)
    path('api/sentry-debug/', sentry_debug, name='sentry-debug'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
