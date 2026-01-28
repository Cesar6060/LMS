# Video Game Course Platform - Rebuild Plan v2.1

## Overview

Strategy for rebuilding the Prosper ISD Video Game Development course platform from scratch.

| Current State | Target State (MVP) | Target State (Full) |
|---------------|-------------------|---------------------|
| 8 Django apps | 4 apps | 7 apps |
| 42+ models | 10 models | 20 models |
| 21 dependencies | 8 core + 3 Phase 5 | + recharts |
| Technical debt | Clean architecture | Teacher-focused LMS |

**MVP Status:** ✅ Complete (Phases 1-6)
**Extended Features:** Phases 7-12.5 ✅ Complete, Phases 13-15 Pending
**Compatibility Research Completed:** January 2026

---

## Part 1: Technology Stack (Validated Versions)

### Critical Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Python | **3.12.8** | Django 4.2 does NOT support 3.13 |
| Django | **4.2.27 LTS** | Security support until April 2026 |
| Database Driver | **psycopg3** | Recommended over psycopg2; better async |
| Auth | **django-allauth** | Email verification, password reset, social login built-in |
| React Router | **v7.x** | Stable Dec 2024; use `react-router` not `react-router-dom` |
| Axios | **1.13.2+** | ⚠️ Versions ≤1.7.x have critical SSRF vulnerabilities |
| Video | **YouTube/Vimeo embeds** | Zero infrastructure; upgrade to Mux/Cloudflare Stream later if needed |

### Backend Requirements

**requirements.txt (Phases 1-4)**
```
# Core Django
Django==4.2.27
djangorestframework==3.15.2
django-cors-headers==4.7.0

# Database
psycopg[binary,pool]==3.3.2

# Authentication
django-allauth==65.3.0
dj-rest-auth==7.0.1

# Files & Images
pillow==12.1.0

# Error Tracking
sentry-sdk[django]==2.19.2
```

**requirements.txt (Add in Phase 5)**
```
# WebSocket Support
channels[daphne]==4.2.0
channels-redis==4.3.0
redis==5.2.1
```

### Frontend Dependencies

**package.json dependencies**
```
react: 18.3.1
react-dom: 18.3.1
react-router: 7.12.0
axios: 1.13.2
react-markdown: 9.0.1
remark-gfm: 4.0.0
lucide-react: 0.562.0
@radix-ui/react-dialog: 1.1.15
@radix-ui/react-dropdown-menu: 2.1.15
@radix-ui/react-tabs: 1.1.12
```

**package.json devDependencies**
```
vite: 6.4.0
@vitejs/plugin-react: 4.4.0
typescript: 5.6.3
@types/react: 18.3.18
@types/react-dom: 18.3.5
@types/node: 22.15.0
tailwindcss: 3.4.17
postcss: 8.4.49
autoprefixer: 10.4.20
```

### Infrastructure (Local Development)

| Component | Version | Docker Image |
|-----------|---------|--------------|
| PostgreSQL | 16 | `postgres:16-alpine` |
| Redis | 7.2 | `redis:7.2-alpine` |
| Python | 3.12 | `python:3.12-slim` |
| Node.js | 22 LTS | `node:22-alpine` |

---

## Part 2: Architecture Decisions

### ADR-001: Authentication Strategy
- **Decision:** django-allauth + dj-rest-auth
- **Why:** Email verification, password reset, social login (Google) built-in
- **Benefit:** Saves 2-3 days of building auth flows manually
- **Rejected:** Basic DRF TokenAuth (no email verification, no password reset)

### ADR-002: Course Structure
- **Decision:** Course → Unit → Lesson hierarchy
- **Why:** Matches Canvas/Udemy mental model
- **Constraint:** No nested units for MVP

### ADR-003: Enrollment System
- **Decision:** 8-character alphanumeric codes
- **Why:** Easy to share verbally, type on mobile
- **Generation:** `secrets.token_urlsafe(6)`

### ADR-004: Video Strategy
- **Decision:** YouTube embeds only (MVP)
- **Why:** Zero infrastructure complexity; free; proven reliability
- **Deferred:** Direct video uploads (consider Cloudflare Stream or Mux in future)
- **Rationale:** For 150 students watching course videos, YouTube embeds are perfectly adequate
- **Note:** Vimeo support removed to simplify implementation

### ADR-005: Progress Tracking
- **Decision:** Track completion + video position per lesson
- **Sync:** Save position every 10 seconds (debounced)
- **Note:** YouTube/Vimeo APIs support position tracking

### ADR-006: Assignment Scope
- **Decision:** Assignments belong to Units
- **Why:** Groups related work; matches teacher organization

### ADR-007: Grading Model
- **Decision:** Simple points-based with feedback
- **Deferred:** Weighted grades, rubrics

### ADR-008: WebSocket Architecture
- **Decision:** Django Channels + Redis channel layer
- **Server:** Daphne (included with `channels[daphne]`)

### ADR-009: Notification Types (Phase 5)
1. New enrollment → instructor receives
2. Assignment submitted → instructor receives
3. Grade posted → student receives

### ADR-010: Error Tracking
- **Decision:** Sentry (free tier: 5K errors/month)
- **Why:** Know when things break in production; stack traces; user context
- **Setup:** Add to Django settings + frontend ErrorBoundary

### ADR-011: File Storage (Submissions)
- **Decision:** Local filesystem for MVP
- **Future:** Cloudflare R2 (free egress, $0.015/GB storage)
- **Why:** Simple for MVP; R2 is cheapest option when scaling

### ADR-012: Announcements (Phase 7)
- **Decision:** Add Announcement model to courses app
- **Why:** Teachers need class-wide communication daily
- **Email:** Optional per-announcement, sent synchronously for MVP

### ADR-013: Gradebook Architecture (Phase 8)
- **Decision:** Computed view, not stored separately
- **Why:** Grades already exist on submissions; avoid data duplication
- **Export:** CSV format for district compatibility

### ADR-014: Late Penalty System (Phase 10)
- **Decision:** Configurable per-assignment with stored penalty
- **Why:** Teachers need automatic late handling (Google Classroom pain point)
- **Storage:** Penalty stored separately from earned grade for transparency

### ADR-015: Quiz Architecture (Phase 12)
- **Decision:** Separate quizzes app, MVP with multiple choice only
- **Why:** Quizzes are auto-graded, distinct from manual assignments
- **Scope:** Simple first; add time limits/shuffling later

### ADR-016: Discussion Simplicity (Phase 13)
- **Decision:** Flat replies, no voting, no nesting
- **Why:** K-12 context doesn't need Reddit-style features
- **Future:** Can add complexity if teachers request it

---

## Part 3: Data Models

### App: accounts (1 model)

**User** (extends AbstractUser)
| Field | Type | Notes |
|-------|------|-------|
| email | EmailField | unique, USERNAME_FIELD |
| is_instructor | BooleanField | default=False |
| created_at | DateTimeField | auto_now_add |

*Note: django-allauth handles email verification, password reset automatically*

### App: courses (5 models)

**Course**
| Field | Type | Notes |
|-------|------|-------|
| code | CharField(10) | unique, e.g., "VGD101" |
| title | CharField(200) | |
| description | TextField | |
| instructor | FK → User | |
| enrollment_code | CharField(8) | unique, auto-generated |
| is_active | BooleanField | default=True |
| created_at | DateTimeField | |

**Unit**
| Field | Type | Notes |
|-------|------|-------|
| course | FK → Course | related_name='units' |
| title | CharField(200) | |
| order | PositiveIntegerField | |

