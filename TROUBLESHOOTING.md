# Troubleshooting Guide

This document captures issues encountered during development and their solutions. Use this as a reference when the standard setup process doesn't work as expected.

---

## Phase 1: Foundation Issues

### Issue 1: Missing `requests` Module

**Symptom:**
```
ModuleNotFoundError: No module named 'requests'
```

**Cause:**
The `django-allauth` package requires `requests` for OAuth/social authentication features, but it's not automatically installed as a dependency.

**Solution:**
Add `requests` to `backend/requirements.txt`:
```
# Authentication
django-allauth==65.3.0
dj-rest-auth==7.0.1
requests>=2.31.0  # Required by allauth for OAuth
```

Then rebuild the backend container:
```bash
docker compose down backend
docker compose build --no-cache backend
docker compose up -d backend
```

---

### Issue 2: Missing Migrations Folders

**Symptom:**
```
django.db.utils.ProgrammingError: relation "accounts_user" does not exist
```

**Cause:**
The Django apps (`accounts`, `courses`, `assignments`) were created without migrations folders, so Django couldn't create the database tables.

**Solution:**
1. Create migrations folders for each app:
```bash
mkdir -p backend/accounts/migrations
mkdir -p backend/courses/migrations
mkdir -p backend/assignments/migrations

touch backend/accounts/migrations/__init__.py
touch backend/courses/migrations/__init__.py
touch backend/assignments/migrations/__init__.py
```

2. Generate initial migrations:
```bash
docker compose run --rm backend python manage.py makemigrations accounts
docker compose run --rm backend python manage.py makemigrations courses
docker compose run --rm backend python manage.py makemigrations assignments
```

3. Apply migrations:
```bash
docker compose run --rm backend python manage.py migrate
```

---

### Issue 3: Migration Order Dependencies

**Symptom:**
```
psycopg.errors.UndefinedTable: relation "accounts_user" does not exist
```
This occurs during `migrate` even after creating migrations.

**Cause:**
Django's built-in `auth` app and `allauth` migrations reference the custom User model, but the `accounts` app migrations haven't been created yet. Django tries to run allauth migrations before the User table exists.

**Solution:**
1. Stop the backend container (it will crash on migrate):
```bash
docker compose down backend
```

