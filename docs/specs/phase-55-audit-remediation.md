# Phase 55 — Audit remediation: security, hygiene, drift, test infrastructure

## Goal

Phase 54 shipped and deployed cleanly, and a full-repo audit found no outstanding
deploy debt — but it did surface a backlog that has been accumulating quietly
across the deployment track. Four things need fixing: (1) auth- and
image-handling dependencies carrying known CVEs, plus two genuine authorization
gaps (an unscoped lesson-move FK and an unvalidated avatar upload); (2) a
`.gitignore` bug that has been silently excluding `docs/archive/` from the
repository entirely, alongside tracked build artifacts and ~60 stale doc
references; (3) dead code from the phase 52–54 consolidations, including a
seeding drift that makes local and CI exercise a *different* lesson-completion
gate than production; and (4) the absence of any frontend test runner and unused
backend coverage tooling. This phase clears all four so the Django 5.2 LTS
upgrade (Phase 56) starts from a clean base.

## Non-goals / out of scope

- **Django 4.2 → 5.2 LTS.** Deferred to Phase 56 by decision. Django 4.2 is past
  EOL (April 2026) and 4.2.30 is its final patch; that upgrade is entangled with
  the `django-allauth` settings renames and deserves its own phase.
- **Multi-instructor tenant isolation.** Confirmed single-instructor for now.
  `CourseViewSet.get_queryset` returning all courses to any instructor
  (`backend/courses/views.py:63-76`) is left as-is and recorded as a follow-up.
  The lesson-move fix below IS in scope — it is cheap and also prevents an
  accidental data-corrupting PATCH.
- **Deleting `render.yaml`.** Phase 48 retired it; **phase 49 re-adopted it**
  (`render.yaml:1-21` — service shape is live-synced on push to main). Deleting
  or editing `plan:`/`region:` would downgrade the instance and re-break SMTP
  egress. Do not touch it.
- **Applying any migration to Neon.** Migrations `0017`–`0020` are already
  applied (verified). New migrations in this phase are written and applied
  locally only; the Neon apply is an explicit operator step at merge time.
- **Global DRF pagination.** Adding `DEFAULT_PAGINATION_CLASS` changes every list
  response to `{count, next, previous, results}` and would break the frontend
  everywhere. Only the two genuinely unbounded endpoints are paginated here; the
  rest is a follow-up.
- **Large refactors.** `CoursePlayerPage.tsx` (825 lines) and
  `backend/courses/views.py` (3,206 lines) both want splitting. Not this phase.
- Making the 6 private `docs/*.md` files tracked — they stay gitignored, content
  refreshed only.

---

## Track A — Dependencies & security

### A1. Backend dependency upgrades (`backend/requirements.txt`)

Verified via `pip-audit` inside the backend container.

- [ ] `django-allauth` 65.3.0 → **65.14.1** (PYSEC-2025-110, -111, PYSEC-2026-56).
      **Not drop-in**: `backend/config/settings.py:331-337` uses the deprecated
      `ACCOUNT_EMAIL_REQUIRED` / `ACCOUNT_AUTHENTICATION_METHOD` /
      `ACCOUNT_USERNAME_REQUIRED`. Migrate to `ACCOUNT_LOGIN_METHODS` /
      `ACCOUNT_SIGNUP_FIELDS` and confirm the demo lockdown still holds
      (`backend/accounts/urls.py:8-12` must still refuse to mount registration
      when `ALLOW_REGISTRATION=False`).
- [ ] `djangorestframework-simplejwt` 5.5.0 → **5.5.1** (PYSEC-2026-1305).
- [ ] `pyjwt` → **2.13.0** (7 advisories). Transitive via simplejwt — pin it
      explicitly in `requirements.txt` so it can't drift back.
- [ ] `pillow` 11.1.0 → **12.3.0** (~20 advisories). Directly relevant to A3.
      Verify Django 4.2 compatibility before committing.
- [ ] Pin `requests` (currently `requests>=2.31.0` at line 19 — the only unpinned
      entry in an otherwise fully pinned file).
- [ ] Re-run `pip-audit` and record the remaining findings. `pip` itself will
      still report advisories; that's the container's pip, not an app dependency.

### A2. Cross-course lesson move (unscoped writable FK)