**Lesson**
| Field | Type | Notes |
|-------|------|-------|
| unit | FK → Unit | related_name='lessons' |
| title | CharField(200) | |
| content | TextField | Markdown |
| order | PositiveIntegerField | |
| video_type | CharField(10) | choices: none/youtube/vimeo |
| video_id | CharField(50) | YouTube/Vimeo video ID, blank=True |

*Note: Simplified video fields—just store the video ID, not full URLs*

**Enrollment**
| Field | Type | Notes |
|-------|------|-------|
| user | FK → User | |
| course | FK → Course | |
| enrolled_at | DateTimeField | |
| | | unique_together: [user, course] |

**LessonProgress**
| Field | Type | Notes |
|-------|------|-------|
| user | FK → User | |
| lesson | FK → Lesson | |
| completed | BooleanField | default=False |
| completed_at | DateTimeField | null=True |
| video_position | PositiveIntegerField | seconds, default=0 |
| | | unique_together: [user, lesson] |

### App: assignments (3 models)

**Assignment**
| Field | Type | Notes |
|-------|------|-------|
| unit | FK → Unit | related_name='assignments' |
| title | CharField(200) | |
| description | TextField | |
| due_date | DateTimeField | |
| points | PositiveIntegerField | |

**Submission**
| Field | Type | Notes |
|-------|------|-------|
| assignment | FK → Assignment | |
| student | FK → User | |
| content | TextField | blank=True |
| file | FileField | upload_to='submissions/', blank=True |
| status | CharField(20) | choices: draft/submitted/graded |
| submitted_at | DateTimeField | |
| updated_at | DateTimeField | |
| | | unique_together: [assignment, student] |

**Grade**
| Field | Type | Notes |
|-------|------|-------|
| submission | OneToOne → Submission | |
| grader | FK → User | |
| points_earned | DecimalField(6,2) | |
| feedback | TextField | blank=True |
| graded_at | DateTimeField | |

### App: notifications (Phase 5, 1 model)

**Notification**
| Field | Type | Notes |
|-------|------|-------|
| recipient | FK → User | |
| type | CharField(50) | enrollment/submission/grade |
| title | CharField(200) | |
| message | TextField | |
| is_read | BooleanField | default=False |
| created_at | DateTimeField | |
| related_url | CharField(200) | optional deep link |

**Total: 4 apps, 10 models**

---

## Part 4: Project Structure

### Backend
```
gamedev_platform/
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py          # Phase 5
│   └── wsgi.py
├── accounts/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py         # Custom views (if needed beyond allauth)
│   ├── urls.py
│   └── tests.py
├── courses/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── permissions.py   # IsInstructor, IsEnrolledOrInstructor
│   └── tests.py
├── assignments/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   └── tests.py
├── notifications/        # Phase 5
│   ├── __init__.py
│   ├── models.py
│   ├── consumers.py
│   ├── routing.py
│   ├── signals.py
│   └── views.py
├── manage.py
├── requirements.txt
├── pytest.ini
└── Dockerfile
```

### Frontend
```
frontend/
├── src/
│   ├── components/
│   │   ├── ui/           # Button, Card, Input, Modal
│   │   ├── layout/       # Header, Sidebar, Layout
│   │   ├── course/       # CourseCard, LessonViewer, ProgressBar
│   │   └── video/        # YouTubePlayer, VimeoPlayer
│   ├── pages/
│   │   ├── auth/         # LoginPage, RegisterPage, ForgotPasswordPage, VerifyEmailPage
│   │   ├── student/      # DashboardPage, CoursesPage, CourseDetailPage, LessonPage
│   │   └── instructor/   # CreateCoursePage, ManageCoursePage, GradingPage
│   ├── contexts/
│   │   └── AuthContext.tsx
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   └── useWebSocket.ts   # Phase 5
│   ├── services/
│   │   ├── api.ts
│   │   ├── auth.ts
│   │   ├── courses.ts
│   │   └── assignments.ts
│   ├── types/
│   │   └── index.ts
│   ├── App.tsx
│   └── main.tsx
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
├── vite.config.ts
└── Dockerfile
```

---

## Part 5: API Endpoints

### Phase 1: Authentication (django-allauth + dj-rest-auth)

```
# Registration & Login
POST /api/auth/registration/              # Create account + send verification email
POST /api/auth/registration/verify-email/ # Verify email with key
POST /api/auth/login/                     # Get auth token
POST /api/auth/logout/                    # Invalidate token

# Password Management
POST /api/auth/password/reset/            # Send reset email
POST /api/auth/password/reset/confirm/    # Reset with token
POST /api/auth/password/change/           # Change password (authenticated)

# User Info
GET  /api/auth/user/                      # Get current user
PUT  /api/auth/user/                      # Update current user

# Social Auth (optional, configure in settings)
POST /api/auth/google/                    # Google OAuth login
```

### Phase 2: Courses & Enrollment
```
# Courses
GET    /api/courses/                     # List all active courses
POST   /api/courses/                     # Create course (instructor)
GET    /api/courses/{code}/              # Course detail with units/lessons
PUT    /api/courses/{code}/              # Update course (instructor)
DELETE /api/courses/{code}/              # Delete course (instructor)

# Units
POST   /api/courses/{code}/units/        # Add unit (instructor)
PUT    /api/units/{id}/                  # Update unit (instructor)
DELETE /api/units/{id}/                  # Delete unit (instructor)
PATCH  /api/units/{id}/reorder/          # Change order (instructor)

# Lessons
POST   /api/units/{id}/lessons/          # Add lesson (instructor)
GET    /api/lessons/{id}/                # Lesson detail (enrolled users)
PUT    /api/lessons/{id}/                # Update lesson (instructor)
DELETE /api/lessons/{id}/                # Delete lesson (instructor)
PATCH  /api/lessons/{id}/reorder/        # Change order (instructor)

# Enrollment
POST   /api/courses/{code}/enroll/       # Enroll with code
GET    /api/enrollments/                 # My enrolled courses
DELETE /api/enrollments/{id}/            # Unenroll
```

### Phase 3: Video & Progress
```
GET  /api/lessons/{id}/progress/         # Get my progress for lesson
POST /api/lessons/{id}/progress/         # Update progress (position, completed)
GET  /api/courses/{code}/progress/       # Overall course progress %
```

*Note: No video upload endpoint—using YouTube/Vimeo embeds only*

### Phase 4: Assignments
```
# Assignments
GET    /api/courses/{code}/assignments/  # List assignments in course
POST   /api/courses/{code}/assignments/  # Create assignment (instructor)
GET    /api/assignments/{id}/            # Assignment detail
PUT    /api/assignments/{id}/            # Update (instructor)
DELETE /api/assignments/{id}/            # Delete (instructor)

# Submissions
GET    /api/assignments/{id}/submission/    # Get my submission
POST   /api/assignments/{id}/submission/    # Create/update my submission
GET    /api/assignments/{id}/submissions/   # All submissions (instructor)

# Grading
POST   /api/submissions/{id}/grade/      # Grade submission (instructor)
PUT    /api/submissions/{id}/grade/      # Update grade (instructor)
GET    /api/grades/                      # My grades across all courses
```

### Phase 5: Notifications
```
GET  /api/notifications/                 # List my notifications (paginated)
POST /api/notifications/{id}/read/       # Mark as read
POST /api/notifications/read-all/        # Mark all as read
WS   /ws/notifications/                  # WebSocket for real-time
```

---

## Part 6: Phase Plans

### Phase 1: Foundation (Days 1-3)

**Goal:** Working authentication with django-allauth + React

#### Backend Tasks
- [x] Create Django project with `config/` directory
- [x] Configure PostgreSQL connection with psycopg3
- [x] Create `accounts` app with custom User model
- [x] Install and configure django-allauth:
  - [x] Email verification enabled
  - [x] Password reset enabled
  - [x] Configure email backend (console for dev)
