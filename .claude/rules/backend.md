---
paths:
  - "backend/**/*.py"
---

# Django Backend Rules

- Follow PEP 8; use type hints where helpful
- REST endpoints live under `/api/`; course-specific routes use course code: `/api/courses/{code}/...`
- Instructor-only endpoints must check `request.user == course.instructor`
- Student endpoints must check enrollment via `Enrollment.objects.filter(...)`
- Every new endpoint gets a pytest covering the permission boundary (instructor vs student vs anonymous)
- Prefer running single test files (`pytest path/to/test.py`), not the whole suite

## Standard view pattern

All authorization checks live in `courses/permissions.py` — import the shared
helpers instead of writing inline checks. Denials are always 403 with
`{'detail': ...}` (raise `PermissionDenied`); never return empty lists or
`{'error': ...}` bodies for permission failures.

```python
from courses.permissions import require_course_instructor, require_course_access

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_view(request, course_code):
    course = get_object_or_404(Course, code=course_code)
    require_course_instructor(request.user, course)   # instructor-only endpoint
    # require_course_access(request.user, course)     # enrolled-or-instructor endpoint
    # ... rest of view
```
