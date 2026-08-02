from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied


# ==================== Shared permission helpers ====================
# Single source of truth for authorization checks. All apps (courses,
# quizzes, discussions) import from here instead of defining
# their own copies.

def is_course_instructor(user, course):
    """Check if user is the instructor of a course."""
    return course.instructor == user


def is_enrolled(user, course):
    """Check if user is actively enrolled in a course."""
    from .models import Enrollment
    return Enrollment.objects.filter(user=user, course=course, is_active=True).exists()


def can_access_course(user, course):
    """Read access to course content = course instructor or active enrollment."""
    return is_course_instructor(user, course) or is_enrolled(user, course)


def require_course_instructor(user, course, detail="Only the course instructor can perform this action."):
    """Raise PermissionDenied (403, {'detail': ...}) unless user teaches the course."""
    if not is_course_instructor(user, course):
        raise PermissionDenied(detail)


def require_course_access(user, course, detail="You must be enrolled in this course or be the instructor."):
    """Raise PermissionDenied (403, {'detail': ...}) unless user teaches or is enrolled in the course."""
    if not can_access_course(user, course):
        raise PermissionDenied(detail)


def require_enrollment(user, course, detail="You must be enrolled in this course."):
    """Raise PermissionDenied (403, {'detail': ...}) unless user is actively enrolled."""
    if not is_enrolled(user, course):
        raise PermissionDenied(detail)


def require_unit_unlocked(user, unit, detail="This unit is locked by your instructor."):
    """Raise PermissionDenied (403) when a non-instructor reads a locked unit.

    Phase 66: locking is enforced here, at every content read, not only in the
    UI — a student who pastes a lesson URL for a locked unit must be refused.
    The course instructor always sees their own content, locked or not.
    """
    if not unit.is_locked:
        return
    if is_course_instructor(user, unit.course):
        return
    raise PermissionDenied(detail)


def locked_unit_ids_for(user, course):
    """Unit ids this user must not see content for (empty for the instructor).

    Used to keep locked units out of progress denominators and flat content
    lists. Returns a set so callers can filter in Python or feed a queryset.
    """
    if is_course_instructor(user, course):
        return set()
    return set(course.units.filter(is_locked=True).values_list('id', flat=True))


def accessible_course_ids(user):
    """IDs of courses the user teaches or is actively enrolled in (for queryset scoping)."""
    from .models import Course, Enrollment
    taught = Course.objects.filter(instructor=user).values_list('id', flat=True)
    enrolled = Enrollment.objects.filter(user=user, is_active=True).values_list('course_id', flat=True)
    return set(taught) | set(enrolled)


# ==================== Permission classes ====================

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

    has_permission gates writes to instructor accounts so create/list on
    ViewSets never falls through to bare IsAuthenticated; actual course
    ownership is enforced per-object (or in perform_create for creates,
    where no object exists yet).
    """
    message = "Only the course instructor can perform this action."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_instructor

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

    has_permission gates writes to instructor accounts (students never write
    course content); ownership is enforced per-object and in perform_create.
    """
    message = "You must be enrolled in this course or be the instructor."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_instructor

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

        # Reads: enrolled or instructor. Writes: course instructor only.
        if request.method in permissions.SAFE_METHODS:
            return can_access_course(user, course)
        return is_course_instructor(user, course)