- [x] Install and configure dj-rest-auth for API endpoints
- [x] Configure CORS for localhost:5173
- [x] Set up Sentry error tracking (basic config)
- [x] Write tests with pytest-django (target: 90% auth coverage)

#### Frontend Tasks
- [x] Create Vite + React + TypeScript project
- [x] Configure Tailwind CSS
- [x] Create AuthContext with login/logout/user state
- [x] Create api.ts with Axios + token interceptor
- [x] Build auth pages:
  - [x] LoginPage
  - [x] RegisterPage
  - [x] ForgotPasswordPage
  - [x] ResetPasswordPage
  - [x] VerifyEmailPage (handle email verification link)
- [x] Build DashboardPage ("Welcome, [name]")
- [x] Set up React Router with ProtectedRoute component
- [x] Add Sentry ErrorBoundary for frontend errors
- [x] Add loading states and error handling

#### Django Settings to Configure
```python
# Key allauth settings
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None

# dj-rest-auth settings
REST_AUTH = {
    'USE_JWT': False,  # Using token auth
    'TOKEN_MODEL': 'rest_framework.authtoken.models.Token',
}
```

#### Success Criteria
- [x] User registers → receives verification email
- [x] User verifies email → can log in
- [x] User logs in → sees personalized dashboard
- [x] User can request password reset → receives email → resets password
- [x] Token persists across browser refresh
- [x] Instructor vs student role displays correctly
- [x] Invalid credentials show error message
- [x] Errors are captured in Sentry

---

### Phase 2: Courses & Enrollment (Days 4-7) ✅ COMPLETE

**Goal:** Instructors create courses, students enroll and view content

#### Backend Tasks
- [x] Create `courses` app with all 5 models
- [x] Create permission classes: IsInstructor, IsEnrolledOrInstructor
- [x] Auto-generate enrollment codes on course creation
- [x] Course CRUD endpoints (instructor only for CUD)
- [x] Unit CRUD with reordering
- [x] Lesson CRUD with reordering
- [x] Enrollment endpoint with code validation
- [x] My enrollments endpoint
- [x] Register models in Django Admin
- [x] Write tests for all endpoints

#### Frontend Tasks
- [x] CoursesPage - Browse all active courses with search
- [x] CourseDetailPage - View units and lessons list
- [x] LessonPage - Markdown content viewer (react-markdown)
- [x] EnrollmentModal - Enter code, show success/error
- [x] Instructor: CreateCoursePage - Form with validation
- [x] Instructor: ManageCoursePage - Unit/lesson CRUD interface
- [x] Instructor: Inline markdown editor with preview
- [x] Add "My Courses" section to dashboard

#### Success Criteria
- [x] Instructor creates course → gets enrollment code
- [x] Instructor adds units successfully 
- [X] Instructor adds lessons with markdown editor 
- [x] Student enters code → enrolls successfully 
- [x] Student sees enrolled courses on dashboard 
- [X] Student views lesson content (markdown rendered) 
- [x] Non-enrolled users cannot access lesson content

---

### Phase 3: Video & Progress (Days 8-10) ✅ COMPLETE

**Goal:** Video lessons (YouTube embeds) with progress tracking

#### Backend Tasks
- [x] Ensure Lesson video fields work (video_type, video_id)
- [x] Create LessonProgress endpoints
- [x] Progress update (upsert pattern)
- [x] Course progress aggregation (% complete)
- [x] Write tests

#### Frontend Tasks
- [x] YouTubePlayer component:
  - [x] Use YouTube IFrame API
  - [x] Track current position
  - [x] Emit events: onPlay, onPause, onProgress, onEnd
- [x] VideoPlayer wrapper that renders correct player based on video_type
- [x] Progress bar component (shows % complete)
- [x] "Mark Complete" button on lessons
- [x] Auto-save video position every 10 seconds
- [x] Resume video from saved position on load
- [x] Instructor: Video type dropdown + video ID input in lesson editor
- [x] Course progress display on CourseDetailPage

*Note: Vimeo support removed to simplify implementation - YouTube only*

#### Video ID Extraction Helper
```
YouTube URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ
Video ID: dQw4w9WgXcQ
```

#### Success Criteria
- [X] YouTube videos play embedded in lesson
- [x] Video position saves every 10 seconds 
- [x] Reopening lesson resumes from last position
- [x] "Mark Complete" updates progress
- [x] Course shows "X% complete" accurately
- [x] Instructor can set video type and ID for lessons

---

### Phase 4: Assignments (Days 11-14) ✅ COMPLETE

**Goal:** Complete assignment workflow

#### Backend Tasks ✅ COMPLETE
- [x] Create `assignments` app with 3 models (Assignment, Submission, Grade)
- [x] Assignment CRUD (instructor only)
- [x] Submission create/update (students)
- [x] Prevent edit after grading (optional: allow resubmit)
- [x] Grade create/update (instructor)
- [x] List submissions for assignment (instructor)
- [x] File upload for submissions (local storage)
- [x] Write tests (25 tests passing)

#### Frontend Tasks ✅ COMPLETE
- [x] AssignmentDetailPage - View details + submission form
- [x] SubmissionForm - Text editor (file upload pending)
- [x] Status badges (draft / submitted / graded)
- [x] Due date display with countdown/overdue indicator
- [x] Instructor: Create assignment via ManageCoursePage
- [x] Instructor: GradingPage - List submissions, grade each
- [x] GradeDisplay - Show points + feedback to student
- [x] Add assignments to CourseDetailPage

#### Success Criteria
- [x] Instructor creates assignment with due date + points
- [x] Student views assignment details
- [x] Student submits text and/or file
- [x] Student can edit submission before grading
- [x] Instructor sees all submissions for assignment
- [x] Instructor grades with points + feedback
- [x] Student sees grade and feedback // Now its two light (Image attached)
- [x] Late submissions are flagged
- [x] Student can upload multiple files (max 3)
- [x] Student submission auto-saves while typing  
- [] Instructor should be able to see previous submissions
- [x] Instructor can allow student to resubmit
- [x] Files display correctly in grading view

---

### Phase 5: Notifications (Days 15-18)

**Goal:** Real-time notifications via WebSocket

#### Backend Tasks
- [ ] Add Channels + Redis to requirements
- [ ] Configure ASGI application
- [ ] Create `notifications` app with Notification model
- [ ] Create WebSocket consumer with token auth
- [ ] Create Django signals for notification triggers:
  - Enrollment created → notify instructor
  - Submission created → notify instructor
  - Grade created → notify student
- [ ] REST endpoints: list, mark read, mark all read
- [ ] Write tests

#### Frontend Tasks
- [ ] useWebSocket hook with:
  - Auto-connect on auth
  - Reconnection logic (exponential backoff)
  - Message handling
- [ ] NotificationBell in header
- [ ] Unread count badge
- [ ] NotificationDropdown - List with timestamps
- [ ] Mark as read on click
- [ ] Toast notification on new message
- [ ] Link to related content (assignment, grade, etc.)

#### Configuration Notes
- Daphne must be first in INSTALLED_APPS
- ASGI_APPLICATION = "config.asgi.application"
- CHANNEL_LAYERS with Redis backend
- WebSocket URL: /ws/notifications/

#### Success Criteria
- [x] WebSocket connects automatically on login
- [x] Grade posted → student sees notification instantly
- [x] Submission created → instructor sees notification
- [x] Enrollment → instructor notified
- [x] Bell shows unread count
- [x] Click notification → marks read + navigates
- [x] WebSocket reconnects on disconnect
- [x] Notifications persist (visible on refresh)

---

### Phase 6: Polish & Testing (Days 19-21)

