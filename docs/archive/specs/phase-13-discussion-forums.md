# Phase 13 — Discussion Forums (Simple)

**App:** `discussions` (new Django app) · **Priority:** 🟢 Lower (peer support)

Closest existing analog: **Announcements** (`courses/models.py` `Announcement`, `courses/views.py` `AnnouncementViewSet`, `frontend/src/pages/announcements/*`). Discussions is essentially *student-writable, threaded announcements*. Follow the Announcement + `quizzes` app patterns throughout.

---

## Goal

Give each course a simple Q&A discussion board: enrolled students and the instructor can start **threads** (title + markdown body) and post flat **replies** (no nesting, no voting, no @mentions). Threads list pinned-first then by most-recent activity, showing reply count and last-activity time. Instructors can **pin** important threads and **lock** resolved ones (locking blocks student replies but the instructor can still post). The thread author is notified on each new reply (never for their own). Authors can edit/delete their own posts; instructors can delete any post for moderation. Scope is deliberately minimal per ADR-016 (K-12 context, no Reddit-style features).

## Out of scope

- Per-lesson or per-unit discussions (course-level only).
- Nested/threaded replies, voting, karma, reactions, @mentions, tags/categories.
- Subscriptions / "notify all prior repliers" — **only the thread author** is notified.
- Notifying the instructor when a new thread is created.
- Soft-delete / tombstones / edit history / audit trail — deletes are **hard deletes** (cascade).
- Rich-text/WYSIWYG editor — plain `<textarea>`, markdown rendered read-only (matches Announcements).
- Search, pagination, or infinite scroll on threads/replies (K-12 class sizes are small).
- Email notifications for replies (in-app `Notification` only).
- Real-time updates / WebSockets.

---

## Data model decisions (resolved in interview)

- **Notifications:** on reply create, notify `thread.author` only, and only if `reply.author != thread.author`. New `Notification.type` choice `('reply', 'New Reply')`.
- **Lock semantics:** `is_locked` blocks reply creation for non-instructors (403); the course instructor may still reply. Locking does **not** freeze editing/deleting of existing posts. Pin/lock never affect thread creation.
- **Delete:** hard delete. Deleting a thread cascades to its replies (FK `on_delete=CASCADE`). Deleting a reply removes it outright.
- **List sort & metadata:** pinned first, then by `last_activity` desc, where `last_activity = Max(replies.created_at)` coalesced to `thread.created_at`. Each list row exposes `reply_count` and `last_activity`.
- **Edit vs delete authority:** editing a post = **author only**. Deleting a post = **author or course instructor** (moderation). Pin/lock = **course instructor only**.

---

## Backend tasks

Base new app on `quizzes` (function-based `@api_view` + course-code helpers) and copy the notification/pin idioms from `Announcement`. Reuse the helpers `is_course_instructor(user, course)` and `is_enrolled(user, course)` (define locally in `discussions/views.py`, mirroring `quizzes/views.py`). Course is looked up by `Course.code` via `get_object_or_404(Course, code=course_code)`. Enrollment check must include `is_active=True`.

### Models & migration
- [x] Create `discussions` app; add `'discussions'` to `INSTALLED_APPS` in `config/settings.py`.
- [x] `Thread` model (`discussions/models.py`):
  - `course = FK(Course, on_delete=CASCADE, related_name='threads')`
  - `author = FK(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='threads_created')`
  - `title = CharField(max_length=200)`
  - `content = TextField(help_text='Markdown supported')`
  - `is_pinned = BooleanField(default=False)`
  - `is_locked = BooleanField(default=False)`
  - `created_at = DateTimeField(auto_now_add=True)`, `updated_at = DateTimeField(auto_now=True)`
  - `Meta: ordering = ['-is_pinned', '-created_at']`
- [x] `Reply` model (`discussions/models.py`):
  - `thread = FK(Thread, on_delete=CASCADE, related_name='replies')`
  - `author = FK(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='replies_created')`
  - `content = TextField()`
  - `created_at = DateTimeField(auto_now_add=True)`, `updated_at = DateTimeField(auto_now=True)`
  - `Meta: ordering = ['created_at']` (chronological)
- [x] `makemigrations discussions` + migrate. Register both models in `discussions/admin.py`.
- [x] Add `('reply', 'New Reply')` to `Notification.TYPE_CHOICES` in `notifications/models.py` (+ migration).

