from django.urls import path

from . import views

urlpatterns = [
    path('profile/', views.gamification_profile, name='gamification-profile'),
]
