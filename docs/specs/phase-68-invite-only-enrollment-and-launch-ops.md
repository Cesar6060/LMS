# Phase 68 — Invite-only enrollment + launch ops

Written 2026-08-03. Predecessor: `docs/specs/phase-67-email-deliverability-and-invite-fallback.md`.
Students arrive ~2026-08-09.

## Goal

Make a pending `CourseInvite` the thing that authorizes joining a course, on
every path, so that knowing a course's enrollment code stops being enough. Today
two endpoints will enroll any authenticated account that presents an 8-character
code, one of them resolving the course by that code alone with no course in the
URL — so a leaked code from any course is a working key to it, and an instructor's
roster removal is undone by the same code they read aloud to the class. This
phase requires an invite on both paths, fixes the three defects sitting in the
same code (a 500 on a non-string code, self-reactivation of removed students,
`{'error':...}` bodies that violate `.claude/rules/backend.md`), gives the
instructor a way to clear dead invitations out of the roster, promotes the class
code into the prominent slot the enrollment code occupies today, and closes the
two launch-ops gaps that must be shut before real student data lands.

## Diagnosis (established 2026-08-03 — do not re-derive)

There are **two** code-only enrollment paths, not the one the phase-67 handoff
named:

1. `CourseViewSet.enroll` — `backend/courses/views.py:100-144`. Action-level
   `permission_classes=[IsAuthenticated]` overrides the viewset's instructor
   classes. Course comes from the URL; `get_object_or_404(Course, code=code,
   is_active=True)` bypasses `get_queryset()`, so any active course is reachable.
   The only other gate is `require_not_demo`.
2. `EnrollmentViewSet.create` → `EnrollmentCreateSerializer` —
   `backend/courses/views.py:474-484` and `backend/courses/serializers.py:595-630`.
   `POST /api/courses/enrollments/`. Resolves the course with
   `Course.objects.get(enrollment_code=value.upper(), is_active=True)` —
   **globally, by code alone**. This is the path the UI actually calls
   (`EnrollmentModal.tsx:34` → `courses.ts:204`). `courseService.enroll()`
   (`courses.ts:197`) targets path 1 and has no callers, but the endpoint is live.

Consequences confirmed in the code:

- **A removed student re-enrolls themselves.** Both paths reactivate a
  soft-deleted `Enrollment` (`views.py:126-130`, `serializers.py:621-627`).
  `remove_student` soft-deletes precisely to preserve grades; the student
  presents the code again and is back.
- **`enroll` 500s on a non-string code.** `request.data.get('enrollment_code',
  '').upper()` (`views.py:110`) raises `AttributeError` on `{"enrollment_code":
  123}`. Phase 67 hardened `join_with_code` against exactly this
  (`normalize_join_code`, `models.py:37-45`); `enroll` never got it. No test
  covers it.
- **`ALLOW_REGISTRATION` gates nothing here.** It is read in exactly one place,
  `backend/accounts/urls.py:11`, and only mounts/unmounts the allauth signup
  URLs. It does not touch `enroll`, `EnrollmentViewSet.create`, `accept_invite`,
  or `join_with_code`. Any design that keys a permission boundary off it is
  keying off an env var that currently governs three URL patterns and nothing
  else — which is why this phase does not do that (see Decisions).
- **The frontend has no config endpoint and no knowledge of
  `ALLOW_REGISTRATION`.** No occurrence anywhere under `frontend/`.
  `backend/config/urls.py` mounts no settings endpoint. So any "hide it when X"
  UI needs a new serializer field; it is not free.

Invite clutter (the roster complaint):

- `StudentRosterPage.tsx:443` — `invites.filter((i) => i.status !== 'accepted')`,
  so **pending, revoked and expired** rows all render.
- The partial constraint is `UniqueConstraint(['course','email'], condition=
  revoked_at IS NULL)` (`models.py:323-329`). Revoked rows are therefore
  unbounded per (course, email): every invite → revoke → re-invite cycle leaves
  another dead row in the table permanently. There is no delete anywhere —
  `revoke_course_invite` (`views.py:1901`) only stamps `revoked_at`.