**Goal:** Production-ready MVP

#### Backend Tasks
- [x] Docker Compose setup (Django + PostgreSQL + Redis)
- [x] Environment variables with python-decouple
- [x] Production settings checklist:
  - [x] DEBUG=False
  - [x] ALLOWED_HOSTS configured
  - [x] SECRET_KEY from environment
  - [x] SECURE_* settings for HTTPS
- [x] Static files with WhiteNoise
- [x] Media file serving configuration
- [x] Health check endpoint (/api/health/)
- [x] Seed data script for demo/testing
- [x] Verify Sentry captures errors correctly

#### Frontend Tasks
- [x] Production Vite build optimization
- [x] Error boundaries with Sentry integration
- [x] Loading skeletons (not just spinners)
- [x] 404 page
- [x] Generic error page
- [x] Responsive design audit (mobile breakpoints)
- [x] Accessibility: ARIA labels, keyboard navigation, focus states

#### Testing
- [x] Backend: pytest-django (target 80% coverage)
  - [x] Auth flows
  - [x] Course CRUD + permissions
  - [x] Enrollment flow
  - [x] Assignment submission + grading
- [x] Frontend: Test critical user flows
  - [x] Login/logout
  - [x] Course enrollment
  - [x] Lesson completion
  - [x] Assignment submission

#### Documentation
- [x] README with:
  - Prerequisites
  - Quick start (docker-compose up)
  - Environment variables
  - Development workflow
- [x] API documentation via DRF browsable API

#### Success Criteria
- [x] `docker-compose up` starts full stack
- [x] No console errors in production build
- [x] All tests pass
- [x] Sentry receiving errors correctly
- [x] Mobile layout works on 375px width
- [x] Documentation complete

---

## Part 6B: Extended Features (Post-MVP)

### Research Summary: What Teachers Actually Need

Based on analysis of Canvas, Google Classroom, Schoology, and teacher feedback:

#### Daily Use Features (Non-Negotiable)
| Feature | Why It Matters |
|---------|----------------|
| **Announcements** | Broadcast to all students + email notification |
| **Gradebook** | View all grades, calculate totals, export CSV |
| **Student Roster** | See enrolled students, track activity |
| **Due Dates + Availability** | "Until" date that closes submissions |
| **Late Submission Handling** | Flag late work, optional penalties |

#### Weekly Use Features (High Priority)
| Feature | Why It Matters |
|---------|----------------|
| **Bulk Enrollment** | Add multiple students via CSV |
| **Grade Export** | Export to CSV for district reporting |
| **Progress Tracking** | See who's falling behind |
| **Email Notifications** | Alert students about grades, deadlines |

#### Periodic Features (Nice to Have)
| Feature | Why It Matters |
|---------|----------------|
| **Dark Mode** | Accessibility, student preference |
| **Notification Settings** | Reduce alert fatigue |
| **Discussion Forums** | Peer support, Q&A |
| **Quizzes** | Knowledge checks |
| **Analytics Dashboard** | End-of-semester insights |

#### Teacher Pain Points (from research)
1. Google Classroom assignments never close → Need "available until" date
2. No student activity tracking → Need last active date
3. Limited gradebook → Need weighted categories, export
4. Notification overload → Need customizable settings
5. No dark mode → Accessibility issue
6. Late penalties are manual → Need automatic deduction option

---

### Phase 7: Announcements & Communication ✅ COMPLETE
**Priority:** 🔴 Critical (teachers need this daily)
**Status:** ✅ Complete

#### Implemented Features
- ✅ Announcement model with course, author, title, content, is_pinned, send_email
- ✅ Announcement CRUD (instructor only)
- ✅ List announcements with pin sorting
- ✅ Pin/unpin functionality
- ✅ AnnouncementsPage with list view
- ✅ AnnouncementDetailPage with markdown rendering
- ✅ Announcements section on CourseDetailPage
- ✅ Create/Edit/Delete announcements
- ✅ Notification created when announcement posted
- ✅ 13 tests for announcements

#### API Endpoints
```
GET    /api/courses/{code}/announcements/     # List
POST   /api/courses/{code}/announcements/     # Create (instructor)
GET    /api/announcements/{id}/               # Detail
PATCH  /api/announcements/{id}/               # Update (instructor)
DELETE /api/announcements/{id}/               # Delete (instructor)
POST   /api/announcements/{id}/pin/           # Pin (instructor)
POST   /api/announcements/{id}/unpin/         # Unpin (instructor)
```

#### Success Criteria
- [x] Instructor posts announcement → all enrolled students receive notification
- [x] Announcements display on course page (pinned first)
- [x] Students can view full announcement with markdown rendered
- [x] Instructor can edit/delete announcements
- [x] Instructor can pin/unpin announcements
- [x] Pinned announcements appear at top of list

---

### Phase 8: Gradebook & Grade Export ✅ COMPLETE
**Priority:** 🔴 Critical (teachers need this weekly)
**Status:** ✅ Complete

#### Implemented Features
- ✅ Gradebook endpoint with students × assignments matrix
- ✅ Total points, percentage, letter grade calculations (A/B/C/D/F scale)
- ✅ CSV export with all grade data
- ✅ GradebookPage with color-coded cells
- ✅ Missing (red), Late (yellow), Submitted (blue), Graded (green) indicators
- ✅ Export CSV button with auth token
- ✅ Summary stats (class average, total possible)
- ✅ Quick actions on ManageCoursePage
- ✅ 10 tests for gradebook

#### API Endpoints
```
GET /api/courses/{code}/gradebook/           # Full gradebook matrix
GET /api/courses/{code}/gradebook/export/    # CSV download
```

#### Success Criteria
- [x] Instructor sees all students × all assignments in one view
- [x] Totals calculate correctly (points earned / points possible)
- [x] Percentage and letter grade display correctly
- [x] Late submissions show yellow indicator
- [x] Missing submissions show red indicator
- [x] Graded submissions show green indicator
- [x] CSV export downloads with all grade data
- [x] Gradebook accessible from ManageCoursePage quick actions

---

### Phase 9: Student Roster & Activity Tracking ✅ COMPLETE
**Priority:** 🟠 High (teachers use weekly)
**Status:** ✅ Complete

#### Implemented Features
- ✅ Enrollment model with last_activity_at and is_active fields
- ✅ Student roster endpoint with activity data and progress percentage
- ✅ Activity tracking on course/lesson access
- ✅ Email invitation system (sends enrollment code via email)
- ✅ Soft-delete enrollment (preserves grades)
- ✅ StudentRosterPage with sortable/searchable table
- ✅ Relative time display ("5 minutes ago", "2 days ago")
- ✅ Activity status badges (Active/Inactive/Never Active)
- ✅ Remove student with confirmation dialog
- ✅ Stats cards (Total, Active, Inactive students)
- ✅ 11 tests for student roster

#### API Endpoints
```
GET    /api/courses/{code}/students/         # Student roster
POST   /api/courses/{code}/students/invite/  # Send email invitation
DELETE /api/courses/{code}/students/{id}/    # Remove student (soft)
POST   /api/courses/{code}/activity/         # Update activity timestamp
```

#### Email Invitation
Instead of bulk CSV enrollment, instructors can send email invitations containing:
- Course name and instructor name
- Enrollment code
- Links to register/enroll

**Note:** Email requires SMTP configuration (see Phase 15)

