# Phase 67 — Email deliverability + invite fallback

Students arrive ~2026-08-09. Invites are the only way in, and the one invite
sent to a school address never landed.

## Goal

Make the invite email survive a school district's mail filter, and make sure a
filtered email is no longer a dead end. Three strands: (1) fix the concrete
deliverability defects — a plain-text part made of raw CSS, a missing DMARC
record, no Reply-To, a Message-ID stamped with a Render container hostname;
(2) make delivery observable, so "Invitation sent" on the roster reflects
whether SMTP actually accepted the message instead of merely whether a database
row was written; (3) give the instructor two out-of-band paths that do not
depend on our mail reaching the student at all — a per-invite copy-link, and a
course join code that a pre-invited student can redeem themselves. The
authorization model does not change: `ALLOW_REGISTRATION=false` stays, and every
new path still requires a pending `CourseInvite` for that exact email address.

## Diagnosis (established this session — do not re-derive)

Live DNS for `stemquests.com` on 2026-08-02:

| Record | State |
| --- | --- |
| `resend._domainkey` DKIM | present |
| `send.stemquests.com` SPF (`v=spf1 include:amazonses.com ~all`) | present |
| `send.stemquests.com` MX (feedback-smtp) | present |
| `_dmarc.stemquests.com` | **absent** |
| `stemquests.com` TXT (root SPF) | **absent** |
| `stemquests.com` MX | **absent** |

Ranked causes:

1. **No DMARC policy.** DKIM and SPF both pass and would align (relaxed
   alignment: `send.stemquests.com` is organizationally `stemquests.com`), but
   with no `_dmarc` record there is no policy to enforce. District gateways and
   the 2024 Google/Yahoo bulk-sender rules treat this as an unauthenticated
   sender.
2. **No MX on the From domain.** `noreply@stemquests.com` cannot receive mail.
   "Sender domain does not accept mail" is a scored rule on Barracuda- and
   Proofpoint-class appliances, and a student who hits Reply gets a bounce.
3. **The text/plain part of every email is ~70 lines of raw CSS.**
   `strip_tags(html_content)` at `backend/core/email.py:57` removes tags but
   keeps the *contents* of `<style>`. Confirmed by running it against
   `backend/templates/emails/base.html`: the plain-text body opens with
   `body { font-family: -apple-system, ... }`. A text/plain part that is
   stylesheet gibberish and does not match the HTML is a textbook Bayesian
   trigger.
4. **Message-ID domain mismatch.** Django derives Message-ID from
   `socket.getfqdn()`, so production stamps a Render container hostname that has
   nothing to do with `stemquests.com`.
5. No Reply-To; a body that is mostly one call-to-action link; a domain
   registered 2026-07-23 with near-zero send volume and therefore no reputation.

And the failure was invisible: sends run on a detached daemon thread with
`fail_silently=True` (`backend/core/email.py:127-144`), `CourseInvite` has no
delivery column, and the roster renders "Invitation sent" straight from the API
response, which is built *before* the thread even runs
(`backend/courses/views.py:1802-1805`).

## Decisions made (interview, 2026-08-02)

- **Scope is email + fallback only.** Robotics 2 moves to phase 68; handoff
  items 3–5 (health-endpoint content read, branch protection, Neon backup) are
  explicitly not in this phase. ROB101 is already live, so students have content
  on day one; getting them *in* is the blocker.
- **Two fallbacks: per-invite copy-link and a course join code.**
- **The join code is a delivery channel, not an authorization.** Redeeming it
  requires the code *and* an email address that already has a pending
  `CourseInvite` on that course. A leaked code enrolls nobody. Invite-only
  survives intact.
- **Join code lives on `Course`, instructor toggles and rotates it.** No
  expiry — off is off. Rotating kills the previous code immediately.
- **Invite links are fetched on demand**, never included in the roster list
  payload, so live tokens stay out of bulk responses, browser cache, and logs.
- **Delivery result is persisted on the invite** (`email_sent_at`,
  `email_error`) and surfaced per row on the roster.
- **Sender identity: add `Reply-To: <instructor email>`.** Keep the From as
  `STEM Quest <noreply@stemquests.com>`. Consequence accepted: the instructor's
  address becomes visible to every invited student.
