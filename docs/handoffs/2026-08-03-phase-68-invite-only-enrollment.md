# Handoff: Phase 68 invite-only enrollment + launch ops

## Current state
**Phase 68 is COMPLETE; PR #97 is OPEN and not merged.**
https://github.com/Cesar6060/LMS/pull/97 — branch
`feat/phase-68-invite-only-enrollment` on `lms` (the go-forward remote).
Spec: `docs/specs/phase-68-invite-only-enrollment-and-launch-ops.md` — every
Backend/Frontend/Verification item checked off; the Prerequisites, Production
and Ops sections are still open owner actions (see Next steps).

A pending `CourseInvite` now authorizes joining a course on **both** code-based
paths. The enrollment code stays as a second factor and on its own enrols
nobody.
- `require_pending_invite()` — `backend/courses/permissions.py`. Exact match on
  the lowercased address, never `iexact`.
- `consume_invite_for()` — `backend/courses/views.py`, near `_activate_enrollment`.
  Returns a bool; False rolls the enrollment back.
- Wired into `CourseViewSet.enroll` (`views.py:100`) and
  `EnrollmentCreateSerializer` (`serializers.py:595`).
- Reactivation of soft-deleted enrollments removed from both paths.
- Non-string code → 400; the three `{'error':}` bodies → `{'detail':}`;
  concurrent double-submit → 400 instead of an uncaught 500.
- `DELETE .../invites/<id>/delete/` and `.../invites/closed/` (`urls.py:47-49`).
  Pending invites must be revoked first.
- `/api/health/?deep=1` runs an ORM content read behind `SELECT 1`; the shallow
  path stays DB-free (it is the Render deploy gate).
- Frontend: `components/course/ClassCodeCard.tsx` rendered from BOTH
  `StudentRosterPage` and `ManageCoursePage` (where it takes the prominent slot
  and the enrollment code is demoted); per-row delete on closed invites +
  "Clear all closed"; `lib/clipboard.ts` shared; `EnrollmentModal` surfaces the
  new 403 detail.
- **No migration** — confirmed by `makemigrations --check` and the
  db-migration-checker agent.
- Verified: pytest **1106**, tsc 0, lint 0 (+1 known warning), vitest **154**.
  Full local click-through done (all five spec steps). Two adversarial passes
  and a code review; every BROKEN finding and every test gap fixed on the
  branch.

## In progress / not done
- **Nothing in the phase is half-built.** The PR is the finish line; merging is
  the user's call (it auto-deploys the backend).
- A stray `feat/phase-68-invite-only-enrollment` branch exists on the **retired**
  `origin` repo (`dev-learning-platform`) — pushed there by reflex before the
  remote was corrected. Deleting it was blocked by a permission classifier, same
  as the phase-67 one. Harmless; delete both when convenient.
- **Deferred, in the PR body, not dropped:** `require_pending_invite` does not
  require a VERIFIED email. Inert while `ALLOW_REGISTRATION` is off; if
  registration is ever enabled, signing up as an invited-but-unregistered
  address plus knowing the code would enroll. Inherited from `accept_invite`
  (phase 67), same exposure — fix both together or neither.
- Carried, none launch-blocking: `THROTTLE_SLIDE_IMPORT` ceiling; phase-61
  slide-import smoke test; JAVA101 answer-rotation reseed; phase-56/64
  click-throughs; Sentry LoginPage; Dependabot #68/#86/#87/#88.

## Next steps
1. **Merge PR #97**, then verify with a REAL content read — an authenticated
   `DEMO101/units/` fetch — not just `/api/health/?deep=1`. Then
   `curl 'https://api.stemquests.com/api/health/?deep=1'` (must still contain the
   verbatim `"database": "ok"`) and confirm UptimeRobot monitor `803564235` is
   still UP. A broken keyword match shows up as a false DOWN, not a missing alert.