#### Success Criteria
- [x] Instructor sees all enrolled students with name, email, enrolled date
- [x] Last Active shows relative time ("5 minutes ago", "2 days ago", "Never")
- [x] Progress percentage displays for each student
- [x] Activity status badges show: Active (green), Inactive (red), Never Active (gray)
- [x] Stats cards show Total, Active, and Inactive student counts
- [x] Table is sortable by clicking column headers
- [x] Search filters students by name or email
- [x] Invite Student button opens modal to send email invitation
- [] Remove student shows confirmation dialog
- [x] Removing student preserves their grades (soft delete)
- [x] Student activity updates when they view course or lesson

---

### Phase 10: Assignment Availability & Late Policies (Days 35-38) ✅ COMPLETE
**Priority:** 🟠 High (daily teaching workflow)

**Goal:** Assignments can open/close on dates with automatic late penalties

#### Why Now?
Teachers need assignments to close after a deadline. Currently, students can submit forever. This is a top complaint about Google Classroom.

#### Features
1. **Available From** - Assignment becomes visible on this date
2. **Available Until** - Submissions close after this date
3. **Late Policy** - Auto-deduct percentage per day late
4. **Grace Period** - Optional buffer before late penalty

#### Model Updates

**Assignment** (add fields)
| Field | Type | Notes |
|-------|------|-------|
| available_from | DateTimeField | null=True (visible immediately if null) |
| available_until | DateTimeField | null=True (never closes if null) |
| late_penalty_percent | DecimalField(5,2) | null=True (e.g., 10 = 10% per day) |
| late_penalty_interval | CharField(10) | 'day' or 'hour', default='day' |
| max_late_penalty | DecimalField(5,2) | null=True (max % to deduct) |

**Submission** (add field)
| Field | Type | Notes |
|-------|------|-------|
| late_penalty_applied | DecimalField(5,2) | Points deducted for lateness |

#### Business Logic
```python
def calculate_late_penalty(submission, assignment):
    if not assignment.late_penalty_percent:
        return 0
    if not assignment.due_date or submission.submitted_at <= assignment.due_date:
        return 0

    if assignment.late_penalty_interval == 'hour':
        units_late = (submission.submitted_at - assignment.due_date).total_seconds() / 3600
    else:
        units_late = (submission.submitted_at - assignment.due_date).days + 1

    penalty = units_late * float(assignment.late_penalty_percent)

    if assignment.max_late_penalty:
        penalty = min(penalty, float(assignment.max_late_penalty))

    return penalty
```

#### Backend Tasks
- [ ] Add availability fields to Assignment model
- [ ] Add late_penalty_applied to Submission model
- [ ] Filter assignments by availability (students only see available)
- [ ] Block submissions after available_until (return 400 error)
- [ ] Calculate late penalty on submission
- [ ] Store penalty separately from grade
- [ ] Apply penalty to final grade calculation
- [ ] Tests for all edge cases (target: 15+ tests)

#### Frontend Tasks
- [ ] Assignment form: Available From/Until date pickers
- [ ] Late policy settings (% per day/hour, max penalty)
- [ ] Display availability window on assignment card
- [ ] "Closed" badge for past-due assignments
- [ ] "Opens [date]" for future assignments
- [ ] Late penalty display in grade view
- [ ] Warning when submitting late

#### Success Criteria
- [x] Assignment not visible before available_from
- [x] Submission blocked after available_until (with clear message)
- [x] Late penalty auto-calculated and shown separately
- [x] Final grade = earned points - late penalty
- [x] Instructor can see penalty applied
- [x] Max penalty cap works correctly

---

### Phase 11: User Settings & Preferences (Days 39-42) ✅ COMPLETE
**Priority:** 🟡 Medium (improves daily experience)

**Goal:** Users can customize their experience with theme and notification preferences

#### Why Now?
Students and teachers need control over their experience—notifications, theme, timezone. This reduces support requests and improves satisfaction.

#### Features
1. **Profile Settings** - Name, avatar
2. **Notification Preferences** - Toggle email notifications by type
3. **Display Preferences** - Dark mode, timezone
4. **Password Change** - Already exists via allauth

#### Models

**UserPreferences** (OneToOne with User)
| Field | Type | Notes |
|-------|------|-------|
| user | OneToOne → User | |
| theme | CharField(10) | 'light', 'dark', 'system', default='system' |
| timezone | CharField(50) | default='America/Chicago' |
| email_announcements | BooleanField | default=True |
| email_grades | BooleanField | default=True |
| email_submissions | BooleanField | default=True (instructor only) |
| email_due_reminders | BooleanField | default=True |

#### API Endpoints
```
GET  /api/auth/settings/                    # Get all preferences
PUT  /api/auth/settings/                    # Update preferences
POST /api/auth/settings/avatar/             # Upload avatar
DELETE /api/auth/settings/avatar/delete/    # Delete avatar
```

#### Backend Tasks
- [x] Create UserPreferences model
- [x] Auto-create preferences on user creation (signal)
- [x] Preferences CRUD endpoint
- [ ] Respect notification preferences when sending emails
- [x] Avatar upload endpoint (store in media/avatars/)
- [x] Include preferences in /api/auth/user/ response
- [ ] Tests (target: 8+ tests)

#### Frontend Tasks
- [x] SettingsPage with tabs: Profile, Notifications, Display
- [x] Profile tab: Name fields, avatar upload with preview
- [x] Notifications tab: Toggle switches for each email type
- [x] Display tab: Theme selector (light/dark/system), timezone dropdown
- [x] Apply theme immediately on change
- [x] Store theme in localStorage for instant load on refresh
- [x] Link to settings from header (Settings icon)
- [x] Update Tailwind config for dark mode support
- [x] ThemeContext for managing theme state

#### Dark Mode Implementation
```typescript
// ThemeProvider approach
useEffect(() => {
  const theme = preferences?.theme || 'system';
  if (theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
}, [preferences?.theme]);
```

#### Success Criteria
- [x] User can change name and upload avatar
- [x] Avatar displays in header
- [x] Dark mode works and persists across sessions
- [x] System theme preference follows OS setting
- [x] Theme is personalized per user (resets on logout)
- ~~[ ] Timezone affects due date displays~~ (Deferred - using Central Time)
- [ ] Disabling email notifications stops those emails
- [x] Settings save immediately (optimistic UI)

---

### Phase 12: Quizzes - Basic (Days 43-48) ✅ COMPLETE
**Priority:** 🟡 Medium (knowledge assessment)

**Goal:** Simple auto-graded quizzes with multiple choice questions

#### Why Now?
After core features are solid, teachers need quick knowledge checks. Start simple: multiple choice only.

#### Scope (MVP Quiz)
- Multiple choice questions only (single correct answer)
- Auto-graded immediately
- Immediate results with correct answers shown
- Configurable max attempts (0 = unlimited, or specific limit)
- No time limits (add later)
- No question shuffling (add later)

#### Models (App: quizzes)

**Quiz**
| Field | Type | Notes |
|-------|------|-------|
| unit | FK → Unit | related_name='quizzes' |
| title | CharField(200) | |
| description | TextField | blank=True |
| passing_score | PositiveIntegerField | default=70 (percent) |
| points | PositiveIntegerField | total points, default=10 |
| max_attempts | PositiveIntegerField | default=0 (0 = unlimited) |
| order | PositiveIntegerField | |
| created_at | DateTimeField | |

**Question**
| Field | Type | Notes |
|-------|------|-------|
| quiz | FK → Quiz | related_name='questions' |
| text | TextField | |
| order | PositiveIntegerField | |

**Choice**
| Field | Type | Notes |
|-------|------|-------|
| question | FK → Question | related_name='choices' |
| text | CharField(500) | |
| is_correct | BooleanField | default=False |
| order | PositiveIntegerField | |

**QuizAttempt**
| Field | Type | Notes |
|-------|------|-------|
| quiz | FK → Quiz | |
| student | FK → User | |
| score | DecimalField(5,2) | percentage |
| passed | BooleanField | |
| completed_at | DateTimeField | auto_now_add |

