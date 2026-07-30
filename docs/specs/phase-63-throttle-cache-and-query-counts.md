# Phase 63 — Shared throttle cache + N+1 query elimination

## Goal

Two backend correctness/performance fixes that share a theme: things that are
silently more expensive (or weaker) in production than the code reads as. First,
DRF throttling currently stores its counters in Django's implicit
`LocMemCache` — there is no `CACHES` setting anywhere — while gunicorn runs
`--workers 2` (`render.yaml:43`). Every configured rate is therefore enforced
*per worker*, so production's real ceiling is roughly double what
`THROTTLE_ANON`, `THROTTLE_USER`, `THROTTLE_PASSWORD_RESET` et al. say, and it
would drift again with any worker-count change. This phase gives throttling a
dedicated, worker-shared cache alias. Second, six serializers run a database
query *per serialized object* — `LessonListSerializer` alone costs 4 queries per
lesson and is served by six different views, so a 40-lesson course detail is
~160 queries. This phase converts those to bulk lookups using the
`_completed_lesson_ids` context-caching idiom already proven in this file
(`courses/serializers.py:240-258`, phase 55 C7), and adds the query-count
regression guards that do not exist today. Backend only — no frontend diff, no
model change, no migration.

## Out of scope

- **Any migration.** The chosen cache backend is file-based specifically to
  avoid one. No model changes, no `AddIndex`, no cache table. If an
  implementation step appears to need a migration, stop and say so.
- **Explicit database indexes.** There are zero `db_index` / `Meta.indexes` in
  the project today. Eliminating the N+1s removes the queries entirely, which
  makes indexing them moot; revisit only if a *remaining* query is slow.
- **Adding a `DEFAULT_PAGINATION_CLASS`.** Deliberately absent
  (`core/pagination.py:3-7`) — it would reshape every list response and break
  the frontend at once. The N+1 fixes make the unpaginated endpoints cheap;
  pagination is a separate decision.
- **`UserSerializer.preferences`** — the reverse-OneToOne that costs 1 query per
  user across 7 nesting sites (`accounts/serializers.py:46`). Declined at
  scoping: it touches `accounts/` and widens the blast radius. Recorded as
  follow-up debt.
- **Changing any response body.** Every field keeps its exact current name,
  type, and value. This phase is invisible to the frontend; `frontend/` must
  have a zero-line diff.
- **Redis / Render Key Value**, and any new dependency in
  `backend/requirements.txt`.
- The carried backlog: XP double-award schema fix, JAVA101 answer-rotation
  reseed, phase-56 regression click-through, school-device login test, Sentry
  LoginPage TypeError, phase-62 manual fullscreen pass.
- `LessonProgressSerializer` (`courses/serializers.py:464-502`, 5-6 queries) —
  single-object endpoint only, cost does not scale. Leave it.

## Key decisions (from scoping interview + code exploration)

1. **A dedicated `throttle` cache alias backed by `FileBasedCache`; `default`
   stays `LocMemCache`.** The two gunicorn workers share one container and
   therefore one filesystem, so a file-backed store genuinely fixes the
   per-worker split with no new service, no new dependency, and no migration.
   Chosen over a Neon `DatabaseCache` because the `anon`/`user` scopes run on
   *every* request — routing those through Postgres would add ~4 queries to the
   hottest path in the app, trading a limit-accuracy bug for a latency bug.
   Accepted limitations, both to be documented in the settings comment:
   counters reset on deploy (unchanged from today), and the fix degrades back to
   per-instance if the service is ever scaled beyond one instance or during the
   brief overlap of a zero-downtime deploy.
2. **All throttle scopes move, not just the sensitive ones.** One alias, one
   `cache` attribute on the shared mixin — a per-scope split would be more code
   and would leave `anon`/`user` (the brute-force guards) still doubled.
3. **The cache backend is never touched locally or in tests except by tests that
   opt in.** `SimpleRateThrottle.allow_request` returns `True` immediately when
   `self.rate is None`, and every rate defaults to `None`
   (`config/settings.py:245-266`). So the new alias adds zero I/O to the other
   ~660 tests.