2. **Fresh Neon backup branch, then production `protected: true`** (LMS project
   `shy-cloud-68280619`). Highest-value item left — the newest backup predates
   several schema changes, and after real student data lands a mistake is
   unrecoverable.
3. **Branch protection on `main`**, requiring both CI jobs. Merging deploys, so
   today a red build can reach production.
4. **Owner actions still open from phase 67**: set `THROTTLE_JOIN_CODE=10/hour`
   and `THROTTLE_INVITE_LINK=60/hour` in Render; apply
   `docs/runbooks/phase-67-email-deliverability-dns.txt` (`_dmarc` + root SPF,
   both still absent); send one invite to the school address that vanished and
   check Gmail "Show original" for SPF/DKIM/DMARC PASS.
5. **Phase 69 — Robotics 2 / ROB201 authoring.** Delete the local-Docker ROB201
   stub first. `populate_robotics_course.py` is the pattern; `_content_upsert.py`
   has the `content_key` rules; the `ROB201` guard is at `courses/tests.py:4449`.

## Decisions made
- **The invite requirement is unconditional**, not gated on `ALLOW_REGISTRATION`
  — that env var governs three allauth URL patterns and nothing else, so keying
  a permission boundary off it would silently regress.
- **The refusal is specific (403 naming the invitation), not generic.** These
  endpoints are `IsAuthenticated` and can only ever answer about the caller's own
  address. `/join/`'s generic 400 exists because it is `AllowAny` and would
  otherwise answer about someone else. Pinned by
  `test_the_refusal_body_is_identical_whoever_else_is_invited`.
- **`consume_invite_for` returns a bool** (spec said "returns nothing"). The
  adversarial pass proved the read-then-write gap let an instructor's revoke lose
  a race it should win. The write is now the authoritative check.
- **A soft-deleted enrollment gets the invite-required 403**, not a fall-through:
  `Enrollment` is `unique_together ('user','course')`, so the spec's literal
  "delete the reactivation branch" would have made a removed student's retry a
  500. The body is identical to "no invite", so it never says "you were removed".
- **Invalid-code response shapes are allowed to differ** between the two paths
  (`{'detail':}` vs DRF's field error). That is a validation failure, not an
  authorization one; the authorization 403 IS identical on both.
- **Delete is hard, and only for closed invites.** No `dismissed_at` column — a
  third lifecycle concept next to `status` and `delivery` is not worth it.

## Gotchas discovered
- **`Enrollment` is `unique_together ('user','course')`.** Any new create path
  over a possibly-existing row is a 500 waiting to happen — the concurrent
  double-submit 500 this phase fixed was pre-existing and reachable by an
  impatient double-click.
- **Raising `PermissionDenied` inside `transaction.atomic()`** is how you roll a
  write back and still return a clean 403; it works identically from a viewset
  action and from a serializer's `create()`.
- **Push to `lms`, not `origin`.** `origin` is the retired repo and accepts the
  push silently.
- **`pytest` is not on the host PATH** — run it as
  `docker compose exec -T backend pytest`.
- Local logins for click-throughs: `instructor@demo.com` and
  `student1@demo.com`, both `LocalDev123!` (set this session, local dev DB only).
  Chrome automation: `form_input` can leave React state stale on the login form —
  click the field, `cmd+a`, then type.

## Files to read first
1. `docs/specs/phase-68-invite-only-enrollment-and-launch-ops.md` — the contract
   plus the Outcomes section recording both deviations and the adversarial pass.
2. `backend/courses/permissions.py` — `require_pending_invite` is the whole
   security contract.
3. `backend/courses/views.py` — `CourseViewSet.enroll`, `consume_invite_for`,
   `delete_course_invite`, `delete_closed_course_invites`.
4. `backend/courses/serializers.py` — `EnrollmentCreateSerializer`, the path that
   resolves the course by code alone.
5. `frontend/src/components/course/ClassCodeCard.tsx` — rendered from two pages;
   change it there, not in either page.
