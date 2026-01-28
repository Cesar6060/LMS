# Video Game Course Platform v2

Educational platform for video game development courses at Prosper ISD.

## Tech Stack

- **Backend:** Django 4.2 LTS + Django REST Framework
- **Frontend:** React 18 + TypeScript + Vite
- **Database:** PostgreSQL 16
- **Auth:** django-allauth + dj-rest-auth

## Quick Start

### Prerequisites

- Python 3.12 (NOT 3.13)
- Node.js 22 LTS
- PostgreSQL 16
- Docker & Docker Compose (optional)

### Option 1: Docker (Recommended)

```bash
# Copy environment file
cp .env.example .env

# Start all services
docker-compose up

# Access:
# - Frontend: http://localhost:5173
# - Backend API: http://localhost:8000/api
# - Admin: http://localhost:8000/admin
```

### Option 2: Local Development

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp ../.env.example .env
# Edit .env with your database credentials

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run server
python manage.py runserver
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev
```

## Project Structure

```
gamedev-platform-v2/
├── backend/
│   ├── config/          # Django settings
│   ├── accounts/        # User model, auth
│   ├── courses/         # Courses, units, lessons
│   ├── assignments/     # Assignments, submissions, grades
│   └── notifications/   # Real-time notifications (Phase 5)
├── frontend/
│   ├── src/
│   │   ├── components/  # Reusable components
│   │   ├── pages/       # Route pages
│   │   ├── contexts/    # React contexts
│   │   └── services/    # API services
│   └── ...
├── docker-compose.yml
└── README.md
```

## API Endpoints

### Authentication
- `POST /api/auth/registration/` - Register new user
- `POST /api/auth/login/` - Login
- `POST /api/auth/logout/` - Logout
- `GET /api/auth/user/` - Current user
- `POST /api/auth/password/reset/` - Request password reset

### Courses
- `GET /api/courses/` - List courses
- `POST /api/courses/` - Create course (instructor)
- `GET /api/courses/{code}/` - Course detail
- `POST /api/courses/{code}/enroll/` - Enroll with code

### Assignments
- `GET /api/courses/{code}/assignments/` - List assignments
- `POST /api/assignments/{id}/submission/` - Submit assignment
- `POST /api/submissions/{id}/grade/` - Grade submission (instructor)

### Announcements
- `GET /api/courses/{code}/announcements/` - List announcements
- `POST /api/courses/{code}/announcements/` - Create announcement (instructor)
- `GET /api/announcements/{id}/` - Announcement detail

### Gradebook
- `GET /api/courses/{code}/gradebook/` - Full gradebook matrix
- `GET /api/courses/{code}/gradebook/export/` - CSV export

### Student Roster
- `GET /api/courses/{code}/students/` - Student roster
- `POST /api/courses/{code}/students/invite/` - Send email invitation
- `DELETE /api/courses/{code}/students/{id}/` - Remove student

### User Settings
- `GET /api/auth/settings/` - Get user preferences
- `PATCH /api/auth/settings/` - Update preferences
- `POST /api/auth/settings/avatar/` - Upload avatar
- `DELETE /api/auth/settings/avatar/delete/` - Remove avatar

### Quizzes
- `GET /api/courses/{code}/quizzes/` - List course quizzes
- `GET /api/units/{id}/quizzes/` - List unit quizzes
- `POST /api/units/{id}/quizzes/` - Create quiz (instructor)
- `GET /api/quizzes/{id}/` - Quiz detail with questions
- `PUT /api/quizzes/{id}/` - Update quiz (instructor)
- `DELETE /api/quizzes/{id}/` - Delete quiz (instructor)
- `POST /api/quizzes/{id}/questions/` - Add question (instructor)
- `PUT /api/questions/{id}/` - Update question (instructor)
- `DELETE /api/questions/{id}/` - Delete question (instructor)
- `POST /api/quizzes/{id}/submit/` - Submit quiz answers
- `GET /api/quizzes/{id}/attempts/` - Get quiz attempts

**Quiz Features:**
- Multiple choice questions with single correct answer
- Auto-grading with immediate results
- Configurable max attempts (0 = unlimited)
- Passing score threshold
- Best score tracking

## Development Phases

### MVP (Complete)
- [x] Phase 1: Foundation (Auth)
- [x] Phase 2: Courses & Enrollment
- [x] Phase 3: Video & Progress
- [x] Phase 4: Assignments
- [x] Phase 5: Notifications
- [x] Phase 6: Polish & Deploy

### Extended Features (In Progress)
- [x] Phase 7: Announcements & Communication
- [x] Phase 8: Gradebook & Grade Export
- [x] Phase 9: Student Roster & Activity Tracking
- [x] Phase 10: Assignment Availability & Late Policies
- [x] Phase 11: User Settings & Preferences
- [x] Phase 12: Quizzes
- [ ] Phase 13: Discussion Forums
- [ ] Phase 14: Analytics Dashboard
- [ ] Phase 15: Email Configuration

## Demo Data

Seed the database with demo content for testing:

```bash
cd backend
python manage.py seed_data

# Or clear existing data first
python manage.py seed_data --clear
```

Demo accounts created:
- **Instructor:** instructor@demo.com / password123
- **Students:** student1@demo.com, student2@demo.com, student3@demo.com / password123

The seed command creates a sample course (VGD101) with units, lessons, assignments, and student progress.

## Testing

```bash
# Backend tests
cd backend
pytest

# With coverage
pytest --cov=. --cov-report=html
```

## Environment Variables

See `.env.example` for all available configuration options.

## License

Private - Prosper ISD