4. **The five existing `cache.clear()` sandwiches must be retargeted.** Throttle
   tests currently clear the *default* alias
   (`accounts/tests.py:357/377`, `:700/709`, `:732/755`;
   `courses/tests.py:3659/3675`, `:3683/3694`, `:3714/3724`). Once throttling
   uses `caches['throttle']`, those clears become no-ops and throttle history
   leaks between tests — an ordering-dependent failure that may not show up on
   the first run. This is the single highest-risk item in the phase.
5. **Context-caching in the serializer, not `annotate()` in each queryset.**
   `LessonListSerializer` is instantiated by six different views
   (`CourseViewSet`, `InstructorCourseViewSet`, `UnitViewSet`,
   `UnitViewSet.reorder`, `CourseUnitsView`, `LessonViewSet`); an annotation
   approach must be repeated in all six and silently breaks when a seventh
   caller forgets. Context-caching lives with the fields it feeds and works no
   matter who instantiates it. It also extends an idiom already in the file with
   a passing test guarding it.
6. **Priming happens in a `ListSerializer` subclass, via
   `Meta.list_serializer_class`.** The bulk query needs to know which lessons
   are in the response; only the `many=True` wrapper sees the whole list.
   `to_representation(data)` collects the pks, primes the shared context dict
   with any it doesn't already hold, then delegates to `super()`. Accepted cost:
   nested under `UnitSerializer(many=True)`, each unit primes separately, so a
   course with U units costs 3U queries rather than 3 — still O(units), not
   O(lessons) (40 lessons across 5 units: ~15 queries, down from ~160). A
   single-object (`many=False`) render falls back to the per-object query, which
   is correct and costs the same as today.
7. **The context dict accumulates; it is never overwritten.** `Serializer.context`
   walks `self.parent` to the root and returns one shared `_context` dict, so a
   nested `ListSerializer` mutating it is visible to every sibling. Prime with
   `dict.setdefault`-style merging so unit 2 does not discard unit 1's entries.
   The dict lives for exactly one response — never cache a serializer instance
   across requests.
8. **`Quiz.question_count` is a read-only model `@property`
   (`quizzes/models.py:25-27`) that runs `.count()`.** So `QuizListSerializer`
   costs **4** per-quiz queries, not 3. Do **not** annotate under the name
   `question_count`: Django assigns annotations with `setattr`, and a read-only
   `property` is a data descriptor, so the assignment raises. Annotate under a
   distinct name and point the serializer field at it with `source=`.
9. **`attempts_remaining` reuses `attempt_count`'s result.**
   `quizzes/serializers.py:69-86` runs the identical
   `obj.attempts.filter(student=user, status=COMPLETED).count()` twice per quiz.
   Even before bulk lookups, that is a free 25% cut.
10. **Regression guards assert per-table counts with a varied result-set size**,
    following `courses/tests.py:4176-4198`: filter `ctx.captured_queries` to the
    specific table, create ~12 objects, assert an exact small count. Immune to
    unrelated query churn, and fails loudly if a fix regresses to per-object.
    Not `assertNumQueries` on the whole response — an unrelated middleware query
    would break it with an unhelpful message.

## Backend tasks

### A. Shared throttle cache (sequential — A2 depends on A1, A3 on A2)

- [x] **A1.** Add a `CACHES` block to `backend/config/settings.py` (there is
      none today; insert it near the `DATABASES` block at `:110-130`). Keep
      `default` as `LocMemCache` explicitly — do not leave it implicit, or a
      reader will assume `throttle` is the only cache. Add a `throttle` alias:
      `django.core.cache.backends.filebased.FileBasedCache`, `LOCATION` from
      `config('THROTTLE_CACHE_DIR', default=<system temp>/stemquest-throttle)`,
      and `OPTIONS: {'MAX_ENTRIES': 5000, 'CULL_FREQUENCY': 4}`. The default
      `MAX_ENTRIES` of 300 is too low — one key per client IP plus one per user
      id means a single class of 200 students can exceed it, and culling would
      start dropping live throttle counters. Do **not** set a `TIMEOUT`: DRF
      passes its own per-key duration to `cache.set()`.
