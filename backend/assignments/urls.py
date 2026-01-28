from django.urls import path
from . import views

urlpatterns = [
    # Course assignments list
    path(
        'courses/<str:course_code>/assignments/',
        views.AssignmentListView.as_view(),
        name='course-assignments'
    ),

    # Unit assignments
    path(
        'units/<int:unit_id>/assignments/',
        views.UnitAssignmentListCreateView.as_view(),
        name='unit-assignments'
    ),

    # Single assignment
    path(
        'assignments/<int:pk>/',
        views.AssignmentDetailView.as_view(),
        name='assignment-detail'
    ),

    # Student's own submission
    path(
        'assignments/<int:assignment_id>/my-submission/',
        views.MySubmissionView.as_view(),
        name='my-submission'
    ),

    # Submit assignment
    path(
        'assignments/<int:assignment_id>/submit/',
        views.submit_assignment,
        name='submit-assignment'
    ),

    # Instructor: list all submissions
    path(
        'assignments/<int:assignment_id>/submissions/',
        views.AssignmentSubmissionsView.as_view(),
        name='assignment-submissions'
    ),

    # Instructor: grade submission
    path(
        'submissions/<int:submission_id>/grade/',
        views.GradeSubmissionView.as_view(),
        name='grade-submission'
    ),

    # Instructor: allow resubmission
    path(
        'submissions/<int:submission_id>/allow-resubmit/',
        views.allow_resubmission,
        name='allow-resubmission'
    ),

    # Instructor: quick grade (inline gradebook editing)
    path(
        'assignments/<int:assignment_id>/quick-grade/<int:student_id>/',
        views.quick_grade,
        name='quick-grade'
    ),
]