`backend/courses/serializers.py:116-123` — `unit` is in `fields` and absent from
`read_only_fields`. `LessonViewSet.get_serializer_class`
(`backend/courses/views.py:274-277`) returns `LessonSerializer` for
`update`/`partial_update`, `perform_update` is not overridden, and
`IsEnrolledOrInstructor.has_object_permission`
(`backend/courses/permissions.py:130-149`) resolves the course from
`obj.unit.course` — the **source** course only. So
`PATCH /api/courses/lessons/<id>/ {"unit": <unit in another course>}` moves the
lesson out of its course with no check on the destination.

The `reorder` action already guards exactly this
(`backend/courses/views.py:314-326` validates
`target_unit.course_id != source_unit.course_id` and re-checks
`require_course_instructor` on both, with a test at
`backend/courses/tests.py:1334`). The plain PATCH path has no equivalent and no test.

- [ ] Add a `validate_unit` to `LessonSerializer` that rejects a target unit
      whose `course_id` differs from the instance's current course, and re-checks
      `require_course_instructor` on the target. Mirror the `reorder` precedent
      rather than inventing a new pattern.
- [ ] Test: instructor PATCHes their lesson's `unit` to a unit in a course they
      do not own → 400/403, lesson unmoved.
- [ ] Test: instructor PATCHes `unit` to another unit **within the same course**
      → still allowed (don't over-tighten).

### A3. Avatar upload accepts arbitrary content [P]

`backend/accounts/views.py:131-160` assigns `request.FILES['avatar']` straight to
an `ImageField` (`backend/accounts/models.py:101-105`). `save()` does not call
`full_clean()`, so there is **no Pillow verification, no content-type check, no
extension allowlist** — only the 5 MB `AVATAR_MAX_UPLOAD_BYTES` cap at line 144.
`.html`/`.svg`/`.js` payloads store fine. Production impact is bounded (R2 private
bucket, presigned URLs on a foreign origin), but under `DEBUG=True` media is
served same-origin from `/media/` (`backend/config/urls.py:39-41`) — stored XSS
on the API origin during local dev.

`lesson_attachments` already does this correctly
(`backend/courses/views.py:2657-2695`: extension allowlist deliberately excluding
`svg`/`html` with a rationale comment, per-file size cap, file-count cap).

- [ ] Apply the same pattern to `upload_avatar`: extension allowlist
      (`png/jpg/jpeg/gif/webp`, explicitly **not** `svg`), content-type check, and
      a Pillow `Image.open(...).verify()` pass. Keep the existing size cap.
- [ ] Tests: `.svg` rejected; `.html` renamed to `.png` rejected (content, not
      just extension); a valid PNG still uploads.

### A4. Demo account can permanently self-unenroll [P]

`backend/courses/views.py:395-420` — `EnrollmentViewSet` is a full `ModelViewSet`
with no `destroy` override, so `DELETE /api/courses/enrollments/<id>/` **hard**
deletes the row. The instructor-side `remove_student` soft-deletes instead
(`backend/courses/views.py:1537-1539`). Every visitor shares `jdoe@demo.com`, so
one visitor un-enrolls the demo account for everyone until an operator re-runs
`seed_demo_account`.

- [ ] Override `destroy` to soft-delete (`is_active=False`), matching
      `remove_student`.
- [ ] Refuse the operation entirely for the demo account, consistent with the
      rest of the demo lockdown (`backend/accounts/serializers.py:167-181` is the
      precedent).
- [ ] Tests: demo account DELETE → refused; a normal student's DELETE →
      soft-deleted, not removed from the table.

### A5. Throttle ident hardening (defense-in-depth) [P]

`backend/core/throttling.py:23-25` returns `HTTP_CF_CONNECTING_IP` verbatim.
**Verified not currently exploitable**: a request carrying that header to
`stemquest-api-va.onrender.com` is rejected by Cloudflare's edge with
`error code: 1000` / 403 before it reaches Django, and a Render web service has
no separately-addressable public origin. This is belt-and-braces only — do not
treat it as an incident.

- [ ] Gate the header on an explicit `TRUST_CF_HEADERS` setting (default on in
      production, off in dev/tests) so the trust boundary is stated in code
      rather than implied by a docstring.
- [ ] Test in the new `backend/core/tests/` (D4): header honored when trusted,
      ignored when not.

### A6. Pagination on unbounded endpoints [P]

`backend/config/settings.py:199-246` sets no pagination default. Scoped
deliberately narrow — see out-of-scope note.

- [ ] Paginate `NotificationListView` (`backend/notifications/views.py`) — grows
      without bound per user — and update the matching frontend service call to
      read `results`.
- [ ] Cap or paginate `student_roster`. Leave `gradebook` and `analytics_*`
      alone (custom `@api_view` matrices; a pagination class won't apply cleanly)
      and record them as a follow-up.

### A7. Frontend dependency upgrades (`frontend/package.json`)

Verified via `npm audit` — 14 advisories (11 high).

- [ ] `axios` ^1.7.9 → **^1.18.1** (SSRF, prototype pollution, credential leak —
      the one runtime-critical bump).
- [ ] `npm audit fix` for the build-chain packages (`vite`, `rollup`, `postcss`,
      `minimatch`, `picomatch`, `brace-expansion`, `flatted`, `js-yaml`,
      `form-data`, `follow-redirects`, `ajv`, `@babel/core`). These are
      build-time only.
- [ ] **Decision point — `react-router` 7.13.0 → 8.3.0 is a MAJOR bump.** The
      advisory range is `6.0.0 - 8.2.0`, so no patch exists within v7. Most of
      the listed CVEs (RSC hydration, SSR single-fetch, `__manifest`, prerendered
      redirect HTML) do not apply to this app's declarative SPA usage, but the
      open-redirect-via-backslash in `<Link>`/`useNavigate` does. **Attempt the
      v8 migration; if it is more than mechanical, stop, revert, and record it as
      Phase 56b** rather than absorbing a router migration into this phase.
      Whichever way it goes, write the outcome into this spec.

### A8. Supply-chain automation (this is why the above drifted)

- [ ] Add `.github/dependabot.yml` covering `pip` (`/backend`), `npm`
      (`/frontend`), and `github-actions`, weekly, grouped minor+patch.
- [ ] Add a `pip-audit` step to the backend CI job
      (`.github/workflows/ci.yml`) — fail on HIGH, with an ignore list for
      non-app packages (`pip` itself).
- [ ] Add `npm audit --audit-level=high` to the frontend CI job. If A7's router
      decision defers the bump, add the documented exception here so CI stays
      green and the debt stays visible.

---

## Track B — Docs & repo hygiene

### B1. `.gitignore` correctness — DO THIS FIRST

**Ordering constraint: B1 must land before B5, or the archive moves become
silent deletions.**

- [ ] `.gitignore:3` — change bare `PLAN.md` to `/PLAN.md`. The bare pattern
      matches at **any depth**, so phase 50's `git mv PLAN.md docs/archive/PLAN.md`
      produced a file on disk that git ignores. Verified:
      `git ls-files docs/archive/` returns 0 files and
      `git check-ignore -v docs/archive/PLAN.md` → `.gitignore:3`. The archive
      that `CLAUDE.md:25` points every future session to **does not exist in the
      repo**.
- [ ] `git add docs/archive/PLAN.md` (74 KB, retirement header already correct).
- [ ] `.gitignore:6` — narrow `docs/*.md` to the 6 named private files
      (`PORTFOLIO.md`, `INTERVIEW_GUIDE.md`, `DEMO_SCRIPT.md`,
      `SCREENSHOT_CHECKLIST.md`, `CLAUDE-CODE-WORKFLOW.md`, `PROMPT-REFERENCE.md`),
      so a future doc dropped at `docs/` root isn't silently swallowed.
- [ ] Add `*.tsbuildinfo`; `git rm --cached frontend/tsconfig.tsbuildinfo`
      (tracked build artifact, currently dirty, churns on every `tsc`).
- [ ] `git rm -r --cached backups/pre-phase-12.6/` — 8 tracked source snapshots
      from 42 phases ago; git history already has them.
- [ ] Add `skills-rules-agents-interview-notes.txt` (untracked, un-ignored at
      root — one `git add -A` from being published).
- [ ] Deduplicate `*.log` (present at both `.gitignore:24` and `:71`).

### B2. Commit the pending working-tree state

- [ ] Commit `docs/runbooks/workflow-prompting-guide.txt` (untracked, current).
- [ ] Commit `docs/handoffs/2026-07-23-phase-52-followup-fix.md` (untracked).
- [ ] Resolve the modified `docs/handoffs/2026-07-23-phase-53-content-consolidation.md`
      (+47 lines seeding the phase-54 brief — that work shipped, so commit it as
      history or drop it deliberately; don't leave it dangling).
- [ ] Fast-forward local `main` to `lms/main` (currently 4 commits behind).

### B3. Factual errors in tracked, reader-facing docs [P]

- [ ] `README.md:119` and `README.md:189` — both say "DRF token auth".
      `backend/config/settings.py:200-204` uses
      `dj_rest_auth.jwt_auth.JWTCookieAuthentication`, `:363` sets `USE_JWT: True`,
      and `frontend/src/services/api.ts:20` sends `Authorization: Bearer` with
      refresh rotation at `:99-104`. `rest_framework.authtoken` isn't installed.
      Fix to JWT. (`CLAUDE.md:8` already gets this right.)
- [ ] `README.md:31, :34, :38` — user-facing "sections" → "pages" per phase 54.
      Leave `:173` (`# Courses, units, lessons, sections, progress`) — the backend
      model really is `LessonSection`.
- [ ] `README.md:170-176` — project structure omits `backend/core/`.
- [ ] `docs/deployment-tools.txt:50` — `stemquest-api.onrender.com` →
      `stemquest-api-va.onrender.com` (retired host).
- [ ] `docs/deployment-tools.txt:54` — the `render.yaml` claim contradicts
      `render.yaml:1-21`; rewrite to "service shape syncs, env vars are
      dashboard-only".
- [ ] `docs/deployment-tools.txt:252` — "376 tests" → actual count (435 `def
      test_` functions at audit time; re-count after Track D).
- [ ] `docs/specs/deployment-overview.md` — add a superseded banner. It is linked
      from `README.md:107` as the deployment "deep dive" and is wrong on five
      counts: Cloudflare Pages (now assets-only Workers), Grafana Cloud (never
      shipped; Sentry + UptimeRobot did), "no custom domain" (phase 51 shipped
      `stemquests.com`), `frontend/public/_redirects` (the file is `_headers`),
      and "deploys are not hard-gated on CI" (`README.md:105` says a red run
      blocks the merge). The file already carries phase 47/48 addenda — extend
      that pattern.

### B4. Private docs refresh (stay gitignored) [P]

Per decision: keep private, refresh content. All 6 describe a product that no
longer exists — WebSockets, assignments (removed phase 18), VGD101, "GameDev
Learning Platform" (renamed phase 27).

- [ ] `docs/PORTFOLIO.md:91` — publishes the **archived** repo URL
      `Cesar6060/dev-learning-platform`; the live repo is `Cesar6060/LMS`. Also
      `:4, :10, :12, :26, :32, :42` claim WebSockets/Redis/assignments.
- [ ] `docs/INTERVIEW_GUIDE.md:1` and the 30-second pitch — same false claims,
      plus "runs in Docker containers" (production runs no containers,
      `README.md:122`).
- [ ] `docs/DEMO_SCRIPT.md` — scripts `VGD101` / `instructor@demo.com` /
      submission grading; the live demo is `JAVA101` / `jdoe@demo.com`,
      student-only (`README.md:16`, phase 44).
- [ ] `docs/SCREENSHOT_CHECKLIST.md:14-18` — superseded by the shipped
      `docs/screenshots/` from phase 45.
- [ ] `docs/CLAUDE-CODE-WORKFLOW.md:23, :54` and `docs/PROMPT-REFERENCE.md:24, :187`
      — still instruct readers to use `PLAN.md` as a live roadmap.
- [ ] `CLAUDE.md:20` — lists a nonexistent `assignments` app (removed phase 18,
      asserted gone by `backend/config/tests/test_url_conf.py:64`) and omits
      `discussions`, `gamification`, `core`. `CLAUDE.md:37` — drop the "until
      Phase 5" framing (49 phases stale).

### B5. Archive the historical record (after B1)

- [ ] Create `docs/archive/{handoffs,specs,runbooks}/`.
- [ ] Move 37 pre-phase-45 handoffs (including `2026-07-17-setup.md` and
      `2026-07-19-stem-quest-pivot-plan-revision.md`), leaving phases 45–54 live.
      **Move, never delete** — several are the only narrative record of live-infra
      decisions still in force (phase 38 Neon/Render creation, phase 40 monitors,
      phase 43 CSP, phase 44 demo account).
- [ ] Move phase 13–35 specs (~23 files), leaving the deployment-track specs live.
- [ ] Move the 8 one-time runbooks (phases 38, 39, 40, 46, 47, 49, 50). **Keep
      live**: `phase-51-db-restore-steps.txt` (genuinely operational — the DB
      restore procedure for the daily R2 backups), `phase-51-email-provider-steps.txt`,
      `workflow-prompting-guide.txt`. Consider dropping the phase prefix from the
      restore runbook so it reads as a standing procedure.
- [ ] Re-point `README.md:107`'s "deployment runbooks" link at the live subset
      rather than the whole directory.

### B6. Clutter removal

- [ ] Delete `docker-compose.prod.yml` and `nginx/nginx.conf` — superseded since
      phase 40 (production is Render + Cloudflare + Neon, no containers).
      `docs/specs/deployment-overview.md:81` explicitly deferred this deletion to
      "later cleanup"; that cleanup never happened. Grep for references first.
- [ ] Delete `PHASE-39-USER-ACTIONS.txt` and `PHASE-40-USER-ACTIONS.txt`
      (gitignored, one-time checklists, long done).
- [ ] Consolidate the three overlapping workflow guides — `PHASE-WORKFLOW.txt`
      (gitignored), `docs/PROMPT-REFERENCE.md`, and
      `docs/runbooks/workflow-prompting-guide.txt` — down to the newest.
- [ ] Prune merged branches: 47 of 54 remote `lms/*` branches are merged into
      `lms/main`; 13 local branches. Leave the 6 unmerged remote branches alone.
- [ ] Review `TROUBLESHOOTING.md` (gitignored, 38 KB, untouched since Jan 29 —
      predates the entire phase 36–54 deployment track). Refresh or archive.

---

## Track C — Dead code & drift removal

### C1. Seeding drift — local/CI gate ≠ production gate

**Verified against prod Neon**: all 40 lessons have `requires_quiz = true`
(migration `0020` seeded it True wherever questions existed). But
`backend/courses/management/commands/populate_java_course.py` never sets
`requires_quiz` at any of its 20 `Lesson.objects.create` sites, and the model
default is `False` (`backend/courses/models.py:119-123`). Grep for
`requires_quiz` across `backend/courses/management/commands/` returns **zero
hits**. A freshly seeded local or CI database therefore exercises a *different*
completion gate than production — the exact thing phase 54 was built to make
explicit.

- [ ] Set `requires_quiz=True` on seeded lessons that get questions, in
      `populate_java_course.py` (20 sites) and `seed_data.py`.
- [ ] Add a test asserting the seeded state matches the production gating rule
      (`requires_quiz` true iff the lesson has questions), so this can't drift
      again.

### C2. Retire the legacy batch quiz flow (unblocks C4)

`submit_lesson_quiz` (`backend/courses/views.py:2273`) and
`answer_lesson_question` (`backend/courses/views.py:2165`) are the pre-phase-32
batch flow, routed at `backend/courses/urls.py:65, :67`. Their frontend wrappers
`courseService.answerLessonQuestion` (`frontend/src/services/courses.ts:464`) and
`submitLessonQuiz` (`:477`) have **zero component callers** — verified; the app
uses the mastery session exclusively
(`frontend/src/components/lesson/LessonQuizSection.tsx:191-195`).

`submit_lesson_quiz` is also the **only** remaining enforcer of
`max_quiz_attempts` (`backend/courses/views.py:2295, :2301-2305`).

- [ ] Delete both views, both URL routes, and both frontend service methods.
- [ ] Remove or retarget the tests that cover them.

### C3. Delete the no-op `required_quiz_id` branch

`backend/courses/views.py:3145-3157` builds `required_unlocked_quiz_ids` from
`node['obj'].required_quiz_id`. Prod has **0 of 40** lessons with
`required_quiz_id` set (verified), so the set is always empty and the loop is
provably a no-op.

- [ ] Delete the block, plus the stale rule described in the `course_map()`
      docstring at `backend/courses/views.py:3091`.
- [ ] Delete the test that exercises it by setting the FK
      (`backend/courses/tests.py:2343-2346`).

### C4. Drop the dormant columns

**Interactive sessions only — these are `RemoveField` migrations. Do not run
unattended, and do not apply to Neon without explicit approval.**

- [ ] Drop `Lesson.required_quiz` (`backend/courses/models.py:110-118`). Prod:
      **0 rows set** — verified. Also delete the now-dead remap in
      `backend/courses/management/commands/clone_course_for_demo.py:118-128`
      (`quiz_map.get(...)` always resolves `None` post-0020) and the assertions
      in `backend/courses/test_seed_demo_account.py:292-348`.
- [ ] Drop `Lesson.max_quiz_attempts` (`backend/courses/models.py:124-127`)
      **after C2** — prod has it non-zero on all 40 lessons, but nothing reads it
      once the legacy endpoint is gone. Also remove it from
      `backend/courses/serializers.py:119, :141, :156`,
      `frontend/src/types/index.ts:92` (declared, never read), and the 20
      `max_quiz_attempts=3` writes in `populate_java_course.py`.
- [ ] Keep the phase-54 migration test
      (`backend/courses/tests.py:1713-1739`) working, or retire it deliberately
      alongside the column.

### C5. Lesson-level content columns — close the write path only

Migration `0019` blanked `content`/`video_type`/`video_id` on every lesson (prod:
**0 of 40** non-empty — verified), but they are still **writable**, and there is a
live write: `frontend/src/pages/instructor/ManageCoursePage.tsx:235` calls
`createLesson(unitId, { title, content: '' })`. Column drop is deliberately NOT
in this phase.

- [ ] Remove the three fields from the write path:
      `backend/courses/serializers.py:117-118` (`LessonSerializer`), `:141`
      (`LessonCreateSerializer`). Keep them readable where the frontend still
      reads them, then drop `content: ''` from `ManageCoursePage.tsx:235` and the
      params in `frontend/src/services/courses.ts:234`.
- [ ] Add `DORMANT (Phase 53)` help_text to `backend/courses/models.py:95-109`,
      matching the `required_quiz` precedent. These were never annotated, which is
      a trap for the next reader.

### C6. Remove the Channels/Redis Phase-5 stub [P]

Dead since before the spec directory begins (specs start at phase 13). Nothing
reads any of it — `backend/config/settings.py` never references `REDIS_URL`, there
is no `CACHES` setting, no Celery, no channel layer, and `VITE_WS_URL` has zero
reads in `frontend/src`. Yet `docker-compose.yml` starts a `redis:7.2-alpine`
container with a named volume on every local run.

- [ ] `backend/requirements.txt:37-40` (commented Channels block),
      `backend/config/asgi.py:4` (stale comment),
      `frontend/src/vite-env.d.ts:5` (`VITE_WS_URL`),
      `.env.example:115-116, :120`,
      `docker-compose.yml:18-24, :43, :78, :83` (service, env, and the
      `redis_data` volume).
- [ ] Also drop the same block from `docker-compose.prod.yml` — or skip if B6
      deletes that file first.

### C7. `getNextLesson()` fakes per-lesson completion — **cut this first if the phase runs long**

`frontend/src/pages/courses/CourseDetailPage.tsx:59-90` estimates which lesson is
next by dividing overall course progress across all lessons (`"For now, we'll
compute this from the course structure"` at `:62`, `"For now, use overall progress
to estimate"` at `:69`). It points at the wrong lesson for any student who
completes out of order. A real correctness bug, but it needs a per-lesson
progress field on the course-detail payload, so it is the largest item in this
track.

- [ ] Add per-lesson completion to the course-detail response and use it directly.
- [ ] Test: a student who completes lessons 1 and 3 gets lesson 2 as "next".

---

## Track D — Test infrastructure

### D1. Stand up a frontend test runner

There are **zero** frontend tests — no vitest, no jest, no `@testing-library/*`,
no `test` script, no `test:` block in `frontend/vite.config.ts`, no `*.test.*`
files anywhere in `frontend/src`. CI runs `tsc --noEmit`, lint, and build only.
This was noticed and skipped back at phase 29
(`docs/handoffs/2026-07-19-phase-29-authoring-efficiency.md:25-26`: *"no JS test
runner installed — covered via a throwaway Node harness"*).

- [ ] Add `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, and
      `jsdom` to `frontend/package.json` devDependencies; add a `test` script and
      a `test:` block in `frontend/vite.config.ts`.
- [ ] First tests against the pure, non-trivial, currently-untested logic:
      `frontend/src/lib/splitSections.ts` (the paste-to-split parser from phase 29)
      and `frontend/src/lib/video.ts` (YouTube ID extraction — the source of the
      phase 52 bug).
- [ ] Add a frontend test step to `.github/workflows/ci.yml`.

### D2. Turn on the backend coverage tooling already paid for

`pytest-cov==6.0.0` is installed (`backend/requirements.txt:35`) but
`backend/pytest.ini` has `addopts = -v --tb=short` — no `--cov`, no threshold —
and CI's "Run tests" step is a bare `pytest`. Coverage has never been measured.

- [ ] Add `--cov=. --cov-report=term-missing` to `backend/pytest.ini`.
- [ ] Record the baseline number in this spec. **Do not set a failing threshold
      in this phase** — measure first, gate in a later one.

### D3. Tests for `backend/core/` (currently zero) [P]

`core` has no test file at all, yet holds the demo-account email suppression
(`backend/core/email.py:33-45`) and the custom throttle scopes that phases 43, 47
and 51 all leaned on — security-adjacent code with no coverage.

- [ ] `backend/core/tests/` covering: `send_templated_email` refusing
      demo-account-triggered mail; the A5 throttle ident trust boundary.
- [ ] Note for a follow-up (not this phase): `send_emails_async`
      (`backend/core/email.py:130-145`) spawns an unbounded raw daemon thread per
      request that dies on worker shutdown — silent mail loss on bulk invites.

### D4. Thicken `notifications` [P]

10 tests for a 381-line app — proportionally the thinnest. `signals.py` (41
lines) drives notification creation and is exactly the kind of thing that breaks
silently.

- [ ] Cover the signal-driven creation paths in
      `backend/notifications/tests.py`.

---

## Verification

Run `/verify-stack` and show the output. Beyond that, these specific checks:

**Automated**
- [ ] `docker compose exec -T backend pytest` — all pass (baseline 503 at phase
      54; expect a net change from C2/C3/C4 deletions plus new tests). Named new
      cases: cross-course lesson-move rejected (A2); same-course move still
      allowed (A2); `.svg` and content-sniffed `.html` avatars rejected, valid PNG
      accepted (A3); demo-account unenroll refused and normal unenroll
      soft-deletes (A4); throttle ident honors/ignores the CF header per setting
      (A5); seeded `requires_quiz` matches the prod rule (C1).
- [ ] `docker compose exec -T frontend npx tsc --noEmit` → 0 errors.
- [ ] `docker compose exec -T frontend npm run lint` → 0 errors.
- [ ] `docker compose exec -T frontend npm test` → passes (new in D1).
- [ ] `docker compose exec -T backend pip-audit` → no HIGH findings in app
      dependencies; record the baseline for anything intentionally left.
- [ ] `cd frontend && npm audit --audit-level=high` → clean, or the A7 router
      exception explicitly documented.
- [ ] CI green on the PR, including the new pip-audit / npm-audit / frontend-test
      steps.

**Repo state (the hygiene track's actual proof)**
- [ ] `git check-ignore -v docs/archive/PLAN.md` → **no output** (was
      `.gitignore:3`).
- [ ] `git ls-files docs/archive/ | wc -l` → non-zero (was 0).
- [ ] `git ls-files frontend/tsconfig.tsbuildinfo` → **empty**.
- [ ] `git ls-files backups/ | wc -l` → **0** (was 8).
- [ ] `git status --short` → clean; no untracked leftovers at repo root.
- [ ] `grep -rn "stemquest-api.onrender.com" README.md docs/deployment-tools.txt`
      → no hits.
- [ ] `grep -rn "DRF token auth" README.md` → no hits.
- [ ] `git log --oneline main..lms/main` → empty (local main fast-forwarded).

**Manual click-through (local, then prod after merge)**
- [ ] Instructor: create a lesson from `ManageCoursePage` → still works after the
      C5 write-path change (no `content: ''` param).
- [ ] Instructor: upload a valid PNG avatar → succeeds; rename an HTML file to
      `.png` and upload → rejected with a clear message.
- [ ] Student: open a lesson with `requires_quiz` on → completion still gated;
      a lesson with it off → completes freely, questions still reachable as
      optional practice (the phase-54 `hasQuiz` vs `quizGates` split must survive
      this phase intact).
- [ ] Fresh `seed_data` / `populate_java_course` on a clean local DB → lessons
      with questions come out `requires_quiz=True`, matching prod (C1).
- [ ] After merge: `https://stemquest-api-va.onrender.com/api/health/?deep=1` →
      `{"status": "ok", "database": "ok"}`, and `https://stemquests.com` loads.

---

## Deploy notes

- New migrations from C4 are **`RemoveField` — irreversible in practice**. Apply
  locally, verify, and only then apply to Neon as an explicit step at merge time.
  Snapshot first; the daily R2 backup (`.github/workflows/db-backup.yml`, last
  success 2026-07-24 10:28 UTC) is the recovery net.
- The `django-allauth` upgrade (A1) touches live auth settings. Verify login,
  logout, password reset, and the demo lockdown against the local stack before
  merging.
- Everything in Track B is repo-only and cannot affect production.

## Audit provenance

Findings verified directly during the start-phase session, not taken on trust:

- Migrations `0017`–`0020` **are** applied to Neon (`django_migrations`, `0020`
  at 2026-07-23 22:20 UTC) — the deploy debt carried in the phase 52/53/54
  handoffs is **closed**. An audit agent reported otherwise; it was wrong.
- The CF-Connecting-IP throttle bypass is **not reachable** through the public
  host — Cloudflare returns `error code: 1000` / 403 for client-supplied CF
  headers. Downgraded from P1 to defense-in-depth (A5).
- Prod lesson data (40 rows): `required_quiz_id` set on 0, `requires_quiz` true
  on 40, lesson-level `content`/`video_id` empty on 40, `max_quiz_attempts` > 0
  on 40.
- `.gitignore` exclusions confirmed via `git check-ignore -v` and `git ls-files`.
- Dependency findings from `pip-audit` (in-container) and `npm audit`.
- Scale context: 5 users, 3 active in 30 days, 1 superuser, 2 courses, 40 lessons.

## Follow-ups recorded, deliberately not in this phase

- Django 4.2 → 5.2 LTS (Phase 56).
- `CourseViewSet.get_queryset` returns every course to any instructor
  (`backend/courses/views.py:63-76`); `IsCourseInstructor.has_object_permission`
  returns True unconditionally for safe methods
  (`backend/courses/permissions.py:97-99`). Only matters if the platform goes
  multi-instructor.
- Drop the lesson-level `content`/`video_type`/`video_id` columns (C5 closes the
  write path; the schema drop is later).
- Split `CoursePlayerPage.tsx` (825 lines, 12 `useState`, 7 `useEffect`) and
  `backend/courses/views.py` (3,206 lines).
- `has_video` + `*_count` N+1 (~83 queries per 20 lessons, unpaginated) —
  `backend/courses/serializers.py:131-133, :160-169`.
- Pagination for `gradebook` / `analytics_*` (custom `@api_view` matrices).
- `send_emails_async` unbounded daemon thread (`backend/core/email.py:130-145`).
- Case-sensitive email match in invite acceptance
  (`backend/courses/views.py:1748`) can create duplicate accounts for one human.
- Enrollment-code entropy: `secrets.token_urlsafe(6)[:8].upper()`
  (`backend/courses/models.py:11`) collapses case; no wrong-code throttle.
- `MEDIA_URL = 'media/'` has no leading slash (`backend/config/settings.py:161`).
- Partial unique index on in-progress `LessonQuizAttempt` (raised phase 32).
- `manualChunks` vendor splitting (`frontend/vite.config.ts`); route-level
  `React.lazy` already landed in phase 50.
- Four `react-hooks/exhaustive-deps` suppressions:
  `QuizSessionFlow.tsx:90`, `LessonQuizSection.tsx:28`, `QuizEditorPage.tsx:110`,
  `QuizDetailPage.tsx:51`.
- Operator backlog carried across phases: decommission the old Oregon Render
  service (`docs/specs/phase-49-region-move-virginia.md:74` — **was due
  2026-07-25**), `ADMIN_URL` flip evidence, revoke the old Gmail app password,
  UptimeRobot Gmail filter, legal DRAFT banner sign-off on `/terms` and
  `/privacy`, cold-start timing measurement.