- [x] **A2.** Comment the block with the reasoning from decisions 1 and 3: why
      file-based and not database (the `anon`/`user` scopes are on every
      request), why it works (both workers share one container filesystem), that
      counters reset on deploy, and that it degrades to per-instance if the
      service is ever scaled past one instance. Reference `render.yaml:43`.
- [x] **A3.** In `backend/core/throttling.py`, add
      `cache = caches['throttle']` to `ClientIPIdentMixin` (`:31-43`) so all four
      throttle classes inherit it — `ClientIPAnonRateThrottle` (`:46`),
      `ClientIPUserRateThrottle` (`:50`), `ClientIPScopedRateThrottle` (`:71`),
      and `ClientIPScopedWriteRateThrottle` (`:75`). Import `caches` from
      `django.core.cache`. Verify by reading DRF's `SimpleRateThrottle` that
      `cache` is a plain class attribute (it is `cache = default_cache`) and that
      nothing else in the MRO reassigns it.
- [x] **A4.** Add `THROTTLE_CACHE_DIR` to `.env.example` (near the other
      `THROTTLE_*` entries at `:30-55`) and to the names-only env inventory
      comment in `render.yaml` (`:60-63`), noting it is optional — the default
      is fine on Render.
- [x] **A5.** [P] Close the unthrottled-read gap on
      `GET /api/courses/<code>/invites/`. `@throttle_classes` *replaces*
      `DEFAULT_THROTTLE_CLASSES`, and `ClientIPScopedWriteRateThrottle` exempts
      safe methods — so that GET currently has no throttle at all. Add
      `ClientIPUserRateThrottle` to the decorator list at `courses/views.py:1631`,
      exactly as `lesson_section_import_slide` already does
      (`courses/views.py:2823-2827`, including its explanatory comment). Leave
      `demo_login` (`accounts/views.py:37`), the password-reset view
      (`accounts/views.py:90`), and `accept_invite` (`courses/views.py:1768`)
      alone: each drops the global classes too, but their scoped rate is
      strictly tighter than `anon`/`user`, so nothing is lost.

### B. `courses/` N+1 — [P] with C and D (different files)

- [x] **B1.** Add a `LessonListListSerializer(serializers.ListSerializer)` in
      `courses/serializers.py` and wire it via
      `LessonListSerializer.Meta.list_serializer_class`. Its
      `to_representation(data)` materializes `data`, collects the lesson pks not
      already primed, and populates three context keys with one bulk query each,
      then calls `super().to_representation(...)`. Merge into whatever is already
      in the context (decision 7) — never replace.
- [x] **B2.** Convert the four count fields on `LessonListSerializer` to read the
      primed maps, falling back to the current per-object query when the key is
      absent (single-object render, or a caller that bypassed the list wrapper):
      - `get_question_count` (`:281-282`) ← `Count` over `Question` by `lesson_id`
      - `get_attachment_count` (`:270-271`) ← `Count` over `LessonAttachment`
      - `get_section_count` (`:273-274`) ← `Count` over `LessonSection`
      - `get_has_video` (`:276-279`) ← the *same* `LessonSection` pass as
        `section_count`; do not issue a second query. `values_list('lesson_id',
        'video_type', 'video_id')` gives both the count and the
        `video_type == 'youtube' and video_id != ''` test in one go.
      Leave `get_is_completed` (`:260-268`) and `_completed_lesson_ids`
      (`:240-258`) untouched — they already work and are already guarded.
