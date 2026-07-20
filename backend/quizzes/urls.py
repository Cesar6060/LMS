from django.urls import path
from . import views

urlpatterns = [
    # Quiz management
    path('units/<int:unit_id>/quizzes/', views.unit_quizzes, name='unit-quizzes'),
    path('quizzes/<int:quiz_id>/', views.quiz_detail, name='quiz-detail'),

    # Question management
    path('quizzes/<int:quiz_id>/questions/', views.quiz_add_question, name='quiz-add-question'),
    path('questions/<int:question_id>/', views.question_detail, name='question-detail'),

    # Quiz taking
    path('quizzes/<int:quiz_id>/submit/', views.submit_quiz, name='submit-quiz'),
    path('quizzes/<int:quiz_id>/attempts/', views.quiz_attempts, name='quiz-attempts'),

    # Mastery session flow (Phase 32)
    path('quizzes/<int:quiz_id>/session/start/', views.start_quiz_session, name='quiz-session-start'),
    path('quizzes/<int:quiz_id>/session/', views.get_quiz_session, name='quiz-session'),
    path('quizzes/<int:quiz_id>/session/answer/', views.answer_quiz_session, name='quiz-session-answer'),

    # Course-level quiz list
    path('courses/<str:course_code>/quizzes/', views.course_quizzes, name='course-quizzes'),

    # Quick grade for gradebook
    path('quizzes/<int:quiz_id>/quick-grade/<int:student_id>/', views.quick_grade_quiz, name='quick-grade-quiz'),
]