- Adding MX / inbound mail on the domain was **not** selected. It stays in the
  runbook as an optional, clearly-marked recommendation (it would also give
  DMARC `rua=` a self-owned destination), not as a checklist item.

## Out of scope

- Robotics 2 / ROB201 authoring — phase 68. Do not touch
  `populate_robotics_course.py` or the `ROB201` guard at
  `backend/courses/tests.py:4449-4452`.
- Making `/api/health/?deep=1` do a real content read (handoff item 3).
- Branch protection on `main`; Neon backup branch + `protected: true`
  (handoff items 4–5).
- Resend webhook ingestion of delivered/bounced/complained events. Rejected for
  this phase: largest new public surface, and SMTP-acceptance tracking answers
  the day-one question.
- Switching from Resend's SMTP relay to the Resend HTTP API, or adding an
  `anymail`/`resend` package. SMTP stays.
- Enabling registration, changing `ALLOW_REGISTRATION`, or any path that creates
  an account without a pending invite for that address.
- Inbound mail / MX / a real mailbox on `stemquests.com` (runbook-optional
  only).
- Retrying failed sends, queues, or Celery. Failures are recorded and surfaced;
  the instructor retries with the existing Resend button.
- Any change to `Course` content, XP, or `content_key` handling.

## Backend tasks

### A. Email hygiene — `backend/core/email.py`

- [x] Add `_html_to_text(html: str) -> str`: drop `<head>`, `<style>`, and
      `<script>` blocks *including their contents* before stripping tags,
      unescape HTML entities, and collapse runs of blank lines. This is the
      safety net — it must produce a clean body even for a template with no
      hand-written text partner.
- [x] In `send_templated_email`, prefer a hand-authored text template: for
      `template_name='emails/course_invite_link.html'`, try
      `emails/course_invite_link.txt` first and fall back to `_html_to_text()`
      when it does not exist. (`registration/password_reset_email.txt` is the
      existing precedent for a real text template.)
- [x] Write `backend/templates/emails/course_invite_link.txt` — greeting,
      instructor name, course title, the bare invite URL on its own line, the
      14-day expiry note. Real sentences, not a link with no context.
- [x] Write `backend/templates/emails/announcement.txt` to the same standard.
- [x] Add a `reply_to: list[str] | None = None` parameter to
      `send_templated_email` and pass it to `EmailMultiAlternatives(reply_to=...)`.
- [x] Add `_transactional_headers()` returning
      `{'Message-ID': make_msgid(domain=<domain of DEFAULT_FROM_EMAIL>)}`, and
      attach it via `extra_headers`. Parse the domain out of
      `DEFAULT_FROM_EMAIL` with `email.utils.parseaddr`, and fall back to
      Django's default when the address has no parseable domain (local dev uses
      `noreply@localhost`).
- [x] `send_course_invite_link_email` gains `reply_to` and forwards it.
- [x] `send_announcement_email` gains `reply_to`, and additionally sets
      `List-Unsubscribe: <{FRONTEND_URL}/settings>` plus
      `List-Unsubscribe-Post: List-Unsubscribe=One-Click`. Announcements are the
      opt-in bulk-ish mailing (`UserPreferences.email_announcements`); invites
      are transactional and get no unsubscribe header.
- [x] `send_emails_async`: wrap each task so that a) the exception is logged
      with the recipient, and b) `django.db.connection.close()` runs in a
      `finally` for every task. The thread opens its own DB connection once
      tasks start writing delivery state — leaving it open leaks a Neon
      connection per invite batch.

### B. Delivery visibility — `backend/courses/`

- [x] Migration on `CourseInvite`: `email_sent_at = DateTimeField(null=True,
      blank=True)` and `email_error = CharField(max_length=255, null=True,
      blank=True)`. Both nullable, therefore additive and old-code-safe — no
      `db_default` needed, and the pre-deploy migration cannot break the
      still-running old code.
- [x] `CourseInvite.refresh()` must clear `email_sent_at` and `email_error`; a
      resent invite starts a fresh delivery attempt.
- [x] Add a `delivery` property: `'failed'` if `email_error`, `'sent'` if
      `email_sent_at`, else `'pending'`. Keep it separate from `status` —
      `status` is the invite lifecycle, `delivery` is the email.