- [x] **B3.** Apply the same treatment to `LessonSerializer` (`:122-207`):
      `get_question_count` (`:199-200`), `get_section_count` (`:202-203`),
      `get_has_video` (`:205-207`). Note this serializer *also* nests
      `attachments` (`:125`) and `sections` (`:126`) as `many=True`, so
      `has_video` is re-querying data the response already loaded — prefer
      deriving it from the prefetched `sections` where the queryset provides one.
      Add `prefetch_related('sections', 'attachments', 'questions')` to
      `LessonViewSet.get_queryset` (`courses/views.py:270-276`), which today has
      `select_related('unit__course')` and no prefetch at all, and to
      `UnitLessonsView.get_queryset` (`:384-387`), which has nothing.
- [x] **B4.** `CourseSerializer.get_student_count` (`:320-321`) and
      `get_is_enrolled` (`:323-327`) — both use `.filter()`, which rebuilds the
      queryset and defeats the existing `prefetch_related('enrollments')` in
      `CourseViewSet.get_queryset` (`courses/views.py:69-71`). Change the
      prefetch to a filtered `Prefetch('enrollments', queryset=...is_active=True)`
      and compute both fields from the prefetched cache, or annotate. Apply the
      same fix to `CourseListSerializer.get_student_count` (`:357-358`) and
      `InstructorCourseSerializer.get_student_count` (`:390-391`); note
      `InstructorCourseViewSet.get_queryset` (`:158-161`) is also missing
      `select_related('instructor')`.
- [x] **B5.** `StudentRosterSerializer.get_progress_percentage` (`:606-618`)
      recomputes `Lesson.objects.filter(unit__course=obj.course).count()` — an
      identical value — once per student, and `obj.course` is itself an
      unfetched FK (the roster queryset does `select_related('user')` but not
      `'course'`, `courses/views.py:1220-1246`). Cache the course lesson total on
      the context and bulk-load per-student completed counts in one grouped
      query. This endpoint is paginated at 100/page, so it is up to 300 queries
      per page today.
- [x] **B6.** [P] `InstructorReminderViewSet.get_queryset`
      (`courses/views.py:3013-3017`) has no `select_related`, so
      `InstructorReminderSerializer.get_course_code` (`:751-752`) costs 1 query
      per reminder. Add `select_related('course')`. One-line fix, no serializer
      change.

### C. `quizzes/` N+1 — [P] with B and D

- [x] **C1.** `QuizListSerializer` (`quizzes/serializers.py:37-86`) — 4 queries
      per quiz. Fix `get_attempts_remaining` (`:77-86`) to reuse the count
      already computed by `get_attempt_count` (`:69-75`) rather than re-running
      the identical query (decision 9), then bulk-load the attempt aggregates for
      the whole result set via the same `ListSerializer` priming pattern as B1.
      `get_best_score` (`:54-67`) needs the best completed attempt per quiz for
      the requesting user — one grouped query, not one `.first()` per quiz.
- [x] **C2.** Replace the `Quiz.question_count` property access with an
      annotation on both feeding querysets — `unit_quizzes`
      (`quizzes/views.py:36`, currently a bare `Quiz.objects.filter(unit=unit)`)
      and `course_quizzes` (`:506`). **Annotate under a different name** and set
      `source=` on the serializer field (decision 8); leave the model property in
      place for other callers. Both querysets also need `select_related('unit',
      'unit__course')` — `unit_title` and `course_code`
      (`quizzes/serializers.py:42-43`) are FK traversals costing 2 more queries
      per quiz on `unit_quizzes`.
- [x] **C3.** `AttemptAnswerSerializer.get_correct_choice_text`
      (`quizzes/serializers.py:204-206`) runs
      `obj.question.choices.filter(is_correct=True).first()` per answer row, and
      `question_text` / `selected_choice_text` (`:193-194`) add FK traversals.
      It is nested `many=True` under `QuizAttemptSerializer.answers` (`:211`).
      Add `prefetch_related('answers__question__choices',
      'answers__selected_choice')` to `quiz_attempts` (`quizzes/views.py:479-486`,
      currently `select_related('student')` only) and derive the correct choice
      from the prefetched cache. Check the other two call sites — `submit_quiz`
      (`:251`) and `answer_quiz_session` (`:454`) — and make the derivation
      fall back safely when no prefetch is present.