2. Create migrations manually using `docker compose run` (doesn't auto-run migrate):
```bash
docker compose run --rm backend python manage.py makemigrations accounts
```

3. Apply all migrations:
```bash
docker compose run --rm backend python manage.py migrate
```

4. Start the backend normally:
```bash
docker compose up -d backend
```

---

### Issue 4: Docker Compose Command Not Found

**Symptom:**
```
command not found: docker-compose
```

**Cause:**
Newer Docker installations use `docker compose` (with a space) instead of `docker-compose` (with a hyphen).

**Solution:**
Use the new syntax:
```bash
# Old syntax (deprecated)
docker-compose up -d

# New syntax
docker compose up -d
```

---

### Issue 5: Version Attribute Warning

**Symptom:**
```
level=warning msg="docker-compose.yml: the attribute `version` is obsolete"
```

**Cause:**
Docker Compose V2 no longer requires the `version` attribute in `docker-compose.yml`.

**Solution:**
Remove the version line from `docker-compose.yml`:
```yaml
# Remove this line:
version: "3.9"

# Keep the rest:
services:
  db:
    ...
```

This is just a warning and doesn't affect functionality.

---

## Alternative Setup: Running Without Docker

If Docker issues persist, you can run the backend locally:

### 1. Set Up Python Virtual Environment
```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Start PostgreSQL (using Docker for just the database)
```bash
docker compose up -d db redis
```

### 3. Create `.env` file in backend folder
```bash
# backend/.env
DEBUG=True
DB_NAME=gamedev_db
DB_USER=gamedev_user
DB_PASSWORD=devpassword
DB_HOST=localhost
DB_PORT=5432
SECRET_KEY=dev-secret-key-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
ACCOUNT_EMAIL_VERIFICATION=optional
```

### 4. Run Migrations and Start Server
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

### 5. Run Frontend Separately
```bash
cd frontend
npm install
npm run dev
```

---

## Alternative Setup: Running Frontend Without Docker

If the frontend container has issues:

```bash
cd frontend
npm install
npm run dev -- --host
```

The `--host` flag allows access from other devices on the network.

---

## Database Reset

If you need to start fresh with the database:

```bash
# Stop all containers
docker compose down

# Remove the database volume
docker volume rm gamedev-platform-v2_postgres_data

# Start fresh
docker compose up -d db redis
docker compose run --rm backend python manage.py makemigrations
docker compose run --rm backend python manage.py migrate
docker compose up -d backend frontend
```

---

## Checking Logs

### View all logs
```bash
docker compose logs -f
```

### View specific service logs
```bash
docker compose logs backend -f
docker compose logs frontend -f
docker compose logs db -f
```

### View last N lines
```bash
docker compose logs backend --tail 50
```

---

## Common API Testing Commands

### Test health endpoint
```bash
curl http://localhost:8000/api/health/
```

### Test registration
```bash
curl -X POST http://localhost:8000/api/auth/registration/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password1":"TestPass1234","password2":"TestPass1234"}'
```

### Test login
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass1234"}'
```

### Test authenticated endpoint
```bash
curl http://localhost:8000/api/auth/user/ \
  -H "Authorization: Token YOUR_TOKEN_HERE"
```

---

## Environment Variables Quick Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `True` | Django debug mode |
| `DB_HOST` | `localhost` | Database host (use `db` in Docker) |
| `DB_PORT` | `5432` | Database port |
| `DB_NAME` | `gamedev_db` | Database name |
| `DB_USER` | `gamedev_user` | Database user |
| `DB_PASSWORD` | `devpassword` | Database password |
| `SECRET_KEY` | (required) | Django secret key |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Allowed frontend origins |
| `EMAIL_BACKEND` | `console` | Email backend for dev |
| `ACCOUNT_EMAIL_VERIFICATION` | `optional` | `optional` or `mandatory` |
| `SENTRY_DSN` | (empty) | Sentry DSN for error tracking |
| `VITE_API_URL` | `http://localhost:8000/api` | Frontend API URL |
| `VITE_SENTRY_DSN` | (empty) | Frontend Sentry DSN |

---

## Phase 3: Video & Progress Issues

### Issue 6: YouTube IFrame API Loading

**Symptom:**
YouTube player doesn't load or shows console errors about `YT` being undefined.

**Cause:**
The YouTube IFrame API script hasn't finished loading before the player tries to initialize.

**Solution:**
The YouTubePlayer component uses a callback-based initialization:
1. Loads the IFrame API script dynamically
2. Sets up `window.onYouTubeIframeAPIReady` callback
3. Creates player only after API is ready

If issues persist, ensure no ad blockers are blocking YouTube scripts.

---

## Phase 2: Courses & Enrollment Issues

### Issue 9: Cannot Create Units

**Symptom:**
Clicking "Add Unit" in the ManageCoursePage does nothing or returns an error.

**Cause:**
The frontend was calling the wrong API endpoint. It was calling `POST /courses/units/` with a course ID in the body, but that endpoint requires a different serializer. The correct endpoint is `POST /courses/courses/{code}/units/`.

**Solution:**
Fixed in `frontend/src/services/courses.ts`:
```typescript
// Before (wrong):
async createUnit(courseId: number, data: { title: string }) {
  return api.post('/courses/units/', { ...data, course: courseId });
}

// After (correct):
async createUnit(courseCode: string, data: { title: string }) {
  return api.post(`/courses/courses/${courseCode}/units/`, data);
}
```

Also update the call in ManageCoursePage to pass `course.code` instead of `course.id`.

---

### Issue 10: Cannot Create Lessons

**Symptom:**
Clicking "Add Lesson" in the ManageCoursePage does nothing or silently fails.

**Cause:**
The frontend was sending `null` for optional fields (`content` and `video_id`), but the Django model fields are defined with `blank=True` but NOT `null=True`. This means they accept empty strings but reject NULL values.

**Solution:**
Fixed in `frontend/src/pages/instructor/ManageCoursePage.tsx`:
```typescript
// Before (wrong - sends null):
const lessonData = {
  title: editingLesson.title,
  content: editingLesson.content || null,
  video_type: editingLesson.video_type,
  video_id: editingLesson.video_id || null,
  order: editingLesson.order,
};

// After (correct - sends empty strings):
const lessonData = {
  title: editingLesson.title,
  content: editingLesson.content || '',
  video_type: editingLesson.video_type,
  video_id: editingLesson.video_id || '',
  order: editingLesson.order,
};
```

Also added error display to the lesson modal to show backend validation errors:
```tsx
{lessonError && (
  <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-4 py-3 text-sm">
    {lessonError}
  </div>
)}
```

---

## Phase 4: Assignments Issues

### Issue 8: "assignments" App Name Conflict

**Symptom:**
```
CommandError: 'assignments' conflicts with the name of an existing Python module
```

**Cause:**
There's a Python package named `assignments` that conflicts with the app name.

**Solution:**
The app was already scaffolded earlier. Check if directory exists:
```bash
ls backend/assignments/
```
If it exists, proceed with implementing the models. No need to run `startapp`.

---

### Issue 11: Video Stutter When Progress Saves

**Symptom:**
Video playback stutters/pauses every 10 seconds when progress is saved.

**Cause:**
The progress saving used React state (`setIsSavingProgress`) which caused component re-renders, affecting the YouTube player.

**Solution:**
Changed from state to refs for tracking save status to avoid re-renders:
```typescript
// Before (causes re-renders):
const [isSavingProgress, setIsSavingProgress] = useState(false);
setIsSavingProgress(true);
// ...
setIsSavingProgress(false);

// After (no re-renders):
const isSavingRef = useRef(false);
isSavingRef.current = true;
// ...
isSavingRef.current = false;
```

Also removed the "Saving..." indicator since it's no longer tracked via state.

---

### Issue 12: YouTube URL Must Be Manually Parsed

**Symptom:**
Instructors must manually extract the video ID from YouTube URLs.

**Solution:**
Added automatic YouTube URL extraction that supports multiple formats:
```typescript
function extractYouTubeVideoId(input: string): string {
  const patterns = [
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
    /^([a-zA-Z0-9_-]{11})$/,
  ];
  // ...
}
```

Supports:
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/embed/VIDEO_ID`
- Just the ID itself

---

### Issue 13: Video Not Fitting Container

**Symptom:**
YouTube video displays with black bars on the right side, not filling the container.

**Cause:**
The YouTube IFrame API doesn't automatically make the player responsive.

**Solution:**
Added width/height to player config and CSS to ensure iframe fills container:
```typescript
// In YouTubePlayer.tsx
playerRef.current = new window.YT.Player(playerIdRef.current, {
  videoId,
  width: '100%',
  height: '100%',
  // ...
});

// Container CSS
className="aspect-video bg-black rounded-lg overflow-hidden [&>div]:w-full [&>div]:h-full [&_iframe]:w-full [&_iframe]:h-full"
```

---

### Issue 14: Drag-to-Reorder Removed

**Decision:**
Removed drag-to-reorder functionality from ManageCoursePage as it was not needed for MVP.

**Changes:**
- Removed `GripVertical` icons from units and lessons
- Removed the import from lucide-react

Note: The backend `reorder` endpoints still exist if this feature is added later.

---

### Issue 15: Assignment Submission Form Not Showing

**Symptom:**
Students viewing an assignment see "Your Submission" section but no form to submit.

**Cause:**
The `canEdit` check only allowed editing if a submission already existed with status 'draft':
```typescript
const canEdit = submission?.status === 'draft';
```

If no submission existed yet, `submission` was `null`, so `canEdit` was `false`.

**Solution:**
Updated the logic to allow submission when no submission exists OR when status is draft:
```typescript
const canEdit = !submission || submission.status === 'draft';
```

---

### Issue 16: No File Upload Option for Assignments

**Symptom:**
Students could only submit text, not files.

**Solution:**
Added file upload UI to AssignmentDetailPage:
- File input with drag-and-drop styling
- Display selected file with remove option
- Include file in submission API call
- Show file link in submitted view

---

### Issue 17: Auto-Save for Assignment Submissions

**Improvement:**
Replaced manual "Save Draft" button with automatic saving to prevent data loss.

**Implementation:**
- Auto-save triggers 2 seconds after user stops typing
- Uses refs to track save state without causing re-renders
- Shows "Saving...", "Saved", or error status
- Only saves when content has actually changed

```typescript
// Debounced auto-save effect
useEffect(() => {
  autoSaveTimeoutRef.current = window.setTimeout(() => {
    performAutoSave(content);
  }, 2000);
  // ...
}, [content, ...]);
```

---

### Issue 18: Grade Display Hard to Read (Dark Green)

**Symptom:**
The graded assignment display used dark green background that was hard to read in dark mode.

**Solution:**
Changed to lighter, more readable styling:
```typescript
// Before
className="mb-6 border-green-200 bg-green-50 dark:bg-green-950 dark:border-green-800"

// After
className="mb-6 border-green-500 bg-green-50 dark:bg-green-900/20 dark:border-green-600"
```

Also updated text colors to use explicit green shades that work in both light and dark modes.

---

### Issue 19: Multiple File Uploads (Max 3)

**Requirement:**
Students should be able to upload up to 3 files per submission.

**Implementation:**
- Created new `SubmissionFile` model for storing multiple files
- Updated backend to handle multiple file uploads via `files` field
- Updated frontend to show existing files, new files, and allow deletion
- Added visual indicators: existing files (gray), new files (blue with "new" tag)
- Shows remaining file slots: "Click to upload (X remaining)"

**Migration:**
```bash
docker compose run --rm backend python manage.py makemigrations assignments
docker compose run --rm backend python manage.py migrate
```

---

### Issue 20: Allow Resubmission Feature

**Requirement:**
Instructors should be able to let students resubmit their assignments.

**Implementation:**
- Added `POST /assignments/submissions/{id}/allow-resubmit/` endpoint
- Resets submission status to 'draft'
- Deletes existing grade
- Added "Allow Resubmission" button on GradingPage
- Submission removed from grading list after allowing resubmit

---

### Issue 21: Save Submission on Page Leave

**Requirement:**
Student submissions should be saved when they leave the page to prevent data loss.

**Implementation:**
- Added `beforeunload` and `visibilitychange` event listeners
- Uses `navigator.sendBeacon()` for reliable save on page close
- Falls back to sync XHR if beacon fails
- Only saves if content has changed from last saved version
- Tracks last saved content with a ref to avoid duplicate saves

```typescript
// Save on page leave
useEffect(() => {
  const handleVisibilityChange = () => {
    if (document.visibilityState === 'hidden') {
      saveOnLeave();
    }
  };
  const handleBeforeUnload = () => {
    saveOnLeave();
  };
  // ...
}, [content, assignment, submission]);
```

---

### Issue 22: Submission History for Instructors

**Requirement:**
Instructors should be able to see previous submissions when a student resubmits.

**Implementation:**
- Created `SubmissionHistory` model to archive past submissions
- When "Allow Resubmission" is clicked, the current submission is archived
- Archives include: content, submitted_at, grade_points, grade_feedback
- GradingPage shows collapsible "Previous Submissions" section
- Each archived submission shows content and grade if it was graded

**Backend changes:**
- Added `SubmissionHistory` model in `assignments/models.py`
- Added `SubmissionHistorySerializer` in `assignments/serializers.py`
- Updated `allow_resubmission` view to archive before reset
- Updated `SubmissionSerializer` to include `history` field

**Frontend changes:**
- Added `history` field to `Submission` type
- Added collapsible history section in GradingPage
- Shows submission number, date, content, and grade for each entry

**Migration:**
```bash
docker compose run --rm backend python manage.py makemigrations assignments
docker compose run --rm backend python manage.py migrate
```

---

### Issue 23: Submission History Not Showing File Attachments

**Symptom:**
When instructors view previous submissions (resubmission history), the attached files from those submissions are not shown.

**Cause:**
The `SubmissionHistory` model didn't track file attachments from archived submissions.

**Solution:**
Added `files_info` JSONField to `SubmissionHistory` model to store file names:
- Backend: Added `files_info = models.JSONField(default=list, blank=True)` to model
- Updated `allow_resubmission` view to archive file names before resetting
- Updated `SubmissionHistorySerializer` to include `files_info`
- Updated GradingPage to display archived file names in history

**Migration:**
```bash
docker compose run --rm backend python manage.py makemigrations assignments
docker compose run --rm backend python manage.py migrate
```

---

### Issue 24: Rename "Text" Submission to "Comments"

**Improvement:**
Changed submission UI to make files the primary submission method and text/content as optional comments.

**Changes:**
- Files section moved to top with clear "Upload Files (max 3)" label
- Added accepted file types description: Images, Documents, Archives, Code files
- Added `accept` attribute to file input for type filtering
- Text field renamed to "Comments (optional)" with smaller height
- Instructor grading view updated to show files first, then comments
- Submitted view updated similarly

---

### Issue 25: Students Could See All Courses Without Enrollment

**Symptom:**
Students clicking "Courses" in the navbar could see all available courses and potentially enroll without a code by clicking on a course card.

**Cause:**
The `CourseViewSet.get_queryset()` returned all active courses for non-instructor users.

**Solution:**
Updated the backend to only return enrolled courses for students:
```python
def get_queryset(self):
    if self.request.user.is_instructor:
        # Instructors see all courses
        return queryset
    else:
        # Students only see courses they are enrolled in
        enrolled_course_ids = Enrollment.objects.filter(
            user=self.request.user
        ).values_list('course_id', flat=True)
        return queryset.filter(id__in=enrolled_course_ids, is_active=True)
```

Also updated the frontend:
- Page title: "My Courses" for students, "All Courses" for instructors
- Empty state: "You are not enrolled in any courses yet" with enroll button
- Students can only enroll via the "Enroll with Code" button

---

## Phase 5: Notifications

Phase 5 implements real-time notifications for course events.

### Notification Types

**For Instructors:**
- **enrollment** - When a student enrolls in their course
- **submission** - When a student submits an assignment

**For Students:**
- **new_lesson** - When instructor adds a new lesson to an enrolled course
- **new_assignment** - When instructor adds a new assignment to an enrolled course
- **grade** - When their assignment is graded
- **resubmission** - When instructor allows them to resubmit

### Backend Implementation
- `Notification` model with recipient, type, title, message, is_read, related_url
- Django signals auto-create notifications on Enrollment, Submission (status=submitted), and Grade creation
- API endpoints:
  - `GET /api/notifications/` - List user's notifications
  - `GET /api/notifications/unread-count/` - Get unread count
  - `POST /api/notifications/{id}/read/` - Mark single as read
  - `POST /api/notifications/mark-all-read/` - Mark all as read

### Frontend Implementation
- `NotificationBell` component in header with:
  - Badge showing unread count
  - Dropdown with notification list
  - Auto-refresh every 30 seconds
  - Click to navigate to related content
  - Mark as read / mark all read functionality
  - Emoji icons for notification types

---

## Running Tests

### All Backend Tests
```bash
docker compose exec backend pytest -v
```

### Specific App Tests
```bash
docker compose exec backend pytest accounts/tests.py -v
docker compose exec backend pytest courses/tests.py -v
docker compose exec backend pytest assignments/tests.py -v
```

### Test Coverage
```bash
docker compose exec backend pytest --cov=. --cov-report=term-missing
```

---

---

## Phase 6: Polish & Deploy

### Dynamic Dashboard Stats

Added real-time statistics to the Dashboard:

**For Instructors:**
- Pending Grades: count of submissions awaiting grading
- Total Students: across all courses

**For Students:**
- Lessons Completed: total completed lessons
- Assignments Due: count of assignments due in next 7 days

**Endpoint:** `GET /api/courses/dashboard/stats/`

---

### Production Docker Setup

Created production-ready Docker configuration:

**Files added:**
- `docker-compose.prod.yml` - Production compose file with nginx reverse proxy
- `backend/Dockerfile.prod` - Production backend with gunicorn
- `frontend/Dockerfile.prod` - Multi-stage build for optimized frontend
- `frontend/nginx.conf` - Frontend nginx config for SPA routing
- `nginx/nginx.conf` - Main reverse proxy config

**To deploy:**
```bash
# Set production environment variables
cp .env.example .env
# Edit .env with production values

# Build and start
docker compose -f docker-compose.prod.yml up -d --build
```

**Production checklist:**
- [ ] Set `DEBUG=False`
- [ ] Generate secure `SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS` with your domain
- [ ] Set up SSL certificates in `nginx/ssl/`
- [ ] Configure email settings for password reset
- [ ] Set up Sentry for error tracking

---

---

## Phase 10: Assignment Availability & Late Penalties

### Issue 26: Empty Strings for Date Fields Causing 400 Errors

**Symptom:**
Creating assignments fails with "Datetime has wrong format" error.

**Cause:**
The frontend sends empty strings `""` for optional date fields (`due_date`, `available_from`, `available_until`), but Django REST Framework's DateTimeField rejects empty strings before custom validation runs.

**Solution:**
Created a custom `EmptyStringToNullDateTimeField` that converts empty strings to `None`:
```python
class EmptyStringToNullDateTimeField(serializers.DateTimeField):
    """DateTimeField that converts empty strings to None."""
    def to_internal_value(self, value):
        if value == '' or value is None:
            return None
        return super().to_internal_value(value)
```

Used this field in `AssignmentCreateUpdateSerializer`:
```python
class AssignmentCreateUpdateSerializer(serializers.ModelSerializer):
    due_date = EmptyStringToNullDateTimeField(required=False, allow_null=True)
    available_from = EmptyStringToNullDateTimeField(required=False, allow_null=True)
    available_until = EmptyStringToNullDateTimeField(required=False, allow_null=True)
```

---

### Issue 27: Poor Text Contrast in Alert Boxes (Light Mode)

**Symptom:**
Text in yellow/amber warning boxes (Late Submission Policy, Late Penalty Applied) is barely visible in light mode.

**Cause:**
Tailwind's yellow color classes (`text-yellow-700`, `bg-yellow-50`) have poor contrast. The CSS variables or theme may also override these colors.

**Solution:**
Use inline styles with explicit hex colors for guaranteed contrast:
```tsx
// Before (hard to read)
<div className="bg-yellow-50 text-yellow-700">

// After (guaranteed contrast)
<div style={{ backgroundColor: '#fef3c7', border: '1px solid #f59e0b' }}>
  <p style={{ color: '#78350f' }}>
```

Colors used:
- **Amber/Yellow boxes**: Background `#fef3c7`, Border `#f59e0b`, Text `#78350f` / `#92400e`
- **Red warning boxes**: Background `#fee2e2`, Border `#ef4444`, Text `#7f1d1d` / `#991b1b`

---

### Issue 28: Students Notified About Unavailable Assignments

**Symptom:**
Students receive notifications for assignments that have `available_from` set in the future.

**Cause:**
The `notify_students_on_new_assignment` signal didn't check if the assignment was available.

**Solution:**
Added availability check in `notifications/signals.py`:
```python
@receiver(post_save, sender=Assignment)
def notify_students_on_new_assignment(sender, instance, created, **kwargs):
    if created:
        # Don't notify if assignment is not yet available
        if not instance.is_available:
            return
        # ... rest of notification logic
```

---

### Issue 29: Sidebar Shows Original Grade Instead of Final Grade

**Symptom:**
In the GradingPage sidebar, graded submissions show original points (e.g., "100/100") instead of final grade after late penalty (e.g., "80/100").

**Cause:**
The sidebar displayed `submission.grade.points` instead of `submission.final_grade`.

**Solution:**
Updated GradingPage.tsx to use `final_grade`:
```tsx
// Before
{submission.grade.points}/{assignment.max_points} pts

// After
{submission.final_grade !== null && submission.final_grade !== undefined
  ? submission.final_grade
  : submission.grade.points}/{assignment.max_points} pts
```

---

### Issue 30: Gradebook and Course Page Show Raw Grade Instead of Final Grade

**Symptom:**
The gradebook shows the original grade (e.g., 100/100) instead of the final grade after late penalty (e.g., 80/100). Same issue on the course detail page's assignment list.

**Cause:**
Both the gradebook endpoint and `AssignmentListSerializer.get_submission_status()` were using `submission.grade.points` without subtracting `submission.late_penalty_applied`.

**Solution:**
Updated both locations to calculate final grade:

In `courses/views.py` (gradebook endpoint):
```python
# Before
points = submission.grade.points

# After
raw_points = submission.grade.points
late_penalty = float(submission.late_penalty_applied or 0)
final_points = max(0, raw_points - late_penalty)
```

In `assignments/serializers.py` (get_submission_status):
```python
# Before
'grade': submission.grade.points if hasattr(submission, 'grade') else None

# After
grade = None
if hasattr(submission, 'grade'):
    raw_points = submission.grade.points
    late_penalty = float(submission.late_penalty_applied or 0)
    grade = max(0, raw_points - late_penalty)
```

---

## Phase 11: User Settings & Preferences

### Issue 31: Theme Persists Across User Logins

**Symptom:**
When User A sets dark mode, logs out, and User B logs in, User B sees dark mode instead of their own preference. The theme setting is shared between all users on the same browser.

**Cause:**
The theme was stored in `localStorage`, which persists across all sessions on the same browser. The theme should be personalized per user (stored in backend `UserPreferences`).

**Solution:**
Updated theme management to be user-specific:

1. **ThemeContext changes:**
   - Added `resetTheme()` function that clears localStorage and resets to 'system'
   - Updated `setTheme()` to accept optional `persist` parameter
   - Theme in localStorage is only for guest/pre-login preference

2. **AuthContext changes:**
   - On login: Load user's theme from `user.preferences.theme` and apply it (without persisting to localStorage)
   - On logout: Call `resetTheme()` to clear theme and reset to 'system'

3. **Login/Register pages:**
   - Added theme toggle button in top-right corner
   - Allows users to switch between light/dark/system before logging in
   - This guest preference is stored in localStorage until they log in

**Files changed:**
- `frontend/src/contexts/ThemeContext.tsx` - Added `resetTheme()`, updated `setTheme()`
- `frontend/src/contexts/AuthContext.tsx` - Apply user theme on login, reset on logout
- `frontend/src/pages/auth/LoginPage.tsx` - Added theme toggle button
- `frontend/src/pages/auth/RegisterPage.tsx` - Added theme toggle button

---

## Phase 12.5: Quiz Integration & Grading Polish

### Issue 32: Quiz Model Has No due_date Field

**Symptom:**
```
AttributeError: 'Quiz' object has no attribute 'due_date'
```
500 Internal Server Error when accessing `/api/courses/{code}/my-grades/`

**Cause:**
The student grades endpoint was trying to access `quiz.due_date`, but the Quiz model doesn't have a due_date field (unlike Assignments).

**Solution:**
Removed all references to `quiz.due_date` in the grades endpoint:
```python
# WRONG
'due_date': quiz.due_date

# CORRECT
'due_date': None  # Quizzes don't have due dates
```

---

### Issue 33: QuizAttempt Has No started_at Field

**Symptom:**
```
AttributeError: 'QuizAttempt' object has no attribute 'started_at'
```

**Cause:**
The grades endpoint was referencing `best_attempt.started_at`, but QuizAttempt only has `completed_at`.

**Solution:**
Use `completed_at` instead:
```python
# WRONG
'submitted_at': best_attempt.started_at

# CORRECT - QuizAttempt only has completed_at
# Remove the reference or use completed_at for display purposes
```

---

### Issue 34: StudentGradeCard Returns Null on Error

**Symptom:**
The "My Grades" card doesn't appear on the course detail page when the API fails.

**Cause:**
The StudentGradeCard component returned `null` when `error` was set or `grades` was null, hiding the entire card.

**Solution:**
Always show the card with at least a link to the full grades page:
```typescript
// WRONG: Hides card completely on error
if (error || !grades) {
  return null;
}

// CORRECT: Always show card with fallback
if (error || !grades) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <TrendingUp className="h-5 w-5" />
          My Grades
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-4">
          {error || 'View your grades and progress in this course.'}
        </p>
        <Link to={`/courses/${courseCode}/grades`}>
          <Button variant="outline" className="w-full justify-between">
            View All Grades
            <ChevronRight className="h-4 w-4" />
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}
```

---

### Issue 35: Unavailable Assignments Showing in Grade Items

**Symptom:**
Students see assignments in their grades list that have `available_from` set in the future.

**Cause:**
The my-grades endpoint wasn't filtering out assignments where `available_from > now`.

**Solution:**
Add availability check before adding to grade items:
```python
now = timezone.now()
for assignment in all_assignments:
    # Skip assignments not available yet
    if assignment.available_from and assignment.available_from > now:
        continue
    # ... process visible assignments
```

---

### Issue 36: Inaccurate Status for Draft Submissions

**Symptom:**
Submissions with status 'draft' show as 'submitted' in the grades view.

**Cause:**
The status logic treated drafts the same as submitted:
```python
# WRONG
if submission:
    status = submission.status  # 'draft' treated as a real status
```

**Solution:**
Treat draft submissions as 'not_started' for display:
```python
# CORRECT
if submission and submission.status == 'graded':
    status = 'graded'
elif submission and submission.status == 'submitted':
    status = 'submitted'
elif submission and submission.status == 'draft':
    status = 'not_started'  # Draft = not yet submitted
elif is_past_due:
    status = 'missing'
else:
    status = 'not_started'
```

---

### Issue 37: Blank Quick Grade Input Causing Errors

**Symptom:**
Clicking on a grade cell, clearing it, and pressing Enter/clicking away causes an error.

**Cause:**
The EditableGradeCell component tried to submit an empty or unchanged value.

**Solution:**
Cancel gracefully when input is empty or unchanged:
```typescript
const handleSubmit = () => {
  const trimmedValue = inputValue.trim();

  // Cancel if empty or unchanged
  if (!trimmedValue || trimmedValue === String(currentValue ?? '')) {
    setIsEditing(false);
    setInputValue(String(currentValue ?? ''));
    return;
  }

  // ... continue with submission
};
```

---

*Last Updated: January 27, 2026*
