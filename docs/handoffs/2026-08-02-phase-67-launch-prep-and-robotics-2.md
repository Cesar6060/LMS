# Handoff: Phase 67 launch prep + Robotics 2 — students arrive ~2026-08-09

## Current state
**Phase 66 (instructor unit locking) is MERGED and LIVE.** Phase 67 = launch prep and
the Robotics 2 course; no spec written yet, so start with one.
- PR #95 squash-merged as `5a49df3f`; deploy verified with a REAL content read
  (`DEMO101/units/` returns `is_locked: false` + populated `lesson_count`), not
  just `/api/health/?deep=1`. Prod holds 0 locked units — nothing changed for anyone.
- Final: pytest **947**, tsc 0, lint 0 (+1 known), vitest **138**, both CI jobs green.
- Prod content ready: DEMO101 + JAVA101 (5 units/20 lessons/74 sections/5 quizzes each),
  ROB101 (6/24/116/6), 352 questions. 5 users, 2 instructors, 0 students.

## In progress / not done
- **Invites are the ONLY way in.** `ALLOW_REGISTRATION=false` in prod (registration
  returns 403); staying that way by decision. Deliverability to a **school domain** is
  untested — the one prod invite ever sent (2026-07-23) went to Yahoo and was accepted
  in 2 min. District filters block unknown senders; likeliest silent day-one failure.
- **Robotics 2 not started.** `ROB201 "Robotics Engineering"` exists in LOCAL Docker
  only — 3 units × 1 generic "Understanding X" lesson. Throwaway scaffolding, NOT a
  draft; not in prod, no seed command references it.
- Carried: `THROTTLE_SLIDE_IMPORT` ceiling; phase-61 slide-import smoke test; JAVA101
  answer-rotation reseed; phase-56 + 64 click-throughs; Sentry LoginPage; Dependabot
  #68/#86/#87/#88 (React 19, eslint 10, vite 8, tailwind 4 each need a companion bump).
  None are launch-blocking.

## Next steps
1. **Send ONE invite to a real school address and confirm it lands in the inbox**
   (not spam) before inviting a cohort. Highest-risk unknown; do it first.
2. **Author Robotics 2.** Follow `populate_robotics_course.py`; delete the local ROB201
   stub first so it can't be mistaken for content. Phase-65 rule applies: every lesson
   and quiz needs a permanent authored `content_key` — changing a key later RE-AWARDS
   its XP to everyone who completed it.
3. **Make `/api/health/?deep=1` do a real content read** instead of `SELECT 1`. All six
   UptimeRobot monitors are health checks, so a total content outage alerts nobody;
   fixing the endpoint upgrades every monitor at once. Best value per line here.
4. **Branch protection on `main`** (require both CI jobs) — merging deploys.
5. **Fresh Neon backup branch + set production `protected: true`.** Branch is
   unprotected; newest backup is 11 days old and predates four schema changes. Do this
   BEFORE real student data lands.
6. Check login on a school Chromebook / filtered network.

## Decisions made
- **Invite-only stays** (user, this session). Registration remains disabled; students
  get in via instructor invites only. No code change needed — it already works this way.
- **Merged only after both CI jobs passed on the FINAL commit**, not an earlier green
  one — the backend job is what covers the migration.
- Phase 66's own decisions live in `docs/specs/phase-66-unit-locking.md`.

## Gotchas discovered
- **Invite throttling is NOT a cohort problem** — easy to misread. The endpoint takes a
  bulk `{"emails": [...]}` list with no per-request cap, and `THROTTLE_INVITE_SEND`
  (~30/hour) counts REQUESTS. One POST invites the whole class.
- **Invites expire in 14 days** (`courses/models.py:210`). Invite close to the start
  date, or a slow student is locked out.
- **`/api/health/?deep=1` is blind to content.** It runs `SELECT 1` and returned 200
  through the phase-65 course outage. Always pair it with an authenticated content read.
- Render is `plan: starter` (no spin-down), Virginia, ~175 ms — cold start is a
  non-issue. Prod API host is `api.stemquests.com`.
- Chrome automation lost host permission mid-session — re-grant in the extension if you
  need click-throughs. Carried: no pytest alongside review subagents.

## Files to read first
1. `docs/specs/phase-66-unit-locking.md` — the finished phase, both adversarial passes.
2. `backend/courses/management/commands/populate_robotics_course.py` — the pattern for
   Robotics 2, and `_content_upsert.py` for the content_key rules.
3. `backend/courses/views.py` — `course_invites` (bulk invite) and the health endpoint.
4. `render.yaml` — prod env-var inventory and throttle guidance.