- [x] **C4.** [P] `quiz_detail` (`quizzes/views.py:65-95`) serves
      `QuizDetailSerializer` (`:89`) with nested `questions` → `choices` and no
      prefetch, costing 1 query per question. Add
      `prefetch_related('questions__choices')`. Serializer unchanged.

### D. `discussions/` N+1 — [P] with B and C

- [x] **D1.** `thread_detail` (`discussions/views.py:60`) is a bare
      `get_object_or_404(Thread, id=thread_id)` feeding `ThreadDetailSerializer`,
      whose nested `replies` (`discussions/serializers.py:45`) each nest
      `UserSerializer(author)`. A 50-reply thread is ~100 queries. Add
      `prefetch_related('replies__author')` and `select_related('course',
      'author')`. Apply the same to `toggle_pin` (`:116`) and `toggle_lock`
      (`:133`), which re-serialize the same object.
- [x] **D2.** Confirm `course_threads` (`discussions/views.py:35-37`) needs no
      change beyond what it has — it already annotates `reply_count` and
      `last_activity` and does `select_related('author')`. The only remaining
      per-thread query is `UserSerializer.preferences`, which is explicitly out
      of scope. Record that in a comment so the next reader doesn't re-derive it.

### E. Tests

- [x] **E1.** Retarget the five throttle-test cache sandwiches to the new alias
      (decision 4): `accounts/tests.py:357/377`, `:700/709`, `:732/755`;
      `courses/tests.py:3659/3675`, `:3683/3694`, `:3714/3724`. Prove the change
      is real — before touching them, run one throttle test twice in the same
      session and confirm the second run fails without the retarget, then fix.
      Keep the `try/finally` shape and the existing comment about DRF snapshotting
      `THROTTLE_RATES` onto the class at import.
- [x] **E2.** Add a test in `backend/core/tests/test_throttling.py` asserting the
      throttle classes resolve to the `throttle` alias and **not** to
      `caches['default']` — i.e. that a write through a throttle class is
      invisible to `caches['default']`. This is the assertion that would catch
      someone later removing the `cache` attribute. Parametrize over the existing
      `ALL_THROTTLES` list (`:34-39`).
- [x] **E3.** [P] Query-count guards, one per fixed endpoint, following
      `courses/tests.py:4176-4198` exactly (filter `captured_queries` by table
      name, assert an exact small count, with ~12 objects created so a
      per-object regression is unmissable):
      - course detail with 12 lessons → `courses_lessonsection`,
        `courses_lessonattachment`, `quizzes_question` each bounded by unit count
      - `LessonViewSet.list` with 12 lessons
      - roster with 12 students → `courses_lessonprogress` and `courses_lesson`
      - `unit_quizzes` with 12 quizzes → `quizzes_question`, `quizzes_quizattempt`
      - `quiz_attempts` with 12 answers → `quizzes_choice`
      - `thread_detail` with 12 replies → the user table
- [x] **E4.** [P] Response-shape guards: for each touched endpoint, assert the
      serialized values are **unchanged** — a lesson with 2 sections still reports
      `section_count == 2`, `has_video` is still `True` only for a YouTube section
      with a non-empty `video_id`, a quiz with 3 completed attempts and
      `max_attempts=5` still reports `attempts_remaining == 2`. Include the
      zero/empty cases (a lesson with no sections, a student with no progress, a
      quiz with `max_attempts=0` → `attempts_remaining is None`) — bulk lookups
      classically lose the rows that have no related objects.
- [x] **E5.** [P] Assert the `many=False` fallback path still works: render
      `LessonListSerializer(lesson)` (no `many=True`) directly and confirm the
      counts are correct without the `ListSerializer` priming.

## Frontend tasks

None. `git diff --stat main -- frontend/` must be empty at PR time — this phase
changes no response shape (decision: Out of scope, "Changing any response body").

## Verification

Run `/verify-stack` and show the output. It must report:

- **Backend:** `pytest` — all 665 existing tests pass, plus the new throttle and
  query-count cases. Any pre-existing test that changes its expected query count
  is a red flag, not a number to update: check it isn't a behavior change.