Health endpoint:

- `backend/config/health.py:19-40`. `?deep=1` runs `SELECT 1` through a raw
  cursor. Plain Django view (not DRF) on purpose, so `IsAuthenticated` can't 403
  the monitors; `@never_cache`; no throttle.
- **Live UptimeRobot check, 2026-08-03: 6 monitors, exactly ONE hits `?deep=1`**
  — `803564235` "STEM Quest DB (deep health)", KEYWORD type, hourly, matching
  `"database": "ok"`. The others are shallow `/api/health/` (`803564203`,
  `803613995`), the frontend, `stemquests.com`, and an unrelated portfolio app.
  The phase-67 handoff's "all six monitors are health checks, so fixing the
  endpoint upgrades every monitor at once" is **wrong**; this upgrades one hourly
  monitor. Scoped in anyway because it is small and it is the only monitor that
  can ever prove Django reaches real data.
- `render.yaml:79` `healthCheckPath: /api/health/` — the **shallow** path is the
  deploy gate. It must stay DB-free.

## Decisions made (interview, 2026-08-03)

1. **A pending invite is required on both paths, unconditionally** — not
   conditional on `ALLOW_REGISTRATION`. One rule, testable without
   `override_settings`, and it cannot silently regress when an env var changes.
   The enrollment code is **not** deleted and not bypassed: it stays as a second
   factor, checked as it is today. Joining now needs the code AND a pending
   invite for the caller's own address. This is the same shape phase 67 chose for
   the class code ("the code is a delivery channel, not an authorization").
2. **A successful code-based enrollment consumes the invite** (`accepted_at`
   stamped), exactly as `accept_invite` does. Without this the invite stays
   pending and remains a live second entry. It also makes decision 3 coherent:
   once consumed, a removal is final until the instructor re-invites.
3. **Removed students no longer self-reactivate.** The reactivation branch on
   both paths goes away. A soft-deleted enrollment now comes back only via
   `accept_invite`'s `_activate_enrollment` — i.e. only after the instructor
   issues a fresh invite. The instructor's removal sticks.
4. **The refusal is specific, not generic.** Code wrong → the existing 400.
   Code right but no pending invite → **403** `{'detail': ...}` naming the
   invitation requirement. This deliberately differs from phase 67's `/join/`,
   which returns one identical 400 for all six failure modes. The reasoning:
   `/join/` is `AllowAny` and its error would otherwise answer "is
   alice@district.edu invited?" about **someone else**. These endpoints are
   `IsAuthenticated` and can only ever answer that question about the **caller's
   own address**, which the caller is entitled to know. A generic error here
   would strand a legitimate student with no idea what to do next. The residual
   leak is a code oracle ("this code is valid for some course") — worth nothing
   once the code authorizes nothing on its own. **Flag this to the
   adversarial-tester rather than letting it re-litigate it.**
5. **Email is matched EXACTLY against the lowercased invite address** —
   `request.user.email.lower() == invite.email`, the `accept_invite:2150`
   pattern. Never `iexact`. Phase 67 proved that Postgres `UPPER()` folds Turkish
   dotless i (U+0131) onto ASCII `i`, which would hand one student another's
   enrollment. Do not "improve" this.
6. **No scoped throttle on the enroll paths** (considered and dropped). Once a
   pending invite is required, brute-forcing an enrollment code yields nothing
   without an invite for the attacker's own address, so the throttle stops being
   load-bearing. The global `ClientIPAnonRateThrottle`/`ClientIPUserRateThrottle`
   ceilings still apply. Revisit if code-only self-enroll is ever restored.
7. **Delete is a hard delete, and only for closed invites.** Pending invites keep
   the existing Revoke button and cannot be deleted — a misclick must never void
   a live invitation. Closed = accepted, revoked, or expired. No `dismissed_at`
   column: a third lifecycle concept next to `status` and `delivery` is not worth
   it, and hard-deleting a closed invite destroys no enrollment (the `Enrollment`
   row is the record that matters, and it is a separate table).
