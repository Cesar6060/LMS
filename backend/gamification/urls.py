from django.urls import path

from . import views

urlpatterns = [
    path('profile/', views.gamification_profile, name='gamification-profile'),
    path('avatar/', views.update_avatar, name='gamification-avatar'),
]
