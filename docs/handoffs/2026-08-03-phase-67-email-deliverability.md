# Handoff: Phase 67 email deliverability + invite fallbacks — MERGED and LIVE

## Current state
**Phase 67 is MERGED and DEPLOYED.** PR #96 squash-merged as `42e6c0c`; migration
`courses/0026` applied in prod at 2026-08-03 19:56:26Z by `preDeployCommand`, ~1 min
after the merge. Verified with a REAL content read (`DEMO101/units/` → 5 units / 20
lessons), not just `/api/health/?deep=1`. `POST /api/courses/join/` returns the
generic 400 in prod. Prod holds 3 courses with 0 join codes and 3 invites with NULL
delivery — nothing changed for anyone.
**Two owner actions remain before inviting students: the Render throttle env vars and
the DNS records. Neither is code; see Next steps 1-2.**
Spec: `docs/specs/phase-67-email-deliverability-and-invite-fallback.md`.
- Email hygiene (`backend/core/email.py`): `_html_to_text` + hand-authored
  `backend/templates/emails/{course_invite_link,announcement}.txt`, `reply_to`,
  From-domain `Message-ID`, `List-Unsubscribe` on announcements only, per-task
  logging + `connection.close()` in `send_emails_async`.
- Delivery visibility: `CourseInvite.email_sent_at` / `email_error` / `delivery`
  (migration `courses/0026`), written via targeted `filter(pk=).update()`.
- Fallbacks: `GET .../invites/<id>/link/`, `GET/POST/DELETE .../join-code/`,
  `POST /api/courses/join/`, plus `frontend/src/pages/auth/JoinWithCodePage.tsx`
  at `/join` and the delivery column + copy-link + class-code card on
  `StudentRosterPage.tsx`.
- Runbook: `docs/runbooks/phase-67-email-deliverability-dns.txt`.
- Final: pytest **1043**, tsc 0, lint 0 (+1 known), vitest **140**.

## In progress / not done
- **Nothing in the phase is half-built.** Two verification gaps, both explained in
  the spec: the **Failed** delivery row was not click-through tested (local
  `EMAIL_BACKEND` is the console backend, so a send cannot fail — covered by
  `test_invite_records_email_error_on_failure`), and the Copy-link button's
  **Copied** / reveal states could not be confirmed under Chrome automation
  because `navigator.clipboard.writeText` never settles there.
- A stray `feat/phase-67-email-deliverability` branch exists on the **retired**
  `origin` repo (`dev-learning-platform`) — pushed there by mistake; deleting it
  was blocked by a permission classifier. Harmless, delete when convenient.
- Carried from phase 66, none launch-blocking: `THROTTLE_SLIDE_IMPORT` ceiling;
  phase-61 slide-import smoke test; JAVA101 answer-rotation reseed; phase-56/64
  click-throughs; Sentry LoginPage; Dependabot #68/#86/#87/#88.

## Next steps
1. **Set `THROTTLE_JOIN_CODE=10/hour` and `THROTTLE_INVITE_LINK=60/hour`** in the
   Render dashboard (backend service → Environment; it restarts itself). Without the
   first, the public `/join/` runs on the general anon ceiling only. Do this BEFORE
   any student invites go out.
2. **Apply the DNS runbook** — `docs/runbooks/phase-67-email-deliverability-dns.txt`.
   This is where most of the deliverability win is; the merged code adds no DMARC
   record. Confirmed still absent 2026-08-03: `_dmarc`, root SPF, root MX. Cloudflare,
   DNS-only (grey cloud): `_dmarc.stemquests.com` TXT `v=DMARC1; p=none; fo=1`, and
   root TXT `v=spf1 include:amazonses.com ~all`.
3. **Send ONE invite to the school address that previously vanished**, then check
   Gmail "Show original" (SPF/DKIM/DMARC all PASS) and the Resend dashboard. This is
   the only thing that actually proves the phase.
4. **Decide on the join-code design consequence** (see Decisions). Closing it means
   scoping a code to a single successful redemption.