- [x] Replace `_queue_invite_email` (`backend/courses/views.py:1720`) with a
      queued callable that sends with `fail_silently=False`, then writes
      `email_sent_at=timezone.now(), email_error=None` on success or
      `email_error=str(exc)[:255]` on failure, via a targeted
      `CourseInvite.objects.filter(pk=...).update(...)` so it cannot clobber a
      concurrent revoke.
- [x] Pass `reply_to=[invite.course.instructor.email]` when queueing, but only
      when that address is non-empty and is not the demo account
      (`core.demo.is_demo_email`).
- [x] `CourseInviteSerializer`: add read-only `email_sent_at`, `email_error`,
      and `delivery`. **Do not add `token` or `invite_url`.**

### C. On-demand invite link

- [x] `GET /api/courses/courses/<code>/invites/<id>/link/` → `invite_link` view.
      `IsAuthenticated` + `require_course_instructor(request.user, course, ...)`
      per `.claude/rules/backend.md`. Returns `{'invite_url': ...}`.
- [x] 404 when the invite id belongs to a different course (path scoping must
      be enforced, not assumed).
- [x] 400 with a `detail` when the invite is not pending (accepted, revoked, or
      expired) — handing out a dead link is worse than refusing.
- [x] Build the URL with the same helper the email uses, so the two can never
      drift.
- [x] New scoped throttle `invite_link`, rate from `THROTTLE_INVITE_LINK`
      (unset = unlimited, matching the existing pattern at
      `backend/config/settings.py:311-315`). Document it in `render.yaml`'s
      env-var inventory with a suggested `60/hour`.

### D. Course join code

- [x] `[P]` `Course.join_code = CharField(max_length=12, null=True, blank=True,
      unique=True, db_index=True)`. Nullable and unique — Postgres allows
      multiple NULLs, so "no code" is the default for every existing course.
      Additive, old-code-safe.
- [x] `[P]` `generate_join_code()`: 8 characters from the unambiguous alphabet
      `ABCDEFGHJKMNPQRSTUVWXYZ23456789` (no `0/O`, no `1/I/L` — students will
      read these off a whiteboard), using `secrets.choice`. Retry on the unique
      collision. Store normalized uppercase.
- [x] `[P]` `normalize_join_code(raw)`: uppercase, strip whitespace and dashes.
      Input must tolerate `abcd-2345`, `ABCD 2345`, and `ABCD2345` alike.
- [x] `GET/POST/DELETE /api/courses/courses/<code>/join-code/` → instructor-only
      via `require_course_instructor`. GET returns `{'join_code': <code|null>}`;
      POST generates or rotates (the previous code stops working the instant it
      is replaced) and returns the new code; DELETE sets it to null.
- [x] `POST /api/courses/join/` → `AllowAny`. Body `{'join_code', 'email'}`.
      Normalize both. Resolve the course by `join_code` (a null code must never
      match — guard explicitly rather than relying on the lookup). Find a
      **pending** `CourseInvite` for `(course, email)`. On success return
      `{'token': invite.token, 'course_title': ..., 'course_code': ...}`; the
      frontend then routes to the existing `/invite/<token>` accept flow, so no
      account-creation logic is duplicated.
- [x] Every failure mode of `/join/` returns **one identical generic 400**
      (`"That code and email don't match an open invitation."`) — unknown code,
      disabled code, unknown email, already-accepted, revoked, and expired must
      be indistinguishable. Otherwise the endpoint is an oracle for "is
      alice@district.edu invited to this course?"
- [x] The demo course must never be joinable. Refuse both the instructor
      join-code endpoints and `/join/` for it; check the existing helpers in
      `backend/core/demo.py` for how the demo course is identified rather than
      hardcoding a code, and follow the established `403 demo_blocked` shape.
- [x] New scoped throttle `join_code`, rate from `THROTTLE_JOIN_CODE`; suggest
      `10/hour` in `render.yaml`, matching `THROTTLE_INVITE_ACCEPT`. Anonymous
      callers throttle by IP through the existing client-IP throttle class.
- [x] `/join/` must not create users, sessions, or enrollments — it only
      resolves a token. All account creation stays in `accept_invite`, which
      already works with `ALLOW_REGISTRATION=false`.

## Frontend tasks

