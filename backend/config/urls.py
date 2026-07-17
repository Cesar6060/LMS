"""
URL configuration for gamedev_platform project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

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
    path('api/assignments/', include('assignments.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/', include('quizzes.urls')),
    path('api/', include('discussions.urls')),

    # Health check
    path('api/health/', lambda request: __import__('django.http', fromlist=['JsonResponse']).JsonResponse({'status': 'ok'})),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