8. **Per-row delete plus one "Clear all closed" bulk action.**
9. **The class code takes the prominent slot on `ManageCoursePage`**; the
   enrollment code is demoted. The enrollment-code box is currently the largest
   code on the page (`ManageCoursePage.tsx:506-529`), so it is what an instructor
   reads to the class — and under invite-only it fails for every student without
   an account, which on day one is all of them. The class code is the one that
   works.
10. **Ops in scope: Neon backup branch + `protected: true`, and branch protection
    on `main`, and the health content read.** Deleting the local ROB201 stub was
    considered and left for phase 69, with Robotics 2 itself.

## Out of scope

- **Robotics 2 / ROB201 authoring — phase 69.** ROB101 is 4,897 lines for
  6 units / 24 lessons / 116 sections / 6 quizzes; Robotics 2 is a full phase on
  its own. Do not touch `populate_robotics_course.py`, `populate_java_course.py`,
  `_content_upsert.py`, or the `ROB201` guard at `backend/courses/tests.py:4449-4452`.
- Deleting the local-Docker ROB201 rows (phase 69, with the authoring).
- Deleting or disabling the enrollment-code mechanism. It stays, as a second
  factor, and is the right tool again if self-enrollment is ever restored.
- Changing `ALLOW_REGISTRATION`, enabling registration, or adding a settings/
  config endpoint for the SPA.
- A scoped throttle on the enroll paths (decision 6).
- Any change to `join_with_code`, `accept_invite`, `invite_link`, the join-code
  management endpoints, or `core/email.py`. Phase 67 shipped those; this phase
  reuses them.
- Resend webhook ingestion; the DNS/DMARC runbook (owner action, still open from
  phase 67 — see Prerequisites).
- Any change to `Course` content, XP, or `content_key` handling.
- Caching the health endpoint's content read (decision: one hourly monitor does
  not justify the project's first non-throttle cache consumer).

## Prerequisites (owner actions carried from phase 67 — NOT this phase's work)

These block inviting students, not this phase's code. Listed so they are not lost:

- [ ] Set `THROTTLE_JOIN_CODE=10/hour` and `THROTTLE_INVITE_LINK=60/hour` in the
      Render dashboard.
- [ ] Apply `docs/runbooks/phase-67-email-deliverability-dns.txt` (`_dmarc` and
      root SPF; both confirmed absent 2026-08-03).
- [ ] Send one invite to the school address that previously vanished and check
      Gmail "Show original" for SPF/DKIM/DMARC PASS.

## Backend tasks

### A. Invite-required enrollment

- [x] Add `require_pending_invite(user, course, message=None)` to
      `backend/courses/permissions.py`, next to `require_course_instructor` /
      `require_course_access`. Raises `PermissionDenied` (403 `{'detail': ...}`)
      unless `course.invites.pending().filter(email=user.email.lower()).exists()`.
      Use the existing `CourseInviteQuerySet.pending()`
      (`models.py:264-270`) — do not re-express the three conditions inline.
      Exact match on the lowercased address only (decision 5).
- [x] Add `consume_invite_for(user, course)` (module-level helper in
      `backend/courses/views.py`, near `_activate_enrollment` at `:1702`):
      stamps `accepted_at=timezone.now()` on the pending invite via a targeted
      `filter(pk=...).update(...)`, mirroring the phase-67 pattern so it cannot
      clobber a concurrent revoke. Returns nothing.
- [x] `CourseViewSet.enroll` (`views.py:100`): after the enrollment-code check
      passes, call `require_pending_invite`, and on the success path call
      `consume_invite_for` inside the same `transaction.atomic()` as the
      `Enrollment.objects.create(...)`. The enroll action currently has no
      `atomic()` — add one so the enrollment and the invite consumption cannot
      diverge.
- [x] `EnrollmentCreateSerializer` (`serializers.py:595`): same requirement.
      Because it resolves the course by code alone, the invite check is the only
      thing scoping it to a course the caller was actually asked to join. Raise
      `PermissionDenied`, not `ValidationError` — a missing invite is an
      authorization failure and must be a 403 `{'detail': ...}` per
      `.claude/rules/backend.md`, not a 400 field error.
