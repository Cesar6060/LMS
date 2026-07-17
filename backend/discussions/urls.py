from django.urls import path
from . import views

urlpatterns = [
    # Course-level thread list + create
    path('courses/<str:course_code>/threads/', views.course_threads, name='course-threads'),

    # Thread detail / update / delete
    path('threads/<int:thread_id>/', views.thread_detail, name='thread-detail'),

    # Thread moderation
    path('threads/<int:thread_id>/pin/', views.toggle_pin, name='thread-pin'),
    path('threads/<int:thread_id>/lock/', views.toggle_lock, name='thread-lock'),

    # Replies
    path('threads/<int:thread_id>/replies/', views.create_reply, name='create-reply'),
    path('replies/<int:reply_id>/', views.reply_detail, name='reply-detail'),
]