**AttemptAnswer**
| Field | Type | Notes |
|-------|------|-------|
| attempt | FK → QuizAttempt | related_name='answers' |
| question | FK → Question | |
| selected_choice | FK → Choice | null=True |
| is_correct | BooleanField | |

#### API Endpoints
```
# Quiz Management (Instructor)
GET    /api/units/{id}/quizzes/           # List quizzes in unit
POST   /api/units/{id}/quizzes/           # Create quiz
GET    /api/quizzes/{id}/                 # Quiz detail with questions
PUT    /api/quizzes/{id}/                 # Update quiz
DELETE /api/quizzes/{id}/                 # Delete quiz

# Questions (Instructor)
POST   /api/quizzes/{id}/questions/       # Add question with choices
PUT    /api/questions/{id}/               # Update question
DELETE /api/questions/{id}/               # Delete question

# Taking Quizzes (Student)
POST   /api/quizzes/{id}/submit/          # Submit answers, get results
GET    /api/quizzes/{id}/attempts/        # My attempts for this quiz
```

#### Backend Tasks
- [x] Create quizzes app with 5 models
- [x] Quiz CRUD (instructor only)
- [x] Question/Choice management
- [x] Submit endpoint: validate answers, calculate score, create attempt
- [x] Return results with correct answers
- [ ] Include quiz scores in gradebook (Phase 8) - Future enhancement
- [x] Tests (20 tests created)

#### Frontend Tasks
- [x] QuizCard in unit view (shows best score if attempted)
- [x] QuizTakingPage:
  - [x] Question list with radio buttons
  - [x] Submit button
  - [x] Results view with score and correct/incorrect
- [x] Instructor: QuizEditorPage:
  - [x] Quiz title, description, passing score
  - [x] Add/edit/delete questions
  - [x] Add/edit choices, mark correct answer
- [x] Add quizzes section to CourseDetailPage

#### Success Criteria
- [x] Instructor creates quiz with multiple choice questions
- [x] Student takes quiz, submits, sees immediate score
- [x] Student sees which answers were correct/incorrect
- [ ] Quiz score appears in gradebook (Future enhancement)
- [x] Configurable max attempts (0 = unlimited)
- [x] Attempts remaining displayed to students
- [x] Submission blocked when max attempts reached
- [x] Passing/failing indicated based on threshold

#### Future Enhancements (Phase 12+)
The following features are planned for future implementation:
- **Lesson Integration:** Quizzes can be required to complete a lesson
- **Gradebook Integration:** Quiz scores appear in gradebook with assignments
- **Weighted Grading:** Overall weight system for lessons, assignments, and quizzes
- **Cumulative Quizzes:** Support for cumulative/comprehensive quizzes covering multiple units

---

### Phase 12.5: Grading Polish (Days 49-52) ✅ COMPLETE
**Priority:** 🟠 High
**Status:** ✅ Complete

**Goal:** Enhance the grading system with quiz integration, weighted grading, and improved UX

#### Why Now?
After implementing quizzes, teachers need a unified view of all student grades (assignments + quizzes) with configurable weights. Students also need visibility into their overall course grade.

#### Implemented Features
1. **Quiz Gradebook Integration** - Quiz scores appear alongside assignment scores in unified gradebook
2. **Weighted Grading System** - Configurable course weights for assignments, quizzes, participation
3. **Student Grade Average Display** - Students see their overall weighted grade on course page and dedicated grades page
4. **Quick Grade in Gradebook** - Inline cell editing for faster grading (assignments only)
5. **Student Grades Page** - Detailed table view of all grades at `/courses/:code/grades`

#### Models

**CourseGradingConfig** (OneToOne with Course)
| Field | Type | Notes |
|-------|------|-------|
| course | OneToOne → Course | |
| assignments_weight | DecimalField(5,2) | default=50 |
| quizzes_weight | DecimalField(5,2) | default=50 |
| participation_weight | DecimalField(5,2) | default=0 |

#### API Endpoints
```
GET/PUT /api/courses/{code}/grading-config/       # Manage grading weights
GET     /api/courses/{code}/my-grades/            # Student grade summary + individual items
POST    /api/assignments/{id}/quick-grade/{student_id}/  # Quick grade
```

#### Backend Tasks
- [x] Create CourseGradingConfig model
- [x] Add grading-config endpoint (instructor only for PUT)
- [x] Update gradebook endpoint to include quiz scores
- [x] Implement weighted grade calculation
- [x] Create my-grades endpoint for students with individual grade items
- [x] Add quick-grade endpoint for inline grading
- [x] Filter unavailable assignments (available_from in future)
- [x] Accurate status handling (graded/submitted/missing/not_started)
- [x] Tests (21+ tests added)

#### Frontend Tasks
- [x] Update GradebookPage to show quiz columns with type icons
- [x] Add GradingConfigModal for weight settings
- [x] Implement EditableGradeCell for inline quick grading
- [x] Create MyGradesPage with detailed grades table
- [x] Add StudentGradeCard to course detail page
- [x] Display weighted average in gradebook
- [x] Color-coded status badges (graded/submitted/late/missing)
- [x] Legend for status indicators

#### Files Created/Modified
**Backend:**
- `backend/courses/models.py` - Added CourseGradingConfig model
- `backend/courses/views.py` - gradebook, grading-config, my-grades endpoints
- `backend/courses/urls.py` - New URL patterns
- `backend/courses/serializers.py` - GradingConfigSerializer
- `backend/assignments/views.py` - quick_grade endpoint
- `backend/assignments/urls.py` - quick-grade URL

**Frontend:**
- `frontend/src/types/index.ts` - GradebookItem, GradeSummary, StudentGradeDetailItem types
- `frontend/src/services/courses.ts` - New API methods
- `frontend/src/services/assignments.ts` - quickGrade method
- `frontend/src/pages/instructor/GradebookPage.tsx` - Quiz display + inline editing
- `frontend/src/pages/student/MyGradesPage.tsx` - New dedicated grades page
- `frontend/src/components/course/StudentGradeCard.tsx` - Grade summary card
- `frontend/src/components/course/GradingConfigModal.tsx` - Weight configuration
- `frontend/src/components/gradebook/EditableGradeCell.tsx` - Inline editing
- `frontend/src/App.tsx` - Added /courses/:code/grades route

#### Success Criteria
- [x] Gradebook shows both assignments and quiz scores in unified view
- [x] Instructor can configure weights (assignments/quizzes/participation)
- [x] Weighted grade calculates correctly
- [x] Students can view their overall course grade
- [x] Students have dedicated grades page with detailed table
- [x] Instructor can click assignment cell to edit grade inline
- [x] Quick grade saves without page refresh
- [x] Unavailable assignments hidden from student grades
- [x] Accurate status display for all grade items

---

### Phase 12.6: Udemy-Style Course Player (Days 53-56)
**Priority:** 🟠 High
**Status:** 🔄 In Progress

**Goal:** Transform course content viewing into a Udemy-like immersive learning experience

#### Why Now?
The current lesson viewing experience requires navigating back to the course page to select each lesson. Students need a focused, distraction-free learning environment with easy navigation between lessons.

#### Scope
- New CoursePlayerPage at `/courses/:code/learn`
- Collapsible sidebar with course curriculum
- Video player + markdown content in main area
- Previous/Next lesson navigation
- Auto-advance on lesson completion
- Progress tracking visible in sidebar
- Keyboard shortcuts for navigation

#### Components

**CoursePlayerPage** (New)
- Full-height layout with header, sidebar, main content
- Responsive design (sidebar collapses on mobile)

