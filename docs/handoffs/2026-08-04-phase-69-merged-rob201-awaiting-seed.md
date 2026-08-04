# Handoff: Phase 69 MERGED — ROB201 shipped, not yet seeded

## Current state
**Phase 69 is COMPLETE and PR #98 is MERGED** (squash `863597c`, 2026-08-04).
Backend deployed to Render; deploy verified. Branch deleted.
Spec: `docs/specs/phase-69-robotics-2-course.md` — every Backend/Frontend/
Verification item checked, plus the post-merge deploy checks.

**The critical thing to know: ROB201 does not exist in production.** The merge
shipped a management command, not content. Prod still holds exactly DEMO101,
JAVA101 and ROB101. Someone must run the seed by hand (Next steps 2).

What shipped:
- `backend/courses/management/commands/populate_robotics_2_course.py` (~5,950
  lines) — ROB201 "Robotics 2", TEKS Robotics II (19 TAC §127.750). Six units /
  24 lessons / 120 sections / 96 comprehension questions / 6 unit quizzes /
  36 quiz questions. All twelve strands (c)(1)–(c)(12) cited. Python replaces
  ROB101's pseudocode; AI is its own unit. Kit-free, free simulators only.
- `backend/courses/tests.py` — `TestPopulateRobotics2Course` (28 tests).
- `backend/courses/test_populate_courses.py` — ROB201 in `COMMANDS` + three
  parametrize lists.
- **No migration**, zero `frontend/` files.
- Final: pytest **1142** (baseline 1106), tsc 0, lint 0 (+1 known), vitest 154.
  Both CI jobs green on the merged commit.

Verified before merging: 45 local migration files against 45 rows in prod's
`django_migrations` for our six apps (accounts 3, courses 26, discussions 1,
gamification 6, notifications 5, quizzes 4) — fully in sync, and this PR added
none, so the Render pre-deploy `migrate` was a no-op.

Verified after merging: authenticated `DEMO101/units/` read → **200, 5 units**
with populated `lesson_count`/`is_locked`; `/api/health/?deep=1` →
`{"status": "ok", "database": "ok", "content": "ok"}`; UptimeRobot monitor
`803564235` **UP**, 13d 4h unbroken; DEMO101 5/20, JAVA101 5/20, ROB101 6/24
all unchanged.

## In progress / not done
- **ROB201 is not in production.** Nothing is half-built — the seed is a
  deliberate manual step that has not been run.
- **The Neon backup + `protected: true` is still not done**, and it now gates
  the seed. This is the last thing standing between the current state and real
  student data.
- Carried, none launch-blocking: JAVA101 answer-rotation reseed (every correct
  answer still at position 0, inherited by DEMO101); `THROTTLE_SLIDE_IMPORT`
  ceiling; phase-61 slide-import smoke test; phase-56/64 click-throughs; Sentry
  LoginPage; Dependabot #68/#86/#87/#88.
- Deferred SUSPICIOUS from the phase-69 adversarial pass, all inherited from
  `_content_upsert.py` and already live for ROB101/JAVA101 — recorded in the
  spec's Outcomes: a reseed silently reverts an instructor's unit reorder;
  `--prune` cascades student progress with only a stdout warning; and
  `_get_instructor` resolves duplicate or inactive namesakes non-deterministically.

## Next steps
1. **Fresh Neon backup branch, then production `protected: true`** (LMS project
   `shy-cloud-68280619`). Do this FIRST — the seed below is the first write of
   new content since the backup gap was identified, and the newest backup
   predates several schema changes.
2. **Seed ROB201 into prod by hand** from a dev machine:
   `DATABASE_URL=<neon direct, non-pooler> python manage.py
   populate_robotics_2_course` — **without `--prune` on the first run.** Read
   the stale-content warnings before deciding anything.
3. **Verify the seed** with a real content read: load `/courses/ROB201` on
   stemquests.com as the instructor and confirm the six-unit outline. Then
   re-confirm DEMO101 5/20, JAVA101 5/20 and ROB101 6/24 are untouched, and
   that monitor `803564235` is still UP.
4. **Branch protection on `main`**, requiring both CI jobs. Merging deploys, so
   today a red build can still reach production.
5. **Owner actions still open from phase 67**: set `THROTTLE_JOIN_CODE=10/hour`
   and `THROTTLE_INVITE_LINK=60/hour` in Render; apply
   `docs/runbooks/phase-67-email-deliverability-dns.txt` (`_dmarc` + root SPF,
   both still absent); send one invite to the school address that vanished and
   check Gmail "Show original" for SPF/DKIM/DMARC PASS.
6. Phase 70 is unscoped. If it authors a fourth course, read the `COMMANDS`
   gotcha below first.

## Decisions made
- **Merged despite the Neon backup still being open**, because the merge
  changes no data: no migrations, and the seed is a separate manual step. The
  backup gates the *seed*, not the merge.
- **Squash-merged**, matching the convention of PRs #95/#96/#97.
- **Full parity with ROB101, not a reduced first cut** (user, interview):
  Python + free simulators, AI as its own unit, no prerequisite enforcement.
- **JAVA101's answer rotation stays carried** — students this term are on
  robotics and Python. Fixing it needs a data migration because
  `_content_upsert` matches choices positionally.
- **Course list ordering accepted as-is.** `Meta.ordering = ['-created_at']`
  will put ROB201 **above** ROB101 everywhere once seeded; confirmed locally.
- **Uniform quiz titles** (`<topic> Quiz`), deliberately not copying ROB101's
  inconsistent `Unit 1 Quiz:` prefix on one of six.

## Gotchas discovered
- **Registering a command in `test_populate_courses.py`'s `COMMANDS` list does
  NOT buy adoption, `--prune` or instructor-guard coverage.** `TestAdoption`,
  `TestPruneFlag` and `TestInstructorGuard` hardcode `populate_robotics_course`
  rather than reading `COMMANDS`. The phase-69 spec claimed otherwise and was
  wrong; the adversarial pass caught it and six ROB201 tests were promoted to
  close the gap. **Those three classes are still hardcoded — a fourth course
  hits the same trap.**
- **Tailwind Typography adds the backticks you see around inline code**
  (`content: '"\`"'` on `code::before`/`::after`). The markdown renders fine;
  it is styling, and it is platform-wide across ROB101/JAVA101 too.
- **The lesson player caches quiz state.** Reseeding with a lesson page open
  gives "Failed to start the quiz session"; a reload fixes it. Not a bug.
- **`upsert_sections` writes only `title`/`content`/`video_type`/`video_id`** —
  it will not write `layout`/`image`/`image_alt`, so a seed can never clobber an
  imported slide.
- Local logins: `instructor@demo.com` / `student1@demo.com`, both `LocalDev123!`
  (re-set 2026-08-03; the previous session's passwords did not survive).
- Enrollment is invite-gated since phase 68 — issue a `CourseInvite` before any
  click-through that enrolls a student, or the code alone 403s.

## Files to read first
1. `docs/specs/phase-69-robotics-2-course.md` — the contract plus Outcomes,
   which records both review passes and the three deferred findings.
2. `backend/courses/management/commands/_content_upsert.py` — the upsert
   contract and the `content_key` rules every seed must follow.
3. `backend/courses/management/commands/populate_robotics_2_course.py` — the
   skeleton is the first ~200 lines; the rest is authored content.
4. `backend/courses/tests.py` — `TestPopulateRobotics2Course`, especially the
   six tests promoted from the adversarial pass at the end of the class.
5. `docs/handoffs/2026-08-03-phase-68-invite-only-enrollment.md` — the carried
   owner actions, which phases 68 and 69 both folded forward but never performed.
