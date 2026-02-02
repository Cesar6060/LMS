# Interview Guide: GameDev Learning Platform

How to talk about this project with recruiters, hiring managers, and technical interviewers.

---

## The 30-Second Pitch

> "I built a full-stack learning management system for teaching video game development courses. It's a production-ready platform with real-time notifications, an immersive video player, quizzes, assignments, and a complete gradebook. I used React and TypeScript on the frontend, Django REST Framework on the backend, PostgreSQL for the database, and WebSockets for real-time features. The whole thing runs in Docker containers."

---

## The 2-Minute Story

> "I identified a need for a specialized learning platform for video game development education—existing solutions like Canvas or Google Classroom are generic and don't provide the immersive learning experience students need.
>
> I designed and built the entire system from scratch. On the frontend, I used React 18 with TypeScript for type safety, Tailwind for styling, and Framer Motion for animations. The backend is Django REST Framework with a PostgreSQL database. I implemented real-time notifications using Django Channels and WebSockets backed by Redis.
>
> The platform supports two user roles: students can watch video lessons, complete quizzes, submit assignments, and track their progress. Instructors can build courses, grade submissions, manage rosters, and post announcements.
>
> One of the technical challenges was implementing the real-time notification system. I had to learn Django Channels and figure out how to authenticate WebSocket connections with JWT tokens. Another challenge was designing the gradebook—I needed weighted categories, late penalties, and the ability to export to CSV.
>
> The result is a production-ready platform with 65+ React components, 40+ API endpoints, and full Docker containerization for deployment."

---

## Technical Decision Deep-Dives

Use these when interviewers ask "Why did you choose X?" or "Tell me about a technical decision you made."

### 1. Why React + TypeScript?

**What I chose:** React 18 with TypeScript, Vite as the build tool

**Why:**
- **TypeScript** catches bugs at compile time. With 65+ components and complex data structures (courses, lessons, grades), type safety prevented countless runtime errors.
- **React 18** for the concurrent features and improved Suspense support—useful for loading states in the course player.
- **Vite** over Create React App because it's significantly faster for development (hot module replacement is instant).

**Talking point:**
> "I chose TypeScript because the data model is complex—courses contain units, units contain lessons, lessons have sections, quizzes, and attachments. Without types, it would be easy to pass the wrong data shape to a component. TypeScript caught issues during development that would have been runtime bugs."

---

### 2. Why Django REST Framework?

**What I chose:** Django 4.2 LTS with Django REST Framework

**Why:**
- **Django's ORM** makes complex queries simple—fetching a student's progress across multiple courses with grades and quiz scores is one queryset.
- **DRF's serializers** handle validation and nested object serialization cleanly.
- **Built-in admin panel** let me quickly manage data during development and gives instructors a fallback admin interface.
- **Mature ecosystem**—django-allauth for auth, django-channels for WebSockets, battle-tested in production.

**Talking point:**
> "I chose Django because I needed complex relational queries—like calculating a student's weighted grade across assignments and quizzes with late penalties. Django's ORM made that straightforward. DRF's serializer system also saved time—I could define the shape of API responses declaratively and get validation for free."

---

### 3. Why WebSockets for Notifications?

**What I chose:** Django Channels with Redis for real-time notifications

**Why:**
- **Instant feedback** when grades are posted—students don't need to refresh
- **No polling overhead**—WebSockets maintain a persistent connection instead of hitting the server every few seconds
- **Redis as the channel layer** makes it scalable—multiple backend instances can share the same pub/sub system

**Talking point:**
> "I implemented WebSockets because the user experience demanded it. When an instructor grades an assignment, the student should see that notification immediately. Polling would work, but it's wasteful—you're making requests even when nothing changed. WebSockets are more efficient and provide a better UX."

**Follow-up if asked about challenges:**
> "The tricky part was authentication. HTTP requests send cookies automatically, but WebSocket connections don't. I had to pass the JWT token as a query parameter during the WebSocket handshake and validate it in a custom middleware."

---

### 4. Why PostgreSQL over MySQL or MongoDB?

**What I chose:** PostgreSQL 16

**Why:**
- **Relational data model fits perfectly**—courses have units, units have lessons, lessons have sections. These relationships are natural in SQL.
- **Django's best-supported database**—features like JSONField work best with Postgres
- **ACID compliance**—grades and submissions need transactional integrity
- **Scalability**—Postgres handles complex queries efficiently with proper indexing

**Talking point:**
> "The data is inherently relational. A grade belongs to a submission, which belongs to an assignment, which belongs to a unit, which belongs to a course. MongoDB would require denormalization or multiple queries. With Postgres and Django's ORM, I can fetch all of that in a single optimized query."

---

### 5. Why Docker?

**What I chose:** Docker Compose with separate containers for frontend, backend, database, and Redis

**Why:**
- **Reproducible environments**—anyone can clone the repo and run `docker-compose up`
- **Isolation**—each service has its own container with specific dependencies
- **Production parity**—development environment mirrors production
- **Easy onboarding**—new developers don't need to install Python, Node, Postgres, Redis manually

**Talking point:**
> "Docker eliminates the 'works on my machine' problem. The entire stack—React frontend, Django backend, Postgres, Redis—spins up with one command. It also makes deployment straightforward since the same containers run in production."

---

### 6. Why JWT Authentication over Sessions?

**What I chose:** JWT tokens with django-rest-auth

