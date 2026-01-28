from rest_framework import permissions


class IsInstructor(permissions.BasePermission):
    """
    Permission check for instructor-only actions.
    """
    message = "Only instructors can perform this action."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_instructor


class IsInstructorOrReadOnly(permissions.BasePermission):
    """
    Instructors can perform any action.
    Others can only read.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and request.user.is_instructor


class IsCourseInstructor(permissions.BasePermission):
    """
    Permission check for course-specific instructor actions.
    Only the course instructor can modify the course.
    """
    message = "Only the course instructor can perform this action."

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only for course instructor
        # Handle different object types
        if hasattr(obj, 'instructor'):
            return obj.instructor == request.user
        elif hasattr(obj, 'course'):
            return obj.course.instructor == request.user
        elif hasattr(obj, 'unit'):
            return obj.unit.course.instructor == request.user
        return False


class IsEnrolledOrInstructor(permissions.BasePermission):
    """
    Permission for accessing course content.
    Allows access if user is enrolled or is the instructor.
    """
    message = "You must be enrolled in this course or be the instructor."

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Get the course from the object
        if hasattr(obj, 'instructor'):
            course = obj
        elif hasattr(obj, 'course'):
            course = obj.course
        elif hasattr(obj, 'unit'):
            course = obj.unit.course
        else:
            return False

        # Check if user is instructor
        if course.instructor == user:
            return True

        # Check if user is actively enrolled
        return course.enrollments.filter(user=user, is_active=True).exists()