### Serializers (`discussions/serializers.py`)
- [x] `ThreadListSerializer` — `id, title, author` (nested `UserSerializer`, read-only) + `author_name` (SerializerMethodField, `get_full_name() or email`), `is_pinned, is_locked, reply_count, last_activity, created_at`. `reply_count` / `last_activity` come from queryset annotations (see views).
- [x] `ThreadDetailSerializer` — `id, course_code (source='course.code'), title, content, author (UserSerializer), is_pinned, is_locked, created_at, updated_at, replies (ReplySerializer many, read-only)`.
- [x] `ThreadCreateSerializer` — `fields = ['id', 'title', 'content']`.
- [x] `ReplySerializer` — `id, author (UserSerializer), content, created_at, updated_at`.
- [x] `ReplyCreateSerializer` — `fields = ['id', 'content']`.

### Endpoints (`discussions/views.py` + `discussions/urls.py`, mounted `path('api/', include('discussions.urls'))`)
All require `IsAuthenticated`. Read access = instructor of the course **or** active enrollment (else 403).

- [x] `GET/POST /api/courses/<str:course_code>/threads/` → `course_threads`
  - GET: list threads for course, annotated `reply_count=Count('replies')` and `last_activity=Coalesce(Max('replies__created_at'), 'created_at')`, ordered `-is_pinned, -last_activity`. Serialize with `ThreadListSerializer`. Instructor-or-enrolled only.
  - POST: instructor-or-enrolled creates a thread; `save(course=course, author=request.user)`. Return `ThreadDetailSerializer` 201.
- [x] `GET/PUT/DELETE /api/threads/<int:thread_id>/` → `thread_detail`
  - GET: instructor-or-enrolled → `ThreadDetailSerializer` (includes replies).
  - PUT: **author or course instructor** (else 403). Edits `title/content` only.
  - DELETE: **author or course instructor** (else 403). Cascades replies. 204.
- [x] `POST /api/threads/<int:thread_id>/pin/` → `toggle_pin` — **instructor only** (else 403). Flips `is_pinned`, `save(update_fields=['is_pinned'])`, return updated thread.
- [x] `POST /api/threads/<int:thread_id>/lock/` → `toggle_lock` — **instructor only** (else 403). Flips `is_locked`. Return updated thread.
- [x] `POST /api/threads/<int:thread_id>/replies/` → `create_reply`
  - Instructor-or-enrolled. **If `thread.is_locked` and requester is not the course instructor → 403.** `save(thread=thread, author=request.user)`. Return `ReplySerializer` 201.
  - After save: if `reply.author != thread.author`, `Notification.objects.create(recipient=thread.author, type='reply', title=f'New reply to "{thread.title}"', message=..., related_url=f'/courses/{thread.course.code}/discussions/{thread.id}')`.
- [x] `PUT /api/replies/<int:reply_id>/` → `update_reply` — **author only** (else 403). Edits `content`.
- [x] `DELETE /api/replies/<int:reply_id>/` → `delete_reply` — **author or course instructor** (else 403). 204.

### Tests (`discussions/tests.py`, target 12+)
Local fixtures (`api_client, instructor, student, second_student, course, enrollment`, plus a non-enrolled student), `APIClient().force_authenticate`, `@pytest.mark.django_db`. Mirror `quizzes/tests.py`. Cover:
- [x] List threads: enrolled → 200; not-enrolled → 403; anonymous → 401.
- [x] Create thread: enrolled student → 201; not-enrolled → 403.
- [x] Thread detail returns nested replies; `reply_count`/`last_activity` correct on list.
- [x] List ordering: pinned thread first, then most-recently-replied thread before an older-activity thread.
- [x] Reply create: enrolled → 201; on **locked** thread by student → 403; on **locked** thread by **instructor** → 201.
- [x] Pin toggle: instructor → 200 (flips); student → 403. Lock toggle: instructor → 200; student → 403.
- [x] Thread update: author → 200; other student → 403; instructor → 200.
- [x] Thread delete by author cascades (its replies gone). Reply delete: author → 204; instructor moderating another's reply → 204; unrelated student → 403.
- [x] Reply edit: author → 200; non-author → 403.
- [x] Notification: a `type='reply'` Notification is created for `thread.author` when another user replies; **no** Notification when the author replies to their own thread.

---

## Frontend tasks

