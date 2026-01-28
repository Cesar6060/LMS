from django.urls import path, include
from . import views

urlpatterns = [
    # dj-rest-auth endpoints
    path('', include('dj_rest_auth.urls')),
    path('registration/', include('dj_rest_auth.registration.urls')),

    # Custom user profile endpoint
    path('profile/', views.user_profile, name='user-profile'),

    # User settings/preferences endpoints
    path('settings/', views.user_settings, name='user-settings'),
    path('settings/avatar/', views.upload_avatar, name='upload-avatar'),
    path('settings/avatar/delete/', views.delete_avatar, name='delete-avatar'),
]
