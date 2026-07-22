from django.conf import settings
from django.urls import path, include
from . import views

# Registration is gated by ALLOW_REGISTRATION. When off (the default, and how the
# live demo runs), every path under registration/ resolves to a 403 stub so no
# account can be created — the real allauth registration urls are never mounted.
if settings.ALLOW_REGISTRATION:
    registration_patterns = path('registration/', include('dj_rest_auth.registration.urls'))
else:
    registration_patterns = path('registration/', views.registration_disabled)

urlpatterns = [
    # One-click demo login — mounted before the dj_rest_auth include so it
    # can't be shadowed by anything that package mounts at the root.
    path('demo-login/', views.demo_login, name='demo-login'),

    # dj-rest-auth endpoints
    path('', include('dj_rest_auth.urls')),
    registration_patterns,

    # Custom user profile endpoint
    path('profile/', views.user_profile, name='user-profile'),

    # User settings/preferences endpoints
    path('settings/', views.user_settings, name='user-settings'),
    path('settings/avatar/', views.upload_avatar, name='upload-avatar'),
    path('settings/avatar/delete/', views.delete_avatar, name='delete-avatar'),
]