- [x] `[P]` Confirm no other `Enrollment`-creating path needs the gate: the only
      others are `_activate_enrollment` (both `accept_invite` branches — already
      invite-driven by construction), `seed_data.py:740`, `seed_demo_account.py:84`,
      and `EnrollmentAdmin`. Management commands and Django admin are
      deliberately exempt. Record this in a comment on `require_pending_invite`
      so the exemption is explicit and not an oversight.

### B. Enroll-path hardening (same code, same review)

- [x] Coerce the enrollment code before `.upper()` on `views.py:110`. Follow
      `normalize_join_code` (`models.py:37-45`), which returns `''` for a
      non-string. A non-string body must be a 400, never a 500.
- [x] `[P]` Remove the reactivation branch from `CourseViewSet.enroll`
      (`views.py:126-130`) and from `EnrollmentCreateSerializer.create`
      (`serializers.py:621-627`). A soft-deleted enrollment is no longer revived
      by presenting a code; it returns the same "already enrolled"/invite
      refusal as any other blocked case. Decide the wording so it does not tell a
      removed student they were removed — reuse the invite-required 403.
- [x] `[P]` Convert every `{'error': ...}` body in `CourseViewSet.enroll` to
      `{'detail': ...}` (`views.py:113`, `:121`, `:135`), per
      `.claude/rules/backend.md`. These are the only three in the action.
- [x] `[P]` Add a module-level comment on `enroll` recording that the enrollment
      code is a second factor and the invite is the authorization — so a future
      reader does not "simplify" the invite check away.

### C. Invite cleanup

- [x] `DELETE /api/courses/courses/<code>/invites/<id>/delete/` →
      `delete_course_invite`. Mounted in `backend/courses/urls.py` after the
      existing `invites/<int:invite_id>/` (revoke) and
      `invites/<int:invite_id>/link/` routes. `IsAuthenticated` +
      `require_course_instructor` + `require_not_demo_course`, matching
      `invite_link` (`views.py:1938-1976`) rather than the older, less-guarded
      `revoke_course_invite`.
- [x] 404 when the invite id belongs to a different course — scope on the path,
      do not assume it (`get_object_or_404(CourseInvite, id=..., course=course)`).
- [x] **400 when the invite is pending**, with a `detail` telling the instructor
      to revoke it first. Only `accepted`, `revoked` and `expired` may be
      deleted (decision 7). Use the existing `invite.status` property — do not
      re-derive the lifecycle.
- [x] `DELETE /api/courses/courses/<code>/invites/closed/` →
      `delete_closed_course_invites`. Same guards. Deletes every invite on the
      course whose status is not `pending`; returns `{'deleted': <count>}`.
      Build the queryset as "not pending" using `CourseInviteQuerySet.pending()`
      negated in SQL (`.exclude(pk__in=course.invites.pending())`), not by
      evaluating the `status` property per row in Python.
- [x] `[P]` URL ordering: `invites/closed/` cannot be shadowed by
      `invites/<int:invite_id>/` because the converter is `int`-typed — confirm
      with a test rather than by inspection.

### D. Health endpoint content read

- [x] `backend/config/health.py`: on `?deep=1`, after the existing `SELECT 1`,
      run a real ORM content read that **names real columns and tolerates zero
      rows** — e.g. `Lesson.objects.values('id', 'content_key', 'unit_id').first()`
      and `Course.objects.values('id', 'code', 'join_code').first()`. A missing
      column raises `ProgrammingError` and fails the check even on an empty
      database; requiring rows to exist would break every test DB and add
      nothing. This is the specific failure the endpoint was blind to during the
      phase-65 outage.
