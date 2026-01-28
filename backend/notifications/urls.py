from django.urls import path
from . import views

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='notification-list'),
    path('unread-count/', views.unread_count, name='notification-unread-count'),
    path('<int:pk>/read/', views.mark_as_read, name='notification-mark-read'),
    path('mark-all-read/', views.mark_all_as_read, name='notification-mark-all-read'),
]
