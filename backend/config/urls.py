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
