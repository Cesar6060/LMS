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
router.register(r'instructor/reminders', views.InstructorReminderViewSet, basename='instructor-reminder')

urlpatterns = [
    # Router URLs
    path('', include(router.urls)),

    # Nested routes
    path('courses/<str:course_code>/units/', views.CourseUnitsView.as_view(), name='course-units'),
    path('units/<int:unit_id>/lessons/', views.UnitLessonsView.as_view(), name='unit-lessons'),

    # Progress tracking
    path('lessons/<int:lesson_id>/progress/', views.LessonProgressView.as_view(), name='lesson-progress'),
    path('courses/<str:course_code>/progress/', views.CourseProgressView.as_view(), name='course-progress'),

    # Course Map (Phase 35)
    path('courses/<str:course_code>/map/', views.course_map, name='course-map'),

    # Announcements
    path('courses/<str:course_code>/announcements/', views.CourseAnnouncementsView.as_view(), name='course-announcements'),

    # Gradebook
    path('courses/<str:course_code>/gradebook/', views.gradebook, name='course-gradebook'),
    path('courses/<str:course_code>/gradebook/export/', views.gradebook_export, name='course-gradebook-export'),
    path('courses/<str:course_code>/grading-config/', views.course_grading_config, name='course-grading-config'),
    path('courses/<str:course_code>/my-grades/', views.student_grade_summary, name='student-grade-summary'),

    # Student Roster
    path('courses/<str:course_code>/students/', views.student_roster, name='student-roster'),
    path('courses/<str:course_code>/students/<int:enrollment_id>/', views.remove_student, name='remove-student'),

    # Course Invites (Phase 51) — instructor management, then the public
    # token endpoints the emailed accept links hit (no auth required).
    path('courses/<str:course_code>/invites/', views.course_invites, name='course-invites'),
    path('courses/<str:course_code>/invites/<int:invite_id>/', views.revoke_course_invite, name='revoke-invite'),
    path('invites/<str:token>/', views.invite_detail, name='invite-detail'),
    path('invites/<str:token>/accept/', views.accept_invite, name='accept-invite'),

    # Instructor Analytics (Phase 31)
    path('courses/<str:course_code>/analytics/overview/', views.analytics_overview, name='analytics-overview'),
    path('courses/<str:course_code>/analytics/quizzes/', views.analytics_quizzes, name='analytics-quizzes'),
    path('courses/<str:course_code>/analytics/students/', views.analytics_students, name='analytics-students'),
    path('courses/<str:course_code>/analytics/activity/', views.analytics_activity, name='analytics-activity'),

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

    # Lesson-Check Mastery Sessions (Phase 32)
    path('lessons/<int:lesson_id>/quiz-session/start/', views.start_lesson_quiz_session, name='lesson-quiz-session-start'),
    path('lessons/<int:lesson_id>/quiz-session/', views.get_lesson_quiz_session, name='lesson-quiz-session'),
    path('lessons/<int:lesson_id>/quiz-session/answer/', views.answer_lesson_quiz_session, name='lesson-quiz-session-answer'),

    # Lesson Attachments (Phase 16)
    path('lessons/<int:lesson_id>/attachments/', views.lesson_attachments, name='lesson-attachments'),
    path('lessons/<int:lesson_id>/attachments/<int:attachment_id>/', views.lesson_attachment_detail, name='lesson-attachment-detail'),

    # Lesson Sections (Phase 17: Lesson Pagination)
    path('lessons/<int:lesson_id>/sections/', views.lesson_sections, name='lesson-sections'),
    path('lessons/<int:lesson_id>/sections/bulk/', views.lesson_sections_bulk_create, name='lesson-sections-bulk-create'),
    path('lessons/<int:lesson_id>/sections/<int:section_id>/', views.lesson_section_detail, name='lesson-section-detail'),
    path('lessons/<int:lesson_id>/sections/reorder/', views.lesson_sections_reorder, name='lesson-sections-reorder'),

    # Instructor Progress Reset
    path('lessons/<int:lesson_id>/progress/reset/', views.reset_lesson_progress, name='reset-lesson-progress'),

    # Instructor Calendar
    path('instructor/calendar/', views.instructor_calendar, name='instructor-calendar'),
]
