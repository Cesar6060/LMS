# Handoff: Phase 69 CLOSED — ROB201 is live in production

## Current state
**Phase 69 is finished.** ROB201 "Robotics 2" was seeded into production on
2026-08-06 and verified through the real app. Production now serves four
courses: DEMO101, JAVA101, ROB101, **ROB201**.

This session ran no implementation code — it was the phase-69 production
close-out. `/start-phase` was invoked but deliberately **stopped** before
writing a spec, because phase 69 still had open production steps.

What happened:
- Neon backup branch `backup-pre-rob201-seed-2026-08-06`
  (`br-sweet-paper-avvy9whb`) forked from `production`, verified at 45
  migrations / 3 courses / 16 units / 64 lessons / 5 users.
- Seeded via the backend container against the Neon **direct (non-pooler)**
  endpoint, **no `--prune`**. Output: `Course: ROB201 - Robotics 2 (created)`,
  `Created 6 units with lessons and quizzes`. No stale-content warnings.
- Post-seed prod counts match the blueprint exactly: **6 units / 24 lessons /
  120 sections / 96 comprehension questions / 6 unit quizzes / 36 quiz
  questions.**
- Verified in the browser as the instructor: `/courses/ROB201` renders the
  six-unit outline, all 24 lessons, all six `<topic> Quiz` titles at 6 Q / 20
  pts; lesson `/courses/ROB201/learn/89` opens in the player with sections, the
  comprehension gate and the unit quiz.
- Untouched, re-confirmed after the seed: DEMO101 5/20/74/85/5/25, JAVA101
  identical, ROB101 6/24/116/96/6/36. `/api/health/?deep=1` → all ok.
  UptimeRobot `803564235` UP, 16d 3h.
- Modified: `docs/specs/phase-69-robotics-2-course.md` only (checklist +
  evidence). No code changed.
- Verify: pytest **1142 passed**, tsc **0**, lint **0 errors** (1 known
  `react-refresh` warning in `ErrorBoundary.tsx`).

## In progress / not done
Nothing half-built. Four owner-dashboard actions remain, none of them code:
1. Neon `production` branch is still `protected: false`.
2. `THROTTLE_JOIN_CODE=10/hour` and `THROTTLE_INVITE_LINK=60/hour` unset in
   Render — `settings.py:321-322` default to `None`, i.e. unthrottled.
3. `_dmarc.stemquests.com` and root SPF on `stemquests.com` still absent
   (re-confirmed by `dig` 2026-08-06).
4. Invite-deliverability test to the school address that vanished.

Carried, unchanged: JAVA101 answer rotation (every correct answer at position
0, inherited by DEMO101); `THROTTLE_SLIDE_IMPORT` ceiling; phase-61 slide-import
smoke test; phase-56/64 click-throughs; Sentry LoginPage; Dependabot
#68/#86/#87/#88; the three deferred `_content_upsert` findings.

## Next steps
1. **Neon console → LMS → Branches → `production` → enable protection.** The
   MCP server exposes no branch-update tool, so this cannot be automated.
2. **Render dashboard**: set `THROTTLE_JOIN_CODE=10/hour`,
   `THROTTLE_INVITE_LINK=60/hour`.
3. **Cloudflare**: apply `docs/runbooks/phase-67-email-deliverability-dns.txt`
   — TXT `_dmarc` = `v=DMARC1; p=none; fo=1`, TXT `@` =
   `v=spf1 include:amazonses.com ~all`, both DNS-only (grey cloud). Only ONE
   root SPF record — edit, never add a second.
4. Send one invite to the school address; check Gmail "Show original" for
   SPF/DKIM/DMARC PASS.
5. **Phase 70 is decided: content-upsert hardening.** Scope it with
   `/start-phase` in a fresh session. It should fix the three deferred findings
   from the phase-69 adversarial pass: a reseed silently reverts an
   instructor's unit reorder; `--prune` cascades student progress with only a
   stdout warning; `_get_instructor` resolves duplicate/inactive namesakes
   non-deterministically. Fold in the `COMMANDS` trap below.

## Decisions made
- **Closed phase 69 before scoping phase 70** (user choice). Two spec items
  were genuinely unchecked, one of which was the seed itself — ROB201 had
  shipped as a management command but did not exist as content.
- **Took a fresh backup branch even though it was not strictly needed.** The
  handoff's claim that the newest backup predated schema changes was **wrong**:
  `backup-pre-phase68-2026-08-03` forked 2026-08-04T00:22Z, after prod's newest
  migration (2026-08-03T19:56Z), and already held all 45. Took a fresh one
  anyway — it costs nothing and names the write it precedes.
- **`enforce_admins` left OFF** on `main` branch protection (user choice), to
  keep a break-glass path. Consequence: an admin override can still put a red
  build into production, since merging `main` deploys.
- **Seeded without `--prune`**, per spec. Nothing to prune anyway — the course
  was created fresh.

## Gotchas discovered
- **Branch protection on `main` was already configured** — it had been carried
  as an open item across phases 67/68/69 but `gh api
  repos/Cesar6060/LMS/branches/main/protection` shows both CI contexts
  required, `strict: true`, force-push and deletion blocked. Verify carried
  items before doing them.
- **A locally-minted JWT will not authenticate against prod.** The container's
  `SECRET_KEY` differs, so simplejwt tokens come back
  `token_not_valid`. For an authenticated prod read, use the browser session —
  do not try to mint a token.
- **`get_connection_string` returns the POOLER host.** Strip `-pooler` from the
  hostname to get the direct endpoint the seed needs
  (`ep-falling-frog-avzgk4ed.c-11.us-east-1.aws.neon.tech`).
- **The Neon MCP server has no branch-update tool** — `protected: true` is
  console-only. `create_branch`/`delete_branch` exist, but nothing to edit
  branch settings.
- **`/api/courses/` returns 401 unauthenticated**, so curl alone cannot verify
  a content read; the deep health check reports `content: ok` regardless.
- **Registering a command in `test_populate_courses.py`'s `COMMANDS` list does
  NOT buy adoption, `--prune` or instructor-guard coverage.** `TestAdoption`,
  `TestPruneFlag` and `TestInstructorGuard` still hardcode
  `populate_robotics_course`. A fourth course hits the same trap.
- Prod holds only 5 users — you, two demo accounts, two test addresses. **No
  real student data yet**, which is why this seed was low-risk. That stops
  being true the moment the cohort enrolls.

## Files to read first
1. `docs/specs/phase-69-robotics-2-course.md` — Prerequisites and Verification
   now carry the full close-out evidence.
2. `backend/courses/management/commands/_content_upsert.py` — the upsert
   contract, and the source of all three phase-70 findings.
3. `docs/runbooks/phase-67-email-deliverability-dns.txt` — exact DNS records
   for Next steps 3.
4. `backend/courses/management/commands/populate_robotics_2_course.py` —
   `_get_instructor` at line 144 is the hardened version worth porting.
5. `backend/courses/test_populate_courses.py` — the hardcoded `COMMANDS` trap.
