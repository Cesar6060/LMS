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

```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_view(request, course_code):
    course = get_object_or_404(Course, code=course_code)
    if request.user != course.instructor:
        return Response({'error': 'Forbidden'}, status=403)
    # ... rest of view
```