- [x] Response on success stays a superset of today's: `{'status': 'ok',
      'database': 'ok', 'content': 'ok'}`. **The string `"database": "ok"` must
      still appear verbatim** — UptimeRobot monitor `803564235` keyword-matches
      it, and changing the shape silently breaks the only deep monitor.
- [x] Failure returns 503 `{'status': 'error', 'content': 'unavailable'}` — no
      `"database": "ok"`, so the monitor fires. Log the exception server-side
      with `logger.exception`; never put the driver's message in the body (the
      existing `health.py:34-36` reasoning: it leaks the Neon host/user/SSL
      config).
- [x] **The shallow path must remain DB-free.** `render.yaml:79` uses it as the
      deploy gate; a DB touch there makes a cold Neon branch fail a deploy.
- [x] `[P]` Update `docs/deployment-tools.txt:217-238`, which currently describes
      the deep monitor as proving only "Django can reach Neon".

## Frontend tasks

- [x] `[P]` Extract the class-code card from `StudentRosterPage.tsx:724-808` into
      `frontend/src/components/course/ClassCodeCard.tsx` — generate / rotate /
      turn off, the confirm-dialog copy at `:960-962`, and the `joinCodeAvailable`
      403-hiding behaviour from `loadJoinCode` (`:207-222`). Render it from both
      `StudentRosterPage` and `ManageCoursePage`. One component, so the two pages
      cannot drift.
- [x] `ManageCoursePage.tsx:506-529`: replace the enrollment-code box in the
      header slot with `ClassCodeCard`. Demote the enrollment code to small
      secondary text (keep it reachable — it is still a real second factor for an
      enrolled student adding another course), or drop it from this page
      entirely if the header gets crowded. Keep the existing copy-to-clipboard
      affordance on whichever code stays prominent, including the phase-67
      clipboard fallback (a non-settling `navigator.clipboard.writeText` must
      reveal the text, not hang).
- [x] `[P]` Invite row: add a delete control on **closed rows only** (`status !==
      'pending'`) in the actions cell at `StudentRosterPage.tsx:668-682`, calling
      the new endpoint via a new `inviteService.deleteInvite`.
- [x] `[P]` Add a "Clear all closed" button above the table, shown only when at
      least one closed invite is present, calling
      `inviteService.deleteClosedInvites`. Confirm before firing.
- [x] `[P]` `frontend/src/services/invites.ts`: `deleteInvite(courseCode, id)`
      and `deleteClosedInvites(courseCode)`.
- [x] `[P]` `EnrollmentModal.tsx:42-45`: handle the new 403 `{'detail': ...}`.
      The handler already reads `detail`, so verify rather than assume — and make
      sure the invite-required message is what the student actually sees instead
      of a generic failure.
- [x] `[P]` Types: any new fields on the course payload used by `ClassCodeCard`
      go in `frontend/src/types/index.ts` / `services/courses.ts` alongside the
      existing `enrollment_code?: string` (`types/index.ts:47`).

## Verification

Backend (`cd backend && pytest` — **run it alone**; the phase-66/67 handoffs both
recorded false failures from running pytest alongside review subagents on a
shared test DB):

- [x] `test_enroll_requires_a_pending_invite` — student with the correct
      enrollment code and **no** invite gets 403 `{'detail': ...}`, and no
      `Enrollment` row is created. Both paths: `/courses/<code>/enroll/` and
      `POST /courses/enrollments/`.
- [x] `test_enroll_succeeds_with_code_and_pending_invite` — both paths, 201.
- [x] `test_enroll_consumes_the_invite` — after a successful enroll the invite's
      `status` is `accepted` and it no longer appears in `pending()`.
- [x] `test_removed_student_cannot_self_reactivate` — enroll, instructor
      `remove_student` (soft delete), student presents the code again → refused,
      and `Enrollment.is_active` stays `False`. This is the regression that
      motivated decision 3; assert the row state, not just the status code.
- [x] `test_re_invite_restores_a_removed_student` — the other half: after a fresh
      invite, `accept_invite` reactivates them. Proves removal is reversible by
      the instructor and only by the instructor.
- [x] `test_revoked_and_expired_invites_do_not_authorize_enroll` — one test per
      dead status, both paths.
- [x] `test_an_invite_on_another_course_does_not_authorize_this_one` — the
      serializer path is the one at risk here, since it resolves the course by
      code alone.
- [x] `test_enrollment_code_email_match_is_exact_not_iexact` — an invite for an
      address differing only by Turkish dotless i (U+0131) must NOT authorize.
      Mirror `test_dotless_i_cannot_resolve_someone_elses_invite`
      (`tests.py:6353`).
- [x] `test_non_string_enrollment_code_is_400_not_500` — `{"enrollment_code":
      123}` and `{"enrollment_code": []}`, both paths.
- [x] `test_enroll_denials_use_detail_not_error` — asserts the three converted
      bodies.
- [x] **Update the existing tests that this phase intentionally breaks**:
      `test_enroll_with_valid_code` (`tests.py:171`) and
      `test_enroll_via_enrollment_endpoint` (`tests.py:207`) both enroll with a
      bare code and will now 403. Give them a pending invite; do not weaken the
      new rule to keep them green. Check `test_enroll_twice_fails` (`:186`) and
      `backend/core/tests/test_demo_lockdown.py:496`
      (`test_student_can_enroll_and_post`) for the same breakage.
- [x] Delete-invite permission boundary, per `.claude/rules/backend.md`:
      instructor 200/204; a different instructor 403; enrolled student 403;
      anonymous 401/403; invite from another course 404; demo course refused.
- [x] `test_pending_invite_cannot_be_deleted` — 400 with a `detail`, and the row
      still exists.
- [x] `test_delete_closed_removes_only_closed` — a course with one pending, one
      revoked, one expired and one accepted invite: bulk delete returns
      `{'deleted': 3}` and leaves exactly the pending row.
- [x] `test_invites_closed_route_is_not_shadowed_by_the_id_route` — `reverse()`
      resolves `invites/closed/` to the bulk view.
- [x] `test_deleting_an_accepted_invite_leaves_the_enrollment` — the student
      stays on the roster.
- [x] Health: `test_health_deep_reports_content_ok` (body contains the verbatim
      substring `"database": "ok"` **and** `'content': 'ok'`);
      `test_health_deep_503_when_content_read_fails` (patch the ORM call to raise
      `ProgrammingError`; assert 503, no `"database": "ok"` in the body, and no
      `neon.tech`/`secret` leak); `test_health_deep_ok_on_empty_database` (zero
      courses and zero lessons still returns 200 — the tolerate-zero-rows
      contract); `test_health_shallow_still_touches_no_db`. Update the existing
      `test_health_deep_ok` (`backend/config/tests/test_production_settings.py:31`),
      which asserts the exact old body.
- [x] Run the `db-migration-checker` agent. **This phase should add no
      migration** — if one appears, that is a signal something drifted from the
      spec, not a step to wave through.
- [x] Run the `adversarial-tester` agent over the enroll paths and the two delete
      endpoints. Brief it that decision 4 (specific 403 rather than a generic
      error) is deliberate and argued, so it does not re-litigate it — but it
      should still confirm the refusal leaks nothing about **other** students'
      invitations.

Frontend:

- [x] `cd frontend && npx tsc --noEmit` → 0 errors.
- [x] `cd frontend && npm run lint` → clean (the 1 known warning may remain).
- [x] `npx vitest run` → all pass. Add: `ClassCodeCard` renders identically from
      both pages and hides on a 403; the delete control is absent on a pending
      row and present on a closed one; "Clear all closed" is hidden when there
      are none.

Whole stack:

- [x] `/verify-stack` → PASS, output pasted as evidence.

Manual click-through (local Docker; instructor `instructor@demo.com` /
`LocalDev123!`, local dev DB only):

- [x] Student with a valid enrollment code and no invite → refused, and the
      message tells them to ask for an invitation.
- [x] Invite that same address → student enrolls → the invite disappears from
      "Open invitations" (consumed) and they appear on the roster.
- [x] Instructor removes them → student tries the code again → still refused.
- [x] Roster: delete one closed invite, then "Clear all closed" → the pending row
      survives both.
- [x] `ManageCoursePage` shows the class code in the prominent slot, generate /
      rotate / turn off all work from that page, and the roster page agrees.

Production (after merge — merging `main` deploys the backend):

- [ ] Verify with a **real content read**, not just `/api/health/?deep=1` —
      an authenticated `DEMO101/units/` fetch, per the CLAUDE.md gotcha.
- [ ] `curl 'https://api.stemquests.com/api/health/?deep=1'` returns the content
      keys and still contains `"database": "ok"`. Then confirm UptimeRobot
      monitor `803564235` is still UP — a broken keyword match shows up as a
      false DOWN, not a missing alert.

Ops (owner actions — do these BEFORE inviting students):

- [ ] **Fresh Neon backup branch, then set production `protected: true`.** LMS
      project `shy-cloud-68280619`. The newest backup is 11 days old and predates
      four schema changes. Highest-value item in the phase; do it before any real
      student data lands, because after that a mistake is unrecoverable.
- [ ] **Branch protection on `main`**, requiring both CI jobs. Merging deploys,
      so today a red build can reach production. GitHub dashboard action, no code.

## Notes for the implementer

- Backend changes need `docker compose restart backend` to take effect.
- Expect **no migration** in this phase. Every change is view/serializer/
  permission logic plus frontend.
- `require_pending_invite` is the whole security contract. Put it in
  `courses/permissions.py` with the other helpers — `.claude/rules/backend.md`
  requires authorization checks to live there, and an inline check on two
  different paths is how the paths drifted apart in the first place.
- The two enroll paths must end up with **identical** authorization. Anything
  true of one and not the other is the bug this phase exists to fix. Consider
  writing the tests parametrized over both endpoints so they cannot diverge
  silently.
- `courseService.enroll()` (`frontend/src/services/courses.ts:197`) has no
  callers. Leaving it is fine; deleting it is also fine. Do not spend time on it.
- Do not touch `join_with_code`, `accept_invite`, or `invite_link`. Phase 67
  shipped them with two adversarial passes; this phase reuses them unchanged.

## Outcomes (implementation, 2026-08-03)

Two deliberate deviations from the text above, both forced by the code:

1. **`consume_invite_for` returns a bool, not nothing.** The spec had it
   returning nothing. The first adversarial pass proved that leaves a real
   TOCTOU: `require_pending_invite` is a read, and an instructor's revoke
   landing between it and the `Enrollment` insert lost a race it should win,
   producing an active enrollment hanging off an invite the roster shows as
   "revoked". The bool makes the WRITE the authoritative check — both callers
   treat False as a refusal and raise inside the `atomic()`, rolling the
   enrollment back. Covered by `test_a_revoke_landing_mid_enroll_wins`.
2. **A soft-deleted enrollment gets the invite-required 403 rather than
   falling through.** `Enrollment` is `unique_together ('user','course')`, so
   simply deleting the reactivation branch (as written) would have made a
   removed student's retry a 500, not a refusal. The refusal reuses the
   invite-required body verbatim, so it is indistinguishable from "no invite"
   and never tells a student they were removed.

One defect found by the same pass and fixed here, pre-existing rather than
introduced: a concurrent double-submit (an impatient double-click was enough)
passed the already-enrolled read twice and the loser hit the unique constraint
raw, returning an uncaught 500 on both paths. Now a 400. Covered by
`test_a_concurrent_double_submit_is_400_not_500`.

Everything else in that pass HELD: cross-course invites, Turkish dotless-i
folding, plus-addressing, non-string codes, the delete endpoints' permission
boundary and IDOR scoping, the demo guard, URL shadowing, and the refusal's
information leakage (byte-identical whoever else is invited — pinned by
`test_the_refusal_body_is_identical_whoever_else_is_invited`).

Left as-is, judged not a defect: the two paths return different SHAPES for an
invalid code — `{'detail': ...}` from the action, DRF's field error
`{'enrollment_code': [...]}` from the serializer. Decision 4 governs the
invite-required 403, which IS identical on both paths; the invalid-code case
is a validation failure, not an authorization one, and `EnrollmentModal`
reads both.