- [x] `[P]` `frontend/src/types/index.ts`: extend `CourseInvite` with
      `email_sent_at: string | null`, `email_error: string | null`,
      `delivery: 'pending' | 'sent' | 'failed'`; add `JoinCodeResponse` and
      `JoinWithCodeResponse`.
- [x] `[P]` `frontend/src/services/invites.ts`: add `getInviteLink(courseCode,
      inviteId)` and `joinWithCode(joinCode, email)`.
- [x] `[P]` Join-code management calls (`getJoinCode`, `rotateJoinCode`,
      `disableJoinCode`) in the course service alongside the other
      instructor-scoped course calls.
- [x] `StudentRosterPage.tsx` — delivery column on the open-invitations table.
      Copy must be honest: a "Sent" badge means our mail server accepted it, not
      that it reached the inbox. Show `email_error` on failed rows.
- [x] `StudentRosterPage.tsx` — per-row **Copy link** button on pending invites:
      calls the link endpoint on click, writes to `navigator.clipboard`, shows a
      transient "Copied" confirmation. Handle the clipboard-permission rejection
      by revealing the URL in a selectable field instead of failing silently.
- [x] `StudentRosterPage.tsx` — join-code card: the code rendered large and
      unmistakable (per the standing readability preference — big type, real
      buttons, prominent), a copy button, Generate / Rotate / Turn off actions,
      one line of instructions the instructor can paste to students, and an
      explicit warning on Rotate that the old code stops working immediately.
- [x] `[P]` New public page `frontend/src/pages/auth/JoinWithCodePage.tsx` at
      `/join`: code + email fields, submits to `joinWithCode`, navigates to
      `/invite/<token>` on success, renders the single generic error otherwise.
      Route it in `App.tsx` next to the existing `/invite/:token` route.
- [x] `[P]` A "Have a class code?" link to `/join` on the login page.

## Docs

- [x] `[P]` `docs/runbooks/phase-67-email-deliverability-dns.txt` — plain text,
      user-executable, no markdown. Must cover:
  - Cloudflare → DNS → add `_dmarc.stemquests.com` TXT
    `v=DMARC1; p=none; fo=1` (start at `p=none`; tighten to `p=quarantine`
    after a week of clean sending). DNS-only, not proxied.
  - Add root SPF: `stemquests.com` TXT `v=spf1 include:amazonses.com ~all`.
  - Optional, clearly marked as not required: Cloudflare Email Routing to give
    the domain MX records and a real forwarding address — this removes the
    "sender domain has no MX" penalty and gives DMARC a self-owned `rua=`
    destination.
  - Verification: the exact `dig` commands, a send to a personal address with
    Gmail's "Show original" showing SPF / DKIM / DMARC all PASS, and a
    mail-tester.com run.
  - The real test: one invite to the school address that previously vanished,
    plus what to check in the Resend dashboard (Emails → the send and its
    status) if it still does not arrive.
  - The fallback script for day one: copy-link and join code, so a filtered
    student is never blocked.

## Verification

Backend (`cd backend && pytest`):

- [x] `test_plaintext_part_contains_no_css` — send an invite, assert the
      text/plain body contains neither `font-family` nor `background-color`,
      and does contain the invite URL and the course title.
- [x] `test_plaintext_falls_back_cleanly_without_txt_template` — render a
      template that has no `.txt` partner and assert `_html_to_text` still
      produced CSS-free output.
- [x] `test_invite_email_sets_reply_to_instructor` and a companion asserting no
      Reply-To is set when the instructor address is the demo account.
- [x] `test_message_id_domain_matches_from_domain`.
- [x] `test_announcement_sets_list_unsubscribe_headers`; invite email asserts
      the header is **absent**.
- [x] `test_invite_records_email_sent_at_on_success` and
      `test_invite_records_email_error_on_failure` (patch the send to raise;
      assert the row carries a truncated error and `delivery == 'failed'`).
- [x] `test_refresh_clears_delivery_state`.
- [x] Link endpoint permission boundary, per `.claude/rules/backend.md`:
      instructor 200 and the body contains the token; a different instructor
      403; enrolled student 403; anonymous 401/403; invite from another course
      404; accepted / revoked / expired invite 400.