**Why:**
- **Stateless**—the server doesn't need to store session data
- **Works with WebSockets**—tokens can be passed during handshake
- **Mobile-ready**—if I build a mobile app later, tokens work the same way
- **Decoupled frontend**—React app can be hosted separately from Django

**Talking point:**
> "JWTs made sense because the frontend and backend are decoupled. The React app is served by Vite in development and could be on a CDN in production. Session cookies would require the same domain. JWTs also simplified WebSocket authentication—I pass the token in the connection URL."

---

## Challenges & How I Solved Them

Use these for "Tell me about a challenge you faced" questions.

### Challenge 1: Real-time WebSocket Authentication

**The problem:** WebSocket connections don't send cookies, so Django's session auth doesn't work.

**How I solved it:**
1. Pass JWT token as query parameter: `ws://localhost:8000/ws/notifications/?token=xxx`
2. Created custom middleware in Django Channels to extract and validate the token
3. Attach the authenticated user to the WebSocket scope

**What I learned:** Authentication mechanisms differ between protocols. I had to understand the WebSocket handshake process and Django Channels' middleware system.

---

### Challenge 2: Weighted Gradebook with Late Penalties

**The problem:** Grades needed to support weighted categories (assignments 60%, quizzes 30%, participation 10%) plus late penalty calculations (e.g., -10% per day late, max 50% penalty).

**How I solved it:**
1. Designed a flexible grade calculation system in the serializer
2. Late penalty calculated at submission time based on due date
3. Final grade = raw grade - late penalty
4. Category weights applied at the gradebook level
5. Handle edge cases: no submissions, excused assignments, extra credit

**What I learned:** Business logic can get complex. I broke it into small, testable functions and wrote unit tests for edge cases.

---

### Challenge 3: Lesson Progress Tracking

**The problem:** Students should resume videos exactly where they left off, even days later.

**How I solved it:**
1. Track `video_position` in `LessonProgress` model
2. Debounce position updates (save every 5 seconds, not every frame)
3. On page load, seek video to saved position
4. Mark lesson complete only when video reaches 90% or user clicks "Mark Complete"

**What I learned:** UX details matter. Saving too frequently wastes bandwidth; saving too rarely loses progress. Debouncing was the right balance.

---

### Challenge 4: Role-Based Permissions

**The problem:** Students should only see their own grades; instructors should see all students. Same endpoint, different data.

**How I solved it:**
1. Check `request.user.is_instructor` in views
2. Filter querysets based on role
3. Use different serializers for student vs instructor (instructor sees more fields)
4. Secure the frontend routes, but always enforce on backend

**What I learned:** Never trust the frontend. Even if a button is hidden, the API must enforce permissions. I always check permissions server-side.

---

## Questions to Expect (and How to Answer)

### "What would you do differently?"

> "I'd add more comprehensive test coverage earlier. I focused on building features fast, and while I tested manually, automated tests would have caught regressions. I'd also consider GraphQL for some endpoints—the nested course structure would benefit from clients requesting exactly what they need."

### "How would you scale this?"

> "The architecture is already scalable. The backend is stateless, so I can run multiple instances behind a load balancer. Redis handles WebSocket pub/sub across instances. For the database, I'd add read replicas and implement caching for frequently-accessed data like course structures. For heavy traffic, I'd put static assets on a CDN."

### "What was the hardest part?"

> "Designing the data model upfront. Getting the relationships right between courses, units, lessons, sections, progress, grades—it required thinking through all the use cases before writing code. Once the model was solid, everything else fell into place."

### "How did you handle security?"

> "Multiple layers. Authentication uses JWT with token refresh. Authorization checks happen on every API endpoint—never trust the frontend. Instructor registration is admin-only to prevent privilege escalation. File uploads are validated for type and size. Passwords are hashed with Django's PBKDF2. CORS is configured to allow only the frontend origin."

### "Did you work alone on this?"

> "Yes, this was a solo project. I designed the architecture, built both frontend and backend, and handled DevOps. I used Claude AI as a coding assistant for pair programming, debugging, and generating boilerplate, but all architectural decisions and problem-solving were mine."

---

## Metrics to Mention

- **65+ React components** built from scratch
- **40+ REST API endpoints** with full CRUD operations
- **5 Django apps** (accounts, courses, assignments, quizzes, notifications)
- **Production-ready** with Docker containerization
- **Real-time** WebSocket notifications
- **Full authentication** system with email verification and password reset
- **Responsive design** with dark mode support

---

## Tailoring for Different Audiences

### For Non-Technical Recruiters

Focus on:
- The problem you solved (schools needed a better learning platform)
- The scope (full application, not just a feature)
- That it's production-ready (not just a tutorial project)

### For Technical Interviewers

Focus on:
- Architecture decisions and trade-offs
- Specific challenges and solutions
- Code quality (TypeScript, testing approach, separation of concerns)

### For Engineering Managers

Focus on:
- How you scoped and prioritized features
- How you'd extend it (scale, new features)
- What you learned and would do differently

---

## Final Tips

1. **Be specific** - Don't say "I built a website." Say "I built an LMS with real-time notifications using Django Channels and WebSockets."

2. **Explain the why** - Anyone can list technologies. Explaining *why* you chose them shows engineering judgment.

3. **Own the challenges** - Interviewers want to hear about problems. Saying "everything went smoothly" is a red flag.

4. **Show growth** - Mention what you learned and what you'd do differently.

5. **Have the code ready** - Be prepared to pull up the GitHub repo and walk through specific files.