- **Migrations:** `python manage.py makemigrations --check --dry-run` — "No
  changes detected". This phase must produce no migration (Out of scope).
- **Types / lint / unit:** `npx tsc --noEmit` 0 errors, `npm run lint` 0 errors
  (1 pre-existing warning at `ErrorBoundary.tsx:117`), `npx vitest run` 101 tests
  pass — all three unchanged, since `frontend/` has a zero-line diff.
- **Build:** `npm run build` succeeds, bundle sizes unchanged from phase 62.

Backend-specific checks beyond the standard suite:

1. **Prove the throttle cache is shared across processes.** Boot two shells into
   the same container, set `THROTTLE_ANON=3/min`, and issue requests from both
   until the 4th is a 429 — i.e. the counter is shared, which it would not be
   under `LocMemCache`. If two processes can't be arranged, the equivalent is a
   test that writes a throttle key in one `caches['throttle']` handle and reads
   it back through a freshly constructed backend instance, plus confirming
   `caches['default'].get(key)` is `None`.
2. **Confirm the cache directory is created and written.** With a rate set, hit a
   throttled endpoint and check that `THROTTLE_CACHE_DIR` exists and contains
   files. Then confirm the directory is *not* created during a normal test run
   with all rates unset (decision 3).
3. **Run the throttle tests twice in one session** (`pytest accounts/tests.py -k
   throttle` twice, and once with `-p no:randomly` if ordering plugins are
   active) — they must pass both times. This is the check that catches E1 being
   done wrong.
4. **Measure the course-detail improvement.** Seed a course with ~5 units and ~40
   lessons, then count total queries for `GET /api/courses/courses/<code>/`
   before and after. Record both numbers in the PR body. Expect roughly 160+ →
   under 25.
5. **Diff the API responses byte-for-byte.** For course detail, lesson list,
   `unit_quizzes`, `quiz_attempts`, and `thread_detail`: capture the JSON on
   `main`, capture it on the branch with identical seed data, and diff. Any
   difference is a bug in this phase — the goal is fewer queries, not different
   output.

Manual click-through (local, then the same paths on production after deploy):

6. Load a course detail page as a student — lesson cards show the same section /
   attachment / question counts and the same video badges as before, and the
   completed ticks are unchanged.
7. Open the instructor roster for a course with several students — progress
   percentages match what they showed before, including 0% for a student with no
   progress.
8. Open a quiz list as a student who has used some attempts — `attempts_remaining`
   is right, and a quiz with unlimited attempts still shows no limit.
9. Review a submitted quiz attempt — every answer row still shows the correct
   choice text.
10. Open a discussion thread with several replies — all authors render.
11. **Throttling still fires in production.** After deploy, confirm a throttled
    endpoint still returns 429 when hammered (the demo-login endpoint at 10/min
    is the safe one to test), and confirm normal browsing is *not* throttled —
    a mis-set `MAX_ENTRIES` or a cache-directory permission error would show up
    as either no throttling at all or spurious 429s.

## Assumptions / deviations

Implemented on `feat/phase-63-throttle-cache-and-query-counts`. Every checklist
item landed. Deviations from the letter of the spec, all deliberate:

1. **`cache` is a property on `ClientIPIdentMixin`, not a class attribute**
   (A3). A bound attribute would freeze one thread's backend instance at import
   and make `override_settings(CACHES=...)` unreachable from tests. Verified
   against DRF's source that `self.cache` is only ever read
   (`throttling.py:123`, `:140`) and never assigned, so a read-only property is
   safe.
2. **Six `cache.clear()` sandwiches, not five** (decision 4 / E1). The spec
   undercounted: three in `accounts/tests.py`, three in `courses/tests.py`,
   12 call sites in total.
