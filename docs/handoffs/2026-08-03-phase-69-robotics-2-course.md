# Handoff: Phase 69 Robotics 2 (ROB201) course

## Current state
**Phase 69 is COMPLETE; PR #98 is OPEN and not merged.**
https://github.com/Cesar6060/LMS/pull/98 — branch
`feat/phase-69-robotics-2-course` on `lms`. Both CI jobs green on `b0da3c4`.
Spec: `docs/specs/phase-69-robotics-2-course.md` — every Backend/Frontend/
Verification item checked; Prerequisites + Production stay open owner actions.

Ships **ROB201 "Robotics 2"**, TEKS Robotics II (19 TAC §127.750), six units /
24 lessons / **120 sections** / 96 comprehension questions / 6 unit quizzes /
36 quiz questions. All twelve strands (c)(1)–(c)(12) cited. Python replaces
ROB101's pseudocode; AI is its own unit. Kit-free, free simulators only.
- `backend/courses/management/commands/populate_robotics_2_course.py` (~5,950
  lines), modeled end-to-end on `populate_robotics_course.py`.
- `backend/courses/tests.py` — `TestPopulateRobotics2Course` (28 tests).
- `backend/courses/test_populate_courses.py` — ROB201 in `COMMANDS` + three
  parametrize lists.
- **No migration** (`makemigrations --check` clean), **zero `frontend/` files**.
- Verified: pytest **1142** (baseline 1106), tsc 0, lint 0 (+1 known warning),
  vitest **154**. Seeded 3× (run 2 pk-stable, run 3 `--prune` clean);
  ROB101/JAVA101/DEMO101 untouched. Full click-through passed every step.
- Two review passes (code-reviewer, adversarial-tester): **no BROKEN findings.**

## In progress / not done
- **Nothing in the phase is half-built.** Merging is the user's call.
- **ROB201 does not exist in production.** Merging deploys the command but
  changes no data; someone must seed it by hand (see Next steps 2).
- Carried, none launch-blocking: JAVA101 answer-rotation reseed (still every
  correct answer at position 0, inherited by DEMO101); `THROTTLE_SLIDE_IMPORT`
  ceiling; phase-61 slide-import smoke test; phase-56/64 click-throughs; Sentry
  LoginPage; Dependabot #68/#86/#87/#88.
- Deferred SUSPICIOUS, all inherited from `_content_upsert.py` and live for
  ROB101/JAVA101 too, listed in the PR body: a reseed silently reverts an
  instructor's unit reorder; `--prune` cascades student progress with only a
  stdout warning; `_get_instructor` resolves duplicate/inactive namesakes
  non-deterministically.

## Next steps
1. **Merge PR #98.** Deploy changes no data — verify with `/api/health/?deep=1`
   (must still contain verbatim `"database": "ok"`) plus a real content read,
   and confirm UptimeRobot monitor `803564235` is still UP.
2. **Fresh Neon backup branch + production `protected: true`** (LMS project
   `shy-cloud-68280619`) — **before** seeding ROB201. Still the highest-value
   item outstanding; the newest backup predates several schema changes.
3. **Seed ROB201 into prod by hand**: `DATABASE_URL=<neon direct, non-pooler>
   python manage.py populate_robotics_2_course`, **without `--prune`** on the
   first run. Then load `/courses/ROB201` on stemquests.com as the instructor
   and confirm ROB101/JAVA101 are intact.
4. **Branch protection on `main`**, requiring both CI jobs. Merging deploys.
5. **Owner actions still open from phase 67**: `THROTTLE_JOIN_CODE=10/hour` and
   `THROTTLE_INVITE_LINK=60/hour` in Render; apply
   `docs/runbooks/phase-67-email-deliverability-dns.txt` (`_dmarc` + root SPF,
   both still absent); send one invite to the school address and check Gmail
   "Show original" for SPF/DKIM/DMARC PASS.

## Decisions made
- **Full parity with ROB101, not a reduced first cut** (user, interview).
  Python + free simulators; AI as its own unit; no prerequisite enforcement.
- **JAVA101's answer rotation stays carried** — students this term are on
  robotics and Python. Fixing it needs a data migration because
  `_content_upsert` matches choices positionally.
- **Course list ordering accepted as-is.** `Meta.ordering = ['-created_at']`
  puts ROB201 **above** ROB101 everywhere; confirmed in the click-through.
- **Delete the local stub before writing the command, not after.** It was
  adoptable (`auto:`-keyed lessons), so `get_or_create` would have grafted onto
  it. ROB201 is pk 19 vs ROB101's pk 10 — proof it was created, not adopted.
- **Uniform quiz titles** (`<topic> Quiz`), deliberately not copying ROB101's
  inconsistent `Unit 1 Quiz:` prefix on one of six.
- **Stripped inline-code backticks from markdown table cells only.** Tailwind
  Typography injects a literal backtick around every `<code>`; in table cells
  that read as clutter. Prose inline code left alone for consistency with
  ROB101/JAVA101, which ship the same way.

## Gotchas discovered
- **Registering a command in `test_populate_courses.py`'s `COMMANDS` list does
  NOT buy adoption, `--prune` or instructor-guard coverage.** `TestAdoption`,
  `TestPruneFlag` and `TestInstructorGuard` hardcode `populate_robotics_course`
  rather than reading `COMMANDS`. The spec claimed otherwise and was wrong; the
  adversarial pass caught it. Six ROB201 tests were promoted to close the gap.
  **If a phase 70 adds a fourth course, the same trap is still there** — those
  three classes are still hardcoded.
- **Tailwind Typography adds the backticks you see around inline code**
  (`content: '"\`"'` on `code::before`/`::after`). The markdown renders fine;
  it is styling, and it is platform-wide.
- **The lesson player caches quiz state.** Reseeding with a lesson page open
  gives "Failed to start the quiz session"; a reload fixes it. Not a bug.
- **`upsert_sections` writes only `title`/`content`/`video_type`/`video_id`** —
  it will not write `layout`/`image`/`image_alt`, so a seed can never clobber an
  imported slide.
- Local logins: `instructor@demo.com` / `student1@demo.com`, both `LocalDev123!`
  (re-set this session; the previous session's passwords did not survive).
- Enrollment is invite-gated since phase 68 — issue a `CourseInvite` before any
  click-through that enrolls a student, or the code alone 403s.

## Files to read first
1. `docs/specs/phase-69-robotics-2-course.md` — contract plus the Outcomes
   section recording both review passes and the three deferred findings.
2. `backend/courses/management/commands/_content_upsert.py` — the upsert
   contract and the `content_key` rules every seed must follow.
3. `backend/courses/management/commands/populate_robotics_2_course.py` — the
   skeleton is the first ~200 lines; the rest is authored content.
4. `backend/courses/tests.py` — `TestPopulateRobotics2Course`, especially the
   six tests promoted from the adversarial pass at the end of the class.
5. `docs/handoffs/2026-08-03-phase-68-invite-only-enrollment.md` — the carried
   owner actions, which phase 69 folded forward but did not perform.