Model the two pages on `pages/announcements/AnnouncementsPage.tsx` (list + create Dialog) and `AnnouncementDetailPage.tsx` (detail + form). Course param is `:code`. Use the shared `api` client, `useAuth()`, and existing `ui/` components (`Button, Card, Dialog, Input, Skeleton`). Markdown via `ReactMarkdown` + `remarkGfm` with `className="prose prose-neutral dark:prose-invert max-w-none"`.

### Types (`frontend/src/types/index.ts`, new `// Phase 13: Discussion types` block)
- [x] `Reply` — `id, author: User, content, created_at, updated_at`.
- [x] `ThreadListItem` — `id, title, author: User, author_name, is_pinned, is_locked, reply_count, last_activity, created_at`.
- [x] `ThreadDetail` — `id, course_code, title, content, author: User, is_pinned, is_locked, created_at, updated_at, replies: Reply[]`.

### Service (`frontend/src/services/discussions.ts`)
- [x] `getCourseThreads(code)` → `GET /courses/${code}/threads/`
- [x] `getThread(id)` → `GET /threads/${id}/`
- [x] `createThread(code, { title, content })` → `POST /courses/${code}/threads/`
- [x] `updateThread(id, { title, content })` → `PUT /threads/${id}/`
- [x] `deleteThread(id)` → `DELETE /threads/${id}/`
- [x] `togglePin(id)` → `POST /threads/${id}/pin/`
- [x] `toggleLock(id)` → `POST /threads/${id}/lock/`
- [x] `createReply(threadId, { content })` → `POST /threads/${threadId}/replies/`
- [x] `updateReply(id, { content })` → `PUT /replies/${id}/`
- [x] `deleteReply(id)` → `DELETE /replies/${id}/`

### Pages & routing
- [x] `pages/discussions/DiscussionsPage.tsx` — list threads (pinned badge, locked indicator, reply count, last-activity relative time), "New Thread" button (any enrolled user) opening a Dialog (title `Input` + markdown `textarea`). Empty state Card. Rows link to detail.
- [x] `pages/discussions/ThreadDetailPage.tsx` — thread title/body (markdown), pinned/locked indicators, replies list (markdown, author + timestamp), reply `<textarea>` form (hidden/disabled with a "This thread is locked" notice when `is_locked` and viewer is not the instructor). Author sees edit/delete on own posts; instructor sees pin/lock toggles + delete on any post. Back link to list.
- [x] Add routes to `App.tsx` (both `ProtectedRoute`): `/courses/:code/discussions` → `DiscussionsPage`, `/courses/:code/discussions/:threadId` → `ThreadDetailPage`. Import pages at top.
- [x] `pages/courses/CourseDetailPage.tsx` — add a **Discussions** section (gated by `canAccessContent`) mirroring the Announcements block: `MessageSquare` icon (from `lucide-react`), heading, and a `Link` to `/courses/${course.code}/discussions` with `View All` / `Manage Discussions` label.

---

## Verification (prove it works end to end)

1. **Backend tests** — `cd backend && pytest discussions/` → all pass, 12+ tests, including the locked-thread 403/instructor-201 split and the self-reply "no notification" case. Show output.
2. **Type check** — `cd frontend && npx tsc --noEmit` → clean.
3. **Lint** — `cd frontend && npm run lint` → clean.
4. **`/verify-stack`** — run and paste output before marking the phase complete.
5. **Manual click-through** (Docker stack up):
   - As **student A**: open a course → Discussions → create a thread → it appears pinned-first list with reply count 0.
   - As **student B** (enrolled): open the thread → post a reply → reply count increments, thread rises by last-activity.
   - As **student A**: see a `reply` notification in the notifications bell; open thread, confirm reply visible.
   - As **instructor**: pin the thread (badge appears, sorts first) → lock it → student B's reply box shows the locked notice and a reply POST is rejected; instructor can still reply.
   - As **instructor**: delete student B's reply (moderation) → gone. As **student A**: edit then delete own thread → replies cascade away.

---

## Notes for implementer
- Run `docker compose restart backend` after backend changes (per CLAUDE.md gotcha).
- Use `django.db.models.functions.Coalesce` + `Max`/`Count` for the list annotations.
- Add the notification `type` choice migration **before** wiring the reply notification, or the create call will fail validation.
- Follow the backend rule: every endpoint needs a pytest covering the instructor/enrolled/anonymous (or non-author) boundary.
