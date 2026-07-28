from django.conf import settings
from django.urls import include, path, re_path
from . import views

# Registration is gated by ALLOW_REGISTRATION. When off (the default, and how the
# live demo runs), every path under registration/ resolves to a 403 stub so no
# account can be created — the real allauth registration urls are never mounted.
# The sub-paths get explicit stubs too: the frontend still calls verify-email/
# and resend-email/, and they should say "registration is disabled" rather
# than 404.
if settings.ALLOW_REGISTRATION:
    registration_patterns = [
        path('registration/', include('dj_rest_auth.registration.urls')),
    ]
else:
    registration_patterns = [
        path('registration/', views.registration_disabled),
        path('registration/verify-email/', views.registration_disabled),
        path('registration/resend-email/', views.registration_disabled),
    ]

urlpatterns = [
    # One-click demo login — mounted before the dj_rest_auth include so it
    # can't be shadowed by anything that package mounts at the root.
    path('demo-login/', views.demo_login, name='demo-login'),

    # Throttled password reset — mounted before the dj_rest_auth include so it
    # shadows the package's unthrottled view at the same path.
    #
    # These shadows use re_path with an optional trailing slash on purpose:
    # dj_rest_auth mounts its own views as r'password/reset/?$' and
    # r'user/?$', so a path() shadow only captures the trailing-slash
    # spelling and the bare one falls through to the unshadowed original —
    # skipping the throttle here, and (until phase 56 caught it) the demo
    # write guard below.
    re_path(r'^password/reset/?$', views.ThrottledPasswordResetView.as_view(),
            name='rest_password_reset'),

    # /api/auth/user/ with demo writes blocked — shadows dj-rest-auth's
    # UserDetailsView, which shares UserSerializer with profile/ below.
    # Defence-in-depth: UserSerializer.update() also refuses the demo account.
    re_path(r'^user/?$', views.DemoSafeUserDetailsView.as_view(),
            name='rest_user_details'),

    # dj-rest-auth endpoints
    path('', include('dj_rest_auth.urls')),
    *registration_patterns,

    # Custom user profile endpoint
    path('profile/', views.user_profile, name='user-profile'),

    # User settings/preferences endpoints
    path('settings/', views.user_settings, name='user-settings'),
    path('settings/avatar/', views.upload_avatar, name='upload-avatar'),
    path('settings/avatar/delete/', views.delete_avatar, name='delete-avatar'),
]