**CourseSidebar** (New)
- Course progress bar
- Accordion-based unit list
- Lesson items with completion status, type icons, duration
- Collapsible state persisted to localStorage

**LessonContent** (Refactored from LessonPage)
- Video player (YouTube/Vimeo)
- Markdown content rendering
- Mark complete button
- Previous/Next navigation

#### Routes
```
/courses/:code/learn           # Opens first incomplete lesson
/courses/:code/learn/:lessonId # Opens specific lesson
```

#### Backend Tasks
- [ ] Add endpoint to get "next lesson" for a course
- [ ] Ensure lesson ordering is correct in course detail response

#### Frontend Tasks
- [ ] Create CoursePlayerPage component
- [ ] Create CourseSidebar component with accordion units
- [ ] Refactor LessonContent from existing LessonPage
- [ ] Implement sidebar collapse/expand with localStorage persistence
- [ ] Add Previous/Next navigation buttons
- [ ] Add keyboard shortcuts (arrow keys)
- [ ] Auto-select first incomplete lesson on load
- [ ] Update routes in App.tsx
- [ ] Add "Continue Learning" button to CourseDetailPage

#### Success Criteria
- [ ] Students can view all lessons without leaving the player
- [ ] Sidebar shows accurate progress per unit
- [ ] Lessons auto-advance on completion
- [ ] Previous/Next buttons work correctly
- [ ] Sidebar collapse state persists across sessions
- [ ] Video progress saves correctly
- [ ] Mobile responsive layout works

#### Rollback Plan
Backup created at: `backups/pre-phase-12.6/`
To restore: Copy files from backup directory to original locations

---

### Phase 12.7: Overall Styling & Theme Polish (Days 57-60)
**Priority:** 🟢 Medium
**Status:** ⏳ Pending

**Goal:** Finalize the visual design and ensure consistent styling across the entire application

#### Why Now?
With core features complete, it's time to polish the UI for a professional, cohesive look before adding more features.

#### Scope
- Consistent color palette across all pages
- Typography refinements
- Dark mode polish
- Loading states and animations
- Button and card styling consistency
- Responsive design improvements
- Instructor vs student visual differentiation

#### Tasks
- [ ] Audit all pages for styling inconsistencies
- [ ] Define and apply consistent color variables
- [ ] Standardize button variants and sizes
- [ ] Polish card components (shadows, borders, spacing)
- [ ] Add subtle animations (hover, transitions)
- [ ] Improve loading skeleton states
- [ ] Test and fix dark mode issues
- [ ] Ensure responsive breakpoints work correctly
- [ ] Add visual distinction for instructor-only elements
- [ ] Polish form inputs and validation states

#### Success Criteria
- [ ] All pages follow consistent design language
- [ ] Dark mode works without visual issues
- [ ] Animations are smooth and purposeful
- [ ] Mobile experience is polished
- [ ] Loading states provide good UX feedback

---

### Phase 13: Discussion Forums - Simple (Days 61-65)
**Priority:** 🟢 Lower (peer support)

**Goal:** Simple course-level discussion threads for Q&A

#### Why Now?
After quizzes, students need a place to ask questions and help each other. Keep it simple: threads and replies, no voting.

#### Scope
- Course-level discussions only (not per-lesson)
- Threads with flat replies (no nesting)
- Pin important threads (instructor)
- Lock resolved threads (instructor)
- No voting/karma
- No @mentions

#### Models (App: discussions)

**Thread**
| Field | Type | Notes |
|-------|------|-------|
| course | FK → Course | related_name='threads' |
| author | FK → User | |
| title | CharField(200) | |
| content | TextField | Markdown |
| is_pinned | BooleanField | default=False |
| is_locked | BooleanField | default=False |
| created_at | DateTimeField | |

**Reply**
| Field | Type | Notes |
|-------|------|-------|
| thread | FK → Thread | related_name='replies' |
| author | FK → User | |
| content | TextField | Markdown |
| created_at | DateTimeField | |

#### API Endpoints
```
GET    /api/courses/{code}/threads/       # List threads
POST   /api/courses/{code}/threads/       # Create thread
GET    /api/threads/{id}/                 # Thread with replies
PUT    /api/threads/{id}/                 # Update (author or instructor)
DELETE /api/threads/{id}/                 # Delete (author or instructor)
POST   /api/threads/{id}/pin/             # Toggle pin (instructor)
POST   /api/threads/{id}/lock/            # Toggle lock (instructor)
POST   /api/threads/{id}/replies/         # Add reply
PUT    /api/replies/{id}/                 # Edit reply
DELETE /api/replies/{id}/                 # Delete reply
```

#### Backend Tasks
- [ ] Create discussions app with 2 models
- [ ] Thread CRUD
- [ ] Reply CRUD
- [ ] Pin/lock (instructor only)
- [ ] Prevent replies on locked threads
- [ ] Notification on reply to your thread
- [ ] Tests (target: 12+ tests)

#### Frontend Tasks
- [ ] DiscussionsPage (list threads, sorted by pinned then recent)
- [ ] ThreadDetailPage (thread content + replies)
- [ ] Create thread form (title + content)
- [ ] Reply form (simple text area)
- [ ] Pinned badge, locked indicator
- [ ] Instructor: pin/lock buttons
- [ ] Add Discussions link to course navigation

#### Success Criteria
- [ ] Student creates discussion thread
- [ ] Other students can reply
- [ ] Thread author gets notification on replies
- [ ] Instructor can pin important threads
- [ ] Instructor can lock resolved discussions
- [ ] Locked threads prevent new replies

---

### Phase 14: Instructor Analytics Dashboard (Days 54-58)
**Priority:** 🟢 Lower (end-of-unit insights)

**Goal:** Instructors can see class performance at a glance

#### Why Now?
After all content/grading features, instructors need visibility into class performance to adjust teaching.