5. **Phase 68 — close the enrollment-code hole in invite-only** (decided 2026-08-03,
   deferred here from phase 67). `CourseViewSet.enroll` (`backend/courses/views.py:100`)
   checks ONLY `enrollment_code` — no invite. So the code alone is the authorization,
   and any student who learns another course's code can self-enroll without ever being
   invited. Harmless today (prod has 0 students, and `IsAuthenticated` means it is
   unreachable without an account while `ALLOW_REGISTRATION=False`), but it becomes
   live the moment the cohort has accounts. Second problem: the ENROLLMENT CODE box is
   the most prominent code on `ManageCoursePage.tsx:513`, so it is what an instructor
   is most likely to read to the class — and it fails for every student who has no
   account yet, which on day one is all of them.
   Do: require a pending `CourseInvite` in `enroll` while registration is off, and
   hide the enrollment-code box under the same condition. Do NOT delete the
   enrollment-code mechanism — it is the right tool again if registration is ever
   re-enabled. Needs a permission-boundary test per `.claude/rules/backend.md`.
6. Phase 68: Robotics 2 / ROB201 authoring. Delete the local ROB201 stub first.
   Then handoff items 3–5 from phase 66 (health-endpoint content read, branch
   protection, Neon backup branch + `protected: true`).

## Decisions made
- **The join code is a delivery channel, not an authorization.** Redeeming needs the
  code AND an address with a pending invite; all six failure modes return one
  identical 400 so it cannot enumerate who is invited.
- **Accepted, and the reason the runbook now carries a caution:** a classmate who
  knows the code and can guess a peer's school address can claim that peer's account
  before they do. Strangers cannot. "Safe to say out loud" is true against outsiders
  only. Not closed — that is a product decision.
- **`join_with_code` matches email EXACTLY, never `iexact`.** A round-1 review
  suggested `iexact`; round 2 proved it lets Turkish dotless i (U+0131) collide with
  ASCII `i` under Postgres `UPPER()`, handing one student another's token. Reverted,
  with the reasoning in a comment so nobody re-applies it.
- **`is_demo_course` ignores `is_active`** — a soft-deleted demo enrollment must not
  silently switch the guard off.
- **The enrollment code and the class code are NOT redundant, and the enrollment code
  is dead weight under invite-only** (user raised this 2026-08-03). Enrollment code:
  `IsAuthenticated`, and the code by itself authorizes enrollment — useful only to
  someone who already has an account, e.g. adding a second course. Class code:
  `AllowAny`, authorizes nothing, only resolves a pending invite for that exact
  address. With `ALLOW_REGISTRATION=False` a new student can never reach the
  enrollment-code path at all, which is exactly why phase 67 needed a separate
  mechanism. Tightening it was deferred to phase 68 rather than bolted onto this
  phase — see Next steps 5.
- `Course.join_code` omits the spec's `db_index=True`: `sqlmigrate` shows
  `unique=True` produces identical DDL.
- `List-Unsubscribe-Post` was kept as the spec dictates even though it points at a
  SPA route with no POST handler. Flagged in the PR as a follow-up.

## Gotchas discovered
- **Django autoescape is per-engine, not per-extension.** A `.txt` email template
  escapes its variables (`Mr. O&#x27;Brien`) unless wrapped in `{% autoescape off %}`.
- **`@throttle_classes` replaces `DEFAULT_THROTTLE_CLASSES` wholesale**, and
  `AnonRateThrottle` returns no cache key once a request is authenticated — list the
  user throttle too or logged-in callers get no ceiling at all.
- **`CourseInvite.refresh()` does not touch `created_at`** (`auto_now_add`), so row
  age is the wrong signal for "is this send in flight".
- **Chrome automation:** `navigator.clipboard.writeText` never settles (produced a
  real 2s-timeout fix); ref-based clicks go stale after a re-render — use coordinates
  or `form.requestSubmit()`.
- **Running pytest alongside review subagents gives false failures** (shared test DB).
  Confirmed again — run the suite alone.
- Local instructor login for click-throughs: `instructor@demo.com` / `LocalDev123!`
  (password set locally this session; `clone_course_for_demo` normally leaves it
  unusable). Local dev DB only.

## Files to read first
1. `docs/specs/phase-67-email-deliverability-and-invite-fallback.md` — the contract
   and both adversarial passes' outcomes.
2. `docs/runbooks/phase-67-email-deliverability-dns.txt` — the DNS steps still to do.
3. `backend/courses/views.py` — `join_with_code`, `invite_link`, `course_join_code`,
   `_send_invite_email_and_record`, `_delivery_error_text`.
4. `backend/core/email.py` — `_html_to_text` and the header helpers.
5. `backend/courses/management/commands/populate_robotics_course.py` — the pattern
   for phase 68, plus `_content_upsert.py` for the `content_key` rules.