3. **The leak is worse than "ordering-dependent"** (decision 4). Because the
   new alias is file-backed, throttle history survives *entire pytest
   sessions*, not just other tests in the same run. Proven before fixing: a
   two-test probe using the old default-alias clear had **both** tests 429 on
   their first request, the first one poisoned by a previous pytest session.
   The existing 19 throttle tests passed anyway — no two of them share a
   scope+ident pair — so this would have shipped silently. Retargeting the
   clears fixes it in both directions, since clearing at test start also wipes
   anything left by a prior session.
4. **Verification step 2 was wrong about the mechanism.** It expected the cache
   directory not to exist after a rate-free test run. `FileBasedCache.__init__`
   calls `_createdir()`, so the directory appears as soon as anything *touches*
   `caches['throttle']`, well before any write. What decision 3 actually claims
   — that rate-free runs do no cache I/O — holds: the directory is created and
   stays **empty** (0 files) after a full rate-free run.
5. **The stats mixin prefers a prefetch cache when the view provides one**
   (B2/B3). `LessonSerializer`'s views already load sections and attachments in
   full, so those render for zero further queries; course detail uses the bulk
   path, because prefetching sections there would pull every section's markdown
   `content` into memory purely to count rows. `LessonViewSet` applies the
   prefetch only to detail actions for the same reason.
6. **`unit_count` switched from `.count()` to `len(.all())`**
   (`CourseListSerializer`). `.count()` on a prefetched related manager still
   issues a query; only iterating the cache is free. Same value, one less query
   per course.
7. **`student_count`/`is_enrolled` use a `to_attr` prefetch, not an annotation**
   (B4). Both fields called `.filter()` on the related manager, which rebuilds
   the queryset regardless of prefetching. `Prefetch(..., to_attr=
   'active_enrollments')` cannot collide with the plain
   `prefetch_related('enrollments')` used elsewhere.
8. **`QuizQuestionCountField` wraps the annotation** (C2). A plain
   `IntegerField(source='annotated_question_count')` was measured to *drop*
   `question_count` from the payload entirely for any caller that bypasses the
   annotated queryset — DRF converts a missing read-only source into
   `SkipField` rather than raising. That is a response-shape change, which this
   phase forbids, so the field catches `SkipField` and falls back to the model
   property.
9. **`select_related('quiz')` added to `quiz_attempts`** beyond C3's letter.
   `QuizAttemptSerializer.quiz_title` was one query per attempt; the fix is one
   word and the endpoint was already being touched. Guarded by
   `test_adding_attempts_does_not_add_queries`.
10. **The roster completed-counts query is scoped by course, not by page.** One
    grouped query returning `(user_id, count)` pairs serves every row without a
    list wrapper to prime it. Slightly more rows than the page on a large
    course, but two integers each, and it removes a per-student query.

### Measured results

Query counts, via `CaptureQueriesContext` on identical seed data, `main` vs
branch:

| Endpoint | Objects | Before | After |
|---|---|---|---|
| Course detail | 40 lessons / 5 units | **168** | **21** |
| `unit_quizzes` (student) | 13 quizzes | 82 | 6 |
| `course_quizzes` (student) | 13 quizzes | 68 | 5 |
| `quiz_attempts` | 1 attempt / 12 answers | 44 | 11 |
| `quiz_detail` (instructor) | 12 questions | 18 | 6 |
| `thread_detail` | 50 replies, 50 authors | 107 | 56 |
| `thread_detail` | 50 replies, 1 author | 107 | 7 |

The residual per-author cost on `thread_detail` is
`UserSerializer.preferences`, explicitly out of scope — it is one query per
*distinct* author, not per reply, which is why the single-author case collapses
to 7.

Response bodies were captured on `main` and on the branch with identical seed
data across seven endpoints (course detail as student and as instructor, course
list, lesson detail, lesson list, roster, instructor courses) — including a
lesson with no related rows, a section with a blank `video_id`, and an inactive
enrollment. The diff is **empty**.

Cross-process sharing was proven directly: one process wrote a throttle bucket
through `ClientIPAnonRateThrottle`, a second, separately-launched process read
the same value back, while a value written to the default `LocMemCache` in the
first process was invisible to the second. That is the two-worker scenario the
phase exists to fix.
