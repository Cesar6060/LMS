# Claude Code Project Instructions

## Project Overview
Video Game Course Platform v2 - Educational LMS for Prosper ISD video game development courses.

## Tech Stack
- **Backend:** Django 4.2 LTS + Django REST Framework + PostgreSQL 16
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS
- **Auth:** django-allauth + dj-rest-auth

## Development Practices

### Parallel Agent Execution (3-Agent Workflow)
Claude Code supports running multiple agents concurrently to speed up development. The recommended **3-Agent Workflow** for implementing phases:

**Agent 1: Backend Development**
- Django models, migrations, serializers
- API views and URL routing
- Permission checks and validation

**Agent 2: Frontend Development**
- React components and pages
- TypeScript types and interfaces
- Service functions for API calls

**Agent 3: Testing & Validation**
- TypeScript compilation check (`npx tsc --noEmit`)
- Backend restart if needed (`docker compose restart backend`)
- Manual testing verification

**Execution Pattern:**
1. Launch Backend + Frontend agents in parallel for independent work
2. Wait for both to complete
3. Run Testing agent to validate integration
4. Fix any compilation or runtime errors
5. Update documentation (PLAN.md, phase plan file)

### Code Style
- **Python:** Follow PEP 8, use type hints where helpful
- **TypeScript:** Strict mode, explicit types for props and state
- **Components:** Functional components with hooks
- **Tests:** pytest for backend, focus on API endpoint coverage

### Project Structure
```
backend/
├── accounts/     # User model, auth, preferences
├── courses/      # Courses, units, lessons, enrollments, gradebook
├── assignments/  # Assignments, submissions, grades
├── quizzes/      # Quizzes, questions, attempts
└── notifications/ # Real-time notifications

frontend/src/
├── components/   # Reusable UI components
├── pages/        # Route pages (student, instructor)
├── services/     # API service functions
├── contexts/     # React contexts (Auth, Theme)
└── types/        # TypeScript type definitions
```

### API Conventions
- REST endpoints under `/api/`
- Course-specific routes use course code: `/api/courses/{code}/...`
- Instructor-only endpoints check `request.user == course.instructor`
- Student endpoints check enrollment via `Enrollment.objects.filter(...)`

### Testing
```bash
# Backend tests
cd backend && pytest

# Frontend type check
cd frontend && npx tsc --noEmit
```

### Common Patterns

**Django View with Permission Check:**
```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_view(request, course_code):
    course = get_object_or_404(Course, code=course_code)
    if request.user != course.instructor:
        return Response({'error': 'Forbidden'}, status=403)
    # ... rest of view
```

**React Service Pattern:**
```typescript
export const myService = {
  async getData(id: number): Promise<MyType> {
    const response = await api.get<MyType>(`/endpoint/${id}/`);
    return response.data;
  },
};
```

### Phase Completion Workflow

When completing a phase from PLAN.md, follow this checklist:

1. **Implementation**
   - Use 3-Agent Workflow (Backend + Frontend + Testing)
   - Ensure all features listed in the phase are implemented
   - Handle edge cases and error states

2. **Validation**
   - TypeScript compiles without errors: `cd frontend && npx tsc --noEmit`
   - Backend runs without errors: `docker compose restart backend`
   - Test key user flows manually

3. **Documentation Updates**
   - Update PLAN.md:
     - Change phase status from "In Progress" to "✅ Complete"
     - Add completion notes if needed
   - Update phase plan file in `~/.claude/plans/`:
     - Mark all success criteria as checked
     - Document any bug fixes applied
     - List all files created/modified
   - Update Troubleshooting.md with any issues encountered

4. **Cleanup**
   - Remove any debug logging
   - Ensure no commented-out code remains
   - Verify all imports are used

### Current Phase
Phase 12.5: Quiz Integration & Grading Polish ✅ Complete
- Quiz scores in gradebook
- Weighted grading system
- Student grade average display
- Quick grade (inline cell editing)

**Next Phase:** Phase 13 - Discussion Forums