- [x] Join-code management boundary: instructor 200; non-instructor 403;
      anonymous 401/403; rotate returns a different code and the previous code
      no longer resolves; DELETE nulls it and `/join/` then refuses.
- [x] `/join/` happy path returns the token of the pending invite, and the
      token then drives `accept_invite` to a working account end to end.
- [x] `/join/` uniform-failure test: unknown code, disabled (null) code,
      unknown email, revoked invite, expired invite, and already-accepted invite
      all return the identical status and identical `detail` string. Assert
      equality across all six responses — this is the enumeration guard.
- [x] `test_join_code_input_is_normalized` — `abcd-2345`, `ABCD 2345`, and
      `ABCD2345` all resolve to the same course.
- [x] `test_join_code_alphabet_has_no_ambiguous_characters`.
- [x] Demo course refuses both join-code management and `/join/`.
- [x] Scoped throttle tests for `invite_link` and `join_code`, following the
      pattern at `backend/courses/tests.py:3657-3706`.
- [x] `/join/` creates no `User` and no `Enrollment` (assert counts unchanged).
- [x] Migration check: run the `db-migration-checker` agent over the new
      migration; both new fields must be nullable with no data migration.

Frontend:

- [x] `cd frontend && npx tsc --noEmit` → 0 errors.
- [x] `cd frontend && npm run lint` → clean (the 1 known warning may remain).
- [x] `npx vitest run` → all pass; add a `JoinWithCodePage` test covering the
      generic-error render and the success redirect.

Whole stack:

- [x] `/verify-stack` → PASS, output pasted as evidence.

Manual click-through (local Docker, instructor account):

- [x] Roster → invite an address → row shows **Sent** with no manual reload.
      Verified in local Docker via Chrome. The break-SMTP half is NOT done as
      a click-through — `EMAIL_BACKEND` is the console backend locally, so it
      cannot fail. The **Failed** path is covered by
      `test_invite_records_email_error_on_failure` (asserts the truncated
      error and `delivery == 'failed'`); the row rendering it is the same
      code path as **Sent**.
- [~] Copy link on a pending invite. The endpoint is verified (200, correct
      token) and the accept flow is verified end to end via the join-code
      path below, which lands on the same `/invite/<token>` page. The
      button's own **Copied** / reveal-on-block states could NOT be confirmed
      under Chrome automation: `navigator.clipboard.writeText` never settles
      there. That finding produced a real fix (a 2s timeout that now treats
      a non-settling clipboard as blocked and reveals the URL). Worth one
      human click to confirm the badge.
- [x] Generated a join code on ROB101 (`6FQVBUX5`), submitted `6fqv-bux5`
      (lowercase + dash) with the invited address at `/join` → landed on
      `/invite/<token>` showing "Join Robotics 1" and the masked address.
      Account creation itself is covered by
      `test_token_then_drives_accept_end_to_end`.
- [x] `/join` with a non-matching submission → the single generic error
      renders. No-account-created is pinned by
      `test_join_creates_no_user_and_no_enrollment`.
- [x] Turn off → card resets to Generate, and `POST /api/courses/join/` with
      the old code returns the generic 400. Rotate is covered by
      `test_rotation_kills_the_previous_code_immediately`.

Production (after merge — merging `main` deploys the backend):

- [ ] DNS runbook applied; `dig TXT _dmarc.stemquests.com` returns the record.
- [ ] Verify the deploy with a **real content read**, not just
      `/api/health/?deep=1` — that endpoint runs `SELECT 1` and reported 200
      through the phase-65 outage.
- [ ] Send one invite to the school address that previously vanished. If it
      lands, the phase is proven. If it does not, the copy-link and join-code
      paths mean day one still works — and the Resend dashboard plus the new
      `email_error` column will say whether it left our side at all.

## Notes for the implementer

- Backend changes need `docker compose restart backend` to take effect.
- The migration is additive and nullable, so the pre-deploy migrate window is
  safe — but keep it that way; do not add a NOT NULL column without
  `db_default`.
- `send_emails_async` runs on a daemon thread. Tests must not rely on thread
  timing: either call the queued callable directly or patch
  `send_emails_async` to run tasks inline.
- `Reply-To` exposes the instructor's address to every invited student. That was
  an explicit decision, not an oversight.
