from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'courses', views.CourseViewSet, basename='course')
router.register(r'instructor/courses', views.InstructorCourseViewSet, basename='instructor-course')
router.register(r'units', views.UnitViewSet, basename='unit')
router.register(r'lessons', views.LessonViewSet, basename='lesson')
router.register(r'enrollments', views.EnrollmentViewSet, basename='enrollment')
router.register(r'announcements', views.AnnouncementViewSet, basename='announcement')

urlpatterns = [
    # Router URLs
    path('', include(router.urls)),

    # Nested routes
    path('courses/<str:course_code>/units/', views.CourseUnitsView.as_view(), name='course-units'),
    path('units/<int:unit_id>/lessons/', views.UnitLessonsView.as_view(), name='unit-lessons'),

    # Progress tracking
    path('lessons/<int:lesson_id>/progress/', views.LessonProgressView.as_view(), name='lesson-progress'),
    path('courses/<str:course_code>/progress/', views.CourseProgressView.as_view(), name='course-progress'),

    # Announcements
    path('courses/<str:course_code>/announcements/', views.CourseAnnouncementsView.as_view(), name='course-announcements'),

    # Gradebook
    path('courses/<str:course_code>/gradebook/', views.gradebook, name='course-gradebook'),
    path('courses/<str:course_code>/gradebook/export/', views.gradebook_export, name='course-gradebook-export'),
    path('courses/<str:course_code>/grading-config/', views.course_grading_config, name='course-grading-config'),
    path('courses/<str:course_code>/my-grades/', views.student_grade_summary, name='student-grade-summary'),

    # Student Roster
    path('courses/<str:course_code>/students/', views.student_roster, name='student-roster'),
    path('courses/<str:course_code>/students/invite/', views.send_course_invite, name='send-invite'),
    path('courses/<str:course_code>/students/<int:enrollment_id>/', views.remove_student, name='remove-student'),

    # Activity tracking
    path('courses/<str:course_code>/activity/', views.update_course_activity, name='update-activity'),

    # Dashboard (Phase 13)
    path('dashboard/stats/', views.dashboard_stats, name='dashboard-stats'),
    path('dashboard/enhanced/', views.enhanced_dashboard, name='enhanced-dashboard'),

    # Lesson Questions (Comprehension Checks - Phase 15)
    path('lessons/<int:lesson_id>/questions/', views.lesson_questions, name='lesson-questions'),
    path('lessons/<int:lesson_id>/questions/<int:question_id>/', views.lesson_question_detail, name='lesson-question-detail'),
    path('lessons/<int:lesson_id>/answer-question/', views.answer_lesson_question, name='answer-lesson-question'),
    path('lessons/<int:lesson_id>/questions-status/', views.lesson_questions_status, name='lesson-questions-status'),
    path('lessons/<int:lesson_id>/submit-quiz/', views.submit_lesson_quiz, name='submit-lesson-quiz'),

    # Lesson Attachments (Phase 16)
    path('lessons/<int:lesson_id>/attachments/', views.lesson_attachments, name='lesson-attachments'),
    path('lessons/<int:lesson_id>/attachments/<int:attachment_id>/', views.lesson_attachment_detail, name='lesson-attachment-detail'),
]