#### Features
- Class overview (enrollment count, avg progress, avg grade)
- Assignment performance (which assignments are students struggling with?)
- Student progress list (who's falling behind?)
- Basic activity trends (submissions over time)

#### API Endpoints
```
GET /api/courses/{code}/analytics/overview/   # Key metrics
GET /api/courses/{code}/analytics/assignments/ # Assignment stats
GET /api/courses/{code}/analytics/students/   # Student progress list
GET /api/courses/{code}/analytics/activity/   # Submissions per day (last 30 days)
```

#### Backend Tasks
- [ ] Overview endpoint: total students, avg progress %, avg grade, active count
- [ ] Assignment stats: per-assignment avg score, completion rate
- [ ] Student progress list: sortable by progress %, last active
- [ ] Activity endpoint: submissions grouped by day
- [ ] Tests (target: 10+ tests)

#### Frontend Tasks
- [ ] AnalyticsDashboard page
- [ ] Overview cards (total students, avg progress, avg grade, active students)
- [ ] Assignment performance table (assignment name, avg score, completion %)
- [ ] Students at risk list (progress < 50%)
- [ ] Simple line chart for submissions over time (use recharts)
- [ ] Add Analytics link to ManageCoursePage

#### Charts Setup
```bash
npm install recharts
```

#### Success Criteria
- [ ] Instructor sees class overview at a glance
- [ ] Instructor can identify struggling assignments (low avg score)
- [ ] Instructor can identify at-risk students (low progress)
- [ ] Activity chart shows submission trends
- [ ] Data loads quickly (<2s)

---

### Phase 15: Email Configuration & Notifications
**Priority:** 🟡 Medium (required for invitations and announcements)

**Goal:** Configure SMTP for email delivery

#### Features
1. **SMTP Configuration** - Connect to email provider (Gmail, SendGrid, etc.)
2. **Email Templates** - HTML templates for invitations, announcements, grades
3. **Async Email** - Background email sending (optional Celery integration)

#### Environment Variables Required
```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@yourplatform.com
FRONTEND_URL=https://yourplatform.com
```

#### Backend Tasks
- [ ] Configure SMTP settings in production
- [ ] Create HTML email templates
- [ ] Test email delivery
- [ ] Add Celery for async email (optional)

#### Success Criteria
- [ ] Email invitations send successfully
- [ ] Announcement emails reach enrolled students
- [ ] Emails have proper branding/formatting

---

### What We're NOT Building (Yet)

Based on research, these features are deferred:

| Feature | Why Deferred |
|---------|--------------|
| Gamification (XP, badges) | Fun but not essential for teaching |
| Code Playground | Complex, students can use external tools |
| Code Challenges | Server execution is complex/risky |
| Video Chapters/Notes | YouTube handles this adequately |
| Course Duplication | Nice-to-have, manual copy works |
| Rubrics | Simple points-based grading is sufficient |
| Peer Review | Complex workflow, rarely used in K-12 |
| Direct Messaging | Email/existing notifications sufficient for now |

---

### Revised Timeline Summary

| Phase | Name | Priority | Status |
|-------|------|----------|--------|
| 7 | Announcements & Communication | 🔴 Critical | ✅ Complete |
| 8 | Gradebook & Grade Export | 🔴 Critical | ✅ Complete |
| 9 | Student Roster & Activity | 🟠 High | ✅ Complete |
| 10 | Assignment Availability & Late Policies | 🟠 High | ✅ Complete |
| 11 | User Settings & Preferences | 🟡 Medium | ✅ Complete |
| 12 | Quizzes (Basic) | 🟡 Medium | ✅ Complete |
| 12.5 | Grading Polish | 🟠 High | ✅ Complete |
| 13 | Discussion Forums | 🟢 Lower | Pending |
| 14 | Analytics Dashboard | 🟢 Lower | Pending |
| 15 | Email Configuration | 🟡 Medium | Pending |

**Completed: Phases 7-12.5** | **Next: Phase 13 (Discussion Forums)**

---

### Release Strategy

```
v1.0.0 = MVP (Phases 1-6) ✅ Complete
v1.1.0 = After Phase 9 (Announcements + Gradebook + Roster) ✅ Complete
v1.2.0 = After Phase 10 (Late Policies) ✅ Complete
v1.3.0 = After Phase 11 (Settings + Dark Mode) ✅ Complete
v1.4.0 = After Phase 12 (Quizzes) ✅ Complete
v1.5.0 = After Phase 12.5 (Grading Polish) ✅ Complete
v2.0.0 = After Phase 15 (Full Platform)
```

---

## Part 7: Docker Setup (Local Development)

### docker-compose.yml
```yaml
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: gamedev_db
      POSTGRES_USER: gamedev_user
      POSTGRES_PASSWORD: ${DB_PASSWORD:-devpassword}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U gamedev_user -d gamedev_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7.2-alpine
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    environment:
      - DEBUG=True
      - DATABASE_URL=postgres://gamedev_user:${DB_PASSWORD:-devpassword}@db:5432/gamedev_db
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=${SECRET_KEY:-dev-secret-key-change-in-production}
      - ALLOWED_HOSTS=localhost,127.0.0.1
      - CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
      - SENTRY_DSN=${SENTRY_DSN:-}
      - EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
    volumes:
      - ./backend:/app
      - backend_static:/app/staticfiles
      - backend_media:/app/media
    ports:
      - "8000:8000"
    command: >
      sh -c "python manage.py migrate &&
             python manage.py collectstatic --noinput &&
             python manage.py runserver 0.0.0.0:8000"

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://localhost:8000/api
      - VITE_WS_URL=ws://localhost:8000/ws
    command: npm run dev -- --host

volumes:
  postgres_data:
  redis_data:
  backend_static:
  backend_media:
```

### Environment Variables

```bash
# .env.example

# Database
DB_PASSWORD=your-secure-password

# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:5173

# Redis
REDIS_URL=redis://localhost:6379/0

# Email (use console backend for dev)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Sentry (optional for dev)
SENTRY_DSN=

# Frontend
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/ws
```

---


## Part 8: Key Principles

1. **One phase at a time** - Complete and test before moving on
2. **No premature optimization** - Simple solutions first
3. **Delete ruthlessly** - If unused for 2 weeks, remove it
4. **Test as you build** - Don't accumulate test debt
5. **Reference, don't copy** - Understand code before reusing
6. **Embeds over uploads** - YouTube handles video complexity

---

## Timeline Summary

### MVP (Phases 1-6) ✅ COMPLETE
| Phase | Days | Deliverable | Status |
|-------|------|-------------|--------|
| 1. Foundation | 1-3 | Auth with email verification | ✅ |
| 2. Courses | 4-7 | Course content viewable | ✅ |
| 3. Video | 8-10 | YouTube embeds + progress | ✅ |
| 4. Assignments | 11-14 | Full assignment workflow | ✅ |
| 5. Notifications | 15-18 | Real-time updates | ✅ |
| 6. Polish | 19-21 | Testing + documentation | ✅ |

**MVP Complete: ~3 weeks**

### Extended Features (Phases 7-15) - Teacher-Focused
| Phase | Deliverable | Priority | Status |
|-------|-------------|----------|--------|
| 7. Announcements | Class-wide communication | 🔴 Critical | ✅ Complete |
| 8. Gradebook | Grade matrix + CSV export | 🔴 Critical | ✅ Complete |
| 9. Student Roster | Activity tracking + email invites | 🟠 High | ✅ Complete |
| 10. Late Policies | Availability dates + penalties | 🟠 High | ✅ Complete |
| 11. Settings | Dark mode + preferences | 🟡 Medium | ✅ Complete |
| 12. Quizzes | Auto-graded MC quizzes | 🟡 Medium | ✅ Complete |
| 12.5. Grading Polish | Quiz gradebook + weighted grades + student grades page | 🟠 High | ✅ Complete |
| 13. Discussions | Simple Q&A forums | 🟢 Lower | Pending |
| 14. Analytics | Instructor dashboard | 🟢 Lower | Pending |
| 15. Email Config | SMTP setup for notifications | 🟡 Medium | Pending |

**Completed: Phases 7-12.5** | **Next: Phase 13 (Discussion Forums)**

---

## Compatibility Quick Reference

| Component | Version | Warning |
|-----------|---------|---------|
| Python | **3.12.8** | ⚠️ NOT 3.13 |
| Django | 4.2.27 | LTS ends Apr 2026 |
| psycopg | 3.3.2 | Use psycopg3, not psycopg2 |
| django-allauth | 65.3.0 | Handles all auth flows |
| React Router | 7.12.0 | Import from `react-router` |
| Axios | **1.13.2** | ⚠️ Security: avoid ≤1.7.x |
| Redis | 7.2 | Last BSD-licensed version |

---

## Key Changes from v2.0

| Change | Before | After | Why |
|--------|--------|-------|-----|
| Auth | DRF TokenAuth | django-allauth + dj-rest-auth | Email verification, password reset built-in |
| Video | YouTube/Vimeo/Upload | YouTube/Vimeo only | Removes infrastructure complexity |
| Error tracking | None | Sentry | Know when things break |
| Lesson.video_url | URLField | video_id CharField | Cleaner; just store the ID |
| Testing | Manual | pytest-django | Catch regressions |

---

*Document Version: 3.4*
*Last Updated: January 27, 2026*
*MVP Status: Complete (Phases 1-6)*
*Extended Features: Phases 7-12.5 Complete, Phases 13-15 Pending*
*Based on: Research into Canvas, Google Classroom, Schoology, and teacher feedback*
