# Phase 69 — Robotics 2 course (ROB201), TEKS-aligned

## Goal

Ship a complete, student-ready **ROB201 "Robotics 2"** course seeded by a new
idempotent management command, at full parity with ROB101: six units, ~24
lessons, six unit quizzes, all authored to the Texas TEKS for Robotics II
(19 TAC §127.750, one credit, recommended grades 10–12, Robotics I as the
stated prerequisite). Content stays **platform-agnostic and kit-free** — free
simulators (VEXcode VR, Tinkercad Circuits) only — but where Robotics I taught
pseudocode and block logic, Robotics II teaches **Python**, and it gives
artificial intelligence a unit of its own, matching the TEKS course overview
("students will explore artificial intelligence and programming in the robotic
and automation industry"). The phase also deletes the stale local-Docker ROB201
rows left behind by the pre-phase-58 `seed_data` stub, so the new command
creates its course rather than adopting throwaway scaffolding.

This is a **content-only phase**. No migration, no model change, no frontend
change. The course pages, quest map, lesson player, quiz player and instructor
editor are all content-generic and were proven so by phase 58.

## Out of scope

- **No frontend work at all.** Zero files under `frontend/` should change.
  `tsc`, `lint` and `vitest` still gate the phase. If a frontend change appears
  necessary, stop and flag it — it means the phase is mis-scoped.
- **No migration and no model change.** Content-only. If `makemigrations
  --check` produces a migration, stop.
- **No course-prerequisite enforcement.** ROB201's content says it assumes
  Robotics 1; the platform does not check. No prerequisite field, no enrollment
  gate, no UI warning. (Decided in the interview — an enforcement mechanism
  would need a migration and would touch the invite-only enroll paths phase 68
  just hardened.)
- **No fix to the course list ordering.** `Course.Meta.ordering` is
  `['-created_at']`, so a freshly seeded ROB201 sorts **above** ROB101 in every
  course list. Accepted as cosmetic (decided in the interview). Do not change
  `Meta.ordering`.
- **No JAVA101 answer-rotation reseed.** Every JAVA101 correct answer still sits
  at position 0, and DEMO101 (cloned from JAVA101) inherits it. Deliberately
  left carried — students this term are on robotics and Python, not Java. Stays
  on the carried list; needs its own change plus a data migration because
  `_content_upsert` matches choices positionally.
- **No YouTube video curation.** All sections seed with `video_type='none'`; the
  instructor adds videos later in the lesson editor. No hardcoded video IDs.
- **No images, slides or attachments.** `upsert_sections` refuses to write
  `layout`/`image`/`image_alt` by design — slide decks only ever arrive through
  the phase-61 import endpoint.
- **No `CourseGradingConfig` for ROB201.** Neither `populate_*` command creates
  one; the gradebook falls back to 50/50. The deleted stub's 60/40 config goes
  away with the stub.
- **No `is_locked` in the blueprint.** Locking is an instructor action after
  seeding. Do not add it to the upsert defaults — `upsert_unit` deliberately
  passes only `title` so a reseed cannot unlock an instructor-locked unit.
- **ROB201 is not added to the demo sandbox.** `clone_course_for_demo` stays
  hardcoded to `SOURCE_CODE = 'JAVA101'`; DEMO101 remains the only demo course.
- **No running the seed against production Neon from a session.** That is an
  owner step, documented below, run by hand.
- **Does not fix carried remainders**: `THROTTLE_SLIDE_IMPORT` ceiling; phase-61
  real-deck slide-import smoke test; phase-56 and phase-64 click-throughs;
  Sentry LoginPage TypeError; Dependabot #68/#86/#87/#88.

---

## Design decisions (settled in the interview — do not relitigate)

1. **Full parity with ROB101**, not a reduced first cut. Six units, 24 lessons,
   six unit quizzes.
2. **Python is the language.** Real Python in fenced ```python blocks, run in
   free simulators (VEXcode VR supports Python) — no hardware kit assumed, same
   rule as ROB101.
3. **Artificial intelligence gets its own unit** (unit 5), rather than being
   folded into the programming unit.
4. **No prerequisite enforcement** — content-only mention.
5. **Course list ordering is accepted as-is** — ROB201 will appear above ROB101.
6. **JAVA101's answer rotation stays carried**, not fixed here.
7. **The owner seeds production**, post-merge, by hand.

---

## Prerequisites (owner actions carried from phases 67 and 68 — NOT this phase's work)

Folded in per the interview so they stay visible. None block writing or merging
this phase's code; all of them block or endanger the student cohort.

- [x] **Fresh Neon backup branch (2026-08-06).** `backup-pre-rob201-seed-2026-08-06`
      (`br-sweet-paper-avvy9whb`), forked from `production` in LMS project
      `shy-cloud-68280619` immediately before the seed. Verified to hold 45
      migrations / 3 courses / 16 units / 64 lessons / 5 users — an exact match
      for pre-seed production.
      Note: the worry that "the newest backup predates several schema changes"
      was **stale**. `backup-pre-phase68-2026-08-03` forked at 2026-08-04T00:22Z,
      after prod's newest migration (2026-08-03T19:56Z), and already held all 45.
- [ ] **Set production `protected: true`.** Still open — the Neon MCP server
      exposes no branch-update tool, so this is a console action:
      Neon → LMS → Branches → `production` → enable branch protection.
- [x] **Branch protection on `main` — already configured** (verified 2026-08-06
      via `gh api repos/Cesar6060/LMS/branches/main/protection`). Requires both
      `Backend (pytest)` and `Frontend (tsc, lint, build)`, `strict: true`,
      force-pushes and deletions blocked. `enforce_admins` deliberately left
      **off** (user decision, 2026-08-06) to preserve a break-glass path — so an
      admin override can still put a red build into production.
- [ ] Set `THROTTLE_JOIN_CODE=60/hour` and `THROTTLE_INVITE_LINK=60/hour` in the
      Render dashboard. **Corrected at phase 74:** this action originally said
      `10/hour` for the join code. Phase 73 deliberately chose 60/hour because
      throttle idents are the client address, so an entire classroom behind one
      school NAT shares a single bucket and 10/hour would lock out a normal
      class joining together. 60/hour is the settled value — do not re-litigate
      it. Both defaults are already 60/hour in `config/settings.py`, so this
      action is now a confirmation rather than a change.
- [ ] Apply `docs/runbooks/phase-67-email-deliverability-dns.txt` (`_dmarc` and
      root SPF). **Re-confirmed still absent 2026-08-06**: `dig +short TXT
      _dmarc.stemquests.com` and `dig +short TXT stemquests.com` both return
      nothing. `send.stemquests.com` correctly returns
      `v=spf1 include:amazonses.com ~all`, so only the two root-level records
      are missing.
- [ ] Send one invite to the school address that previously vanished and check
      Gmail "Show original" for SPF/DKIM/DMARC PASS.
- [ ] Carried security note, not this phase's work: `require_pending_invite`
      does not require a **verified** email. Inert while `ALLOW_REGISTRATION` is
      off. Inherited from `accept_invite` (phase 67) — fix both together or
      neither.

---

## Course structure (content blueprint)

Six units, TEKS strand citations from **§127.750(c)(1)–(c)(12)** in parentheses.
**24 lessons, 4 per unit.** Each lesson = 4–5 markdown `LessonSection`s + exactly
4 `LessonQuestion`s (4 choices, exactly 1 correct). Each unit = one
`quizzes.Quiz` with 6 questions, `passing_score=70`, `points=20`,
`max_attempts=3`, `order=0`.

Section 0 of every lesson is titled **"Overview"** and follows ROB101's template:
`# <Lesson Title>`, a hook paragraph, `## Learning Objectives` with 4 bullets,
then a closing `> **TEKS alignment:** §127.750(c)(N) — ...` blockquote.

### Unit 1 (order 0) — Advanced Systems, Safety & Teams
(c)(1) employability, (c)(3) teamwork, (c)(5) safety, (c)(6) technological systems

| # | Lesson | `content_key` | Strand |
|---|---|---|---|
| 0 | From Robotics 1 to Robotics 2: Systems at Scale | `rob201-from-robotics-1-to-robotics-2` | (c)(6) |
| 1 | Industrial Safety, Lockout/Tagout & Risk Assessment | `rob201-industrial-safety-and-lockout-tagout` | (c)(5) |
| 2 | Professional Standards & Industry Certifications | `rob201-professional-standards-and-certifications` | (c)(1) |
| 3 | Leading a Robotics Project Team | `rob201-leading-a-robotics-project-team` | (c)(3) |

Quiz: **Advanced Systems, Safety & Teams Quiz** — `rob201-quiz-advanced-systems-safety-teams`

### Unit 2 (order 1) — Math & Physics: Torque, Gear Ratio, Stability & Payload
(c)(2) mathematical processes, (c)(7) advanced mathematics and physics

| # | Lesson | `content_key` | Strand |
|---|---|---|---|
| 0 | Torque & Rotational Motion | `rob201-torque-and-rotational-motion` | (c)(7) |
| 1 | Gear Ratios, Speed & Mechanical Advantage | `rob201-gear-ratios-and-mechanical-advantage` | (c)(2), (c)(7) |
| 2 | Center of Mass, Stability & Tipping | `rob201-center-of-mass-and-stability` | (c)(7) |
| 3 | Payload, Load Calculations & Safety Factors | `rob201-payload-and-load-calculations` | (c)(2) |

Quiz: **Math & Physics of Motion Quiz** — `rob201-quiz-math-and-physics-of-motion`

### Unit 3 (order 2) — Manipulators, End Effectors & Arm Construction
(c)(9) manipulators/accumulators/end effectors, (c)(11) tools, equipment and materials

| # | Lesson | `content_key` | Strand |
|---|---|---|---|
| 0 | Robot Arm Anatomy & Degrees of Freedom | `rob201-robot-arm-anatomy-and-degrees-of-freedom` | (c)(9) |
| 1 | End Effectors: Grippers, Suction & Tooling | `rob201-end-effectors-grippers-and-tooling` | (c)(9) |
| 2 | Actuators & Accumulators: Pneumatics vs Hydraulics | `rob201-actuators-and-accumulators` | (c)(9), (c)(11) |
| 3 | Building an Arm: Workspace, Reach & Materials | `rob201-arm-construction-workspace-and-reach` | (c)(11) |

Quiz: **Manipulators & End Effectors Quiz** — `rob201-quiz-manipulators-and-end-effectors`

### Unit 4 (order 3) — Programming Robots in Python
(c)(8) creates a program to control a robotic or automated system

| # | Lesson | `content_key` | Strand |
|---|---|---|---|
| 0 | Python Fundamentals for Robots | `rob201-python-fundamentals-for-robots` | (c)(8) |
| 1 | Loops, Conditionals & Functions in Robot Code | `rob201-loops-conditionals-and-functions` | (c)(8) |
| 2 | Reading Sensors in Python | `rob201-reading-sensors-in-python` | (c)(8) |
| 3 | Closed-Loop Control & Tuning in Code | `rob201-closed-loop-control-and-tuning` | (c)(8) |

Quiz: **Programming Robots in Python Quiz** — `rob201-quiz-programming-robots-in-python`

### Unit 5 (order 4) — Artificial Intelligence & Autonomous Systems
(c)(6) technological systems, (c)(8) programming — advanced

| # | Lesson | `content_key` | Strand |
|---|---|---|---|
| 0 | What Artificial Intelligence Means in Robotics | `rob201-what-ai-means-in-robotics` | (c)(6) |
| 1 | Machine Learning Basics: Training vs Programming | `rob201-machine-learning-basics-for-robots` | (c)(8) |
| 2 | Computer Vision & Perception | `rob201-computer-vision-and-perception` | (c)(6) |
| 3 | Autonomous Navigation & Path Planning | `rob201-autonomous-navigation-and-path-planning` | (c)(8) |

Quiz: **Artificial Intelligence & Autonomous Systems Quiz** — `rob201-quiz-ai-and-autonomous-systems`

### Unit 6 (order 5) — Design, Project Management & Production Capstone
(c)(4) project management, (c)(10) engineering design methodologies, (c)(12) product production

| # | Lesson | `content_key` | Strand |
|---|---|---|---|
| 0 | The Design Process for a Real Client | `rob201-design-process-for-a-real-client` | (c)(10) |
| 1 | Scheduling, Budget & Bill of Materials | `rob201-scheduling-budget-and-bill-of-materials` | (c)(4) |
| 2 | Prototyping, Tolerance & Quality Control | `rob201-prototyping-tolerance-and-quality-control` | (c)(12) |
| 3 | Capstone: Build, Test & Present | `rob201-capstone-build-test-and-present` | (c)(10), (c)(12) |

Quiz: **Design, Project Management & Production Quiz** — `rob201-quiz-design-project-management-capstone`

**Strand coverage check** — all 12 appear: (c)(1) U1L2 · (c)(2) U2L1,L3 ·
(c)(3) U1L3 · (c)(4) U6L1 · (c)(5) U1L1 · (c)(6) U1L0, U5L0, U5L2 ·
(c)(7) U2L0,L1,L2 · (c)(8) U4 all four, U5L1, U5L3 · (c)(9) U3L0,L1,L2 ·
(c)(10) U6L0,L3 · (c)(11) U3L2,L3 · (c)(12) U6L2,L3.

---

## Backend tasks

### A. Clear the stale local stub (do this FIRST)

- [x] Delete the local-Docker `ROB201` course rows before writing anything else.
      They are leftovers from the pre-phase-58 `seed_data.create_robotics_course()`
      (removed in `dbc220d`): a `Course(code='ROB201', title='Robotics
      Engineering')`, a `CourseGradingConfig(60/40)`, three units at orders
      **1/2/3** and three keyless "Understanding X" lessons that write the
      dormant `Lesson.content` field. **Prod never had ROB201** — this is local
      only. Verify with
      `docker compose exec backend python manage.py shell -c "from courses.models import Course; print(Course.objects.filter(code='ROB201').values('id','title'))"`,
      then delete.
      **Why first:** `Course.code` is `unique=True`, so
      `get_or_create(code='ROB201')` would silently **adopt** that row — dragging
      in its 60/40 grading config and its 1-based units — and its three lessons
      carry a NULL/`auto:` `content_key`, which `is_adoptable()` returns True
      for, so they would be adopted at position rather than replaced.

### B. The command skeleton

- [x] Create `backend/courses/management/commands/populate_robotics_2_course.py`,
      modeled **end-to-end on `populate_robotics_course.py`** — it is the
      canonical pattern and the only seed carrying all the phase-55/58/65 fixes.
      Do **not** model on `populate_java_course.py` (its `_get_instructor`
      silently no-ops on failure and it has no choice rotation) and do not model
      on `seed_data.py` (1-based orders, writes the dormant `Lesson.content`).
      The skeleton must reproduce, exactly:
      - `add_arguments` exposing `--prune` (`action='store_true'`).
      - `handle` initializing `self.seen_lesson_keys` / `self.seen_quiz_keys`
        **before** any content work.
      - Instructor lookup **outside** `transaction.atomic()`; all content work
        **inside** it.
      - `_get_instructor()` filtering on `is_instructor=True` and raising
        `CommandError` when absent — the ROB101 version, not JAVA101's.
      - Local `_lesson` / `_quiz` wrappers that raise `ValueError` on a key
        reused within one run and record the key in the seen set. Unit builders
        must never call `upsert_lesson` / `upsert_quiz` directly.
      - `_report_stale(course, prune=options['prune'])` as the last step inside
        the transaction.
      - `_stable_choice_order` / `_rotate_choices` copied verbatim, applied to
        both lesson questions and quiz questions.
- [x] `_get_or_update_course`: `get_or_create(code='ROB201', defaults={'title':
      'Robotics 2', 'description': ..., 'instructor': ...})`, then re-assign
      those three fields on the not-created path. Touch **nothing else** — not
      `is_active`, not `enrollment_code`, not `join_code` (leave it NULL), and
      create no `CourseGradingConfig`. Description is one prose paragraph, no
      markdown headings (the course card renders it as plain text).
- [x] `_create_course_content` calling `_create_unit1` … `_create_unit6` in
      order, then the section/question helper trio (`_create_sections`,
      `_create_lesson_questions`, `_create_quiz_questions`) delegating to the
      `_content_upsert` helpers.

### C. Unit content builders — `[P]` (six independent builders, once B exists)

Each is `_create_unitN(self, course)` plus `_create_unitN_quiz(self, unit)`,
authored per the blueprint above. They touch different regions of one new file;
if dispatched in parallel, have each subagent produce its two methods as a
self-contained block for assembly, and give each the same authoring rules:

- [x] `_create_unit1` + `_create_unit1_quiz` — Advanced Systems, Safety & Teams `[P]`
- [x] `_create_unit2` + `_create_unit2_quiz` — Math & Physics `[P]`
- [x] `_create_unit3` + `_create_unit3_quiz` — Manipulators & End Effectors `[P]`
- [x] `_create_unit4` + `_create_unit4_quiz` — Programming Robots in Python `[P]`
- [x] `_create_unit5` + `_create_unit5_quiz` — AI & Autonomous Systems `[P]`
- [x] `_create_unit6` + `_create_unit6_quiz` — Design, PM & Production Capstone `[P]`

**Authoring rules every builder must follow:**
- Units use **0-based `order`** (0–5), matching ROB101. `Unit` is
  `unique_together ('course','order')`.
- Content goes in `LessonSection.content` as **GitHub-flavored Markdown ONLY**.
  Never write `Lesson.content`, `Lesson.video_type` or `Lesson.video_id` — they
  are dormant and pinned empty by test.
- All sections `video_type='none'`, `video_id=''`. Never set `layout`, `image`
  or `image_alt`.
- Author the **correct choice first** in every question, then let
  `_rotate_choices` place it. Do not hand-shuffle.
- Exactly **4 choices, exactly 1 correct** on every lesson question and every
  quiz question. Exactly **4 lesson questions per lesson**, **6 questions per
  unit quiz**.
- Python appears in fenced ```python blocks inside section content. Keep it
  simulator-runnable and kit-free; VEXcode VR / Tinkercad are the named tools.
- Every lesson's "Overview" section ends with a
  `> **TEKS alignment:** §127.750(c)(N) — ...` blockquote.
- Quiz titles are uniform: `<Unit topic> Quiz`, with **no** `Unit N Quiz:`
  prefix on any of the six. (ROB101 is inconsistent here — unit 1 has the prefix
  and the other five do not. Do not copy that inconsistency.)
- **Length caps that hard-fail a seed:** `Course.code` 10, all `title` fields
  200, `content_key` 100, `Choice.text` and `LessonQuestionChoice.text` **500**.
  Question text is unbounded.
- **`content_key` is permanent.** Use the blueprint's keys verbatim. The XP
  ledger dedupes on the key, so changing one later re-awards its XP to everyone
  who already completed that content. Keys are globally unique across all
  courses — `_assert_same_course` raises if a `rob101-*` key is copy-pasted in.

### D. Tests — `[P]` with C, after B exists

- [x] Register the command in the parametrized `COMMANDS` list at
      `backend/courses/test_populate_courses.py:25-28` as
      `('populate_robotics_2_course', 'ROB201', 6, 24, 6)`. That single line
      buys the shared seed-shape, key-prefix (`rob201-`), no-`auto:`-key,
      key-uniqueness, `requires_quiz`-invariant and idempotency assertions.
      **Correction (adversarial pass):** it does NOT buy adoption, `--prune` or
      the instructor guard — `TestAdoption`, `TestPruneFlag` and
      `TestInstructorGuard` hardcode `populate_robotics_course` rather than
      reading `COMMANDS`. Those were covered separately; see Outcomes. `[P]`
- [x] New `class TestPopulateRobotics2Course` in `backend/courses/tests.py`,
      mirroring `TestPopulateRoboticsCourse` (`tests.py:4223`):
      command runs clean; running twice is idempotent (unit/lesson/section/
      question counts stable, course pk stable, enrollment survives); 6 units
      each with exactly 1 unit quiz; every lesson has exactly 4 questions with
      4 choices and exactly 1 correct; every lesson with questions has
      `requires_quiz=True`; no lesson has non-empty dormant `content`/`video_id`;
      every section is `video_type='none'`; course code is `ROB201` and title
      `Robotics 2`; no `CourseGradingConfig` is created. `[P]`
- [x] `test_all_twelve_teks_strands_cited` — each of `§127.750(c)(1)` through
      `(c)(12)` appears in at least one section's content. **Use the `(?!\d)`
      negative lookahead** as `test_all_eleven_teks_strands_cited`
      (`tests.py:4381`) does, or `(c)(1)` will be falsely satisfied by `(c)(10)`,
      `(c)(11)` and `(c)(12)`. `[P]`
- [x] `test_correct_answers_are_not_all_at_position_zero` — assert the correct
      choice's `order` takes more than one distinct value across ROB201's
      questions. This is the defect phase 58 found by click-through; pin it in
      code this time so ROB201 cannot regress to JAVA101's state. `[P]`
- [x] Tighten the existing `test_seed_data_no_longer_creates_rob201`
      (`tests.py:4460-4463`). Its assertion `not Course.objects.filter(
      code='ROB201').exists()` was unambiguous when ROB201 was nobody's course;
      now that ROB201 is legitimate, make the test assert that **`seed_data`
      specifically** does not create it — e.g. snapshot the ROB201 queryset
      before and after `call_command('seed_data')` — so it cannot pass for the
      wrong reason. `[P]`
- [x] `makemigrations --check` produces nothing. If a migration appears, **stop**
      — this phase is content-only and mis-scoped.

---

## Frontend tasks

- [x] **None.** Course pages, quest map, lesson player, quiz player and the
      instructor editor are all content-generic (proven by phase 58). Zero
      `frontend/` files should change. `tsc`, `lint` and `vitest` still gate the
      phase.

---

## Verification

Local, in order:

- [x] `/verify-stack` PASS — full backend suite including the new tests, `tsc` 0
      errors, `eslint` clean (the one known warning is acceptable), `vitest`
      green. Baseline entering the phase: pytest **1106**, tsc 0, lint 0 (+1
      known), vitest **154**.
- [x] `docker compose exec backend python manage.py makemigrations --check
      --dry-run` → no changes.
- [x] `docker compose exec backend python manage.py populate_robotics_2_course`
      **twice**. Second run reports "refreshed", the course pk is unchanged, and
      the counts are identical both runs: **6 units / 24 lessons / ~104–120
      sections / 96 lesson questions / 6 quizzes / 36 quiz questions**. Record
      the exact section count in the Outcomes section.
- [x] Run it a third time with `--prune` and confirm it reports (and deletes)
      nothing — a clean blueprint has no stale content.
- [x] Confirm `Course.objects.filter(code='ROB201').count() == 1` and that no
      `CourseGradingConfig` exists for it.
- [x] Confirm ROB101 and JAVA101 are untouched: their unit/lesson/quiz counts
      and course pks are the same before and after seeding ROB201.

Manual click-through (local, browser automation; accounts `instructor@demo.com`
and `student1@demo.com`, both `LocalDev123!`):

- [x] Instructor sees the full ROB201 outline in `ManageCoursePage` — 6 units,
      24 lessons, 6 unit quizzes, titles correct.
- [x] Student enrolls in ROB201. **Note: enrollment is invite-gated as of phase
      68** — issue a `CourseInvite` for `student1@demo.com` on ROB201 first, or
      the enrollment code alone will 403.
- [x] Quest map at `/courses/ROB201/map` renders 30 nodes (24 lessons + 6 boss
      quizzes) with 6 boss nodes.
- [x] Open unit 4 lesson 0 (`rob201-python-fundamentals-for-robots`): all
      sections render, the ```python fences highlight as code, tables render as
      tables, and the TEKS blockquote renders as a blockquote.
- [x] Answer that lesson's 4 comprehension questions to mastery, then confirm
      the lesson can be completed (the `requires_quiz` gate releases) and XP is
      awarded once.
- [x] Attempt and pass the Unit 4 boss quiz; confirm 20 points and that a second
      pass awards no additional XP.
- [x] **Spot-check answer distribution by eye** across several questions — the
      correct answer must not always be the first option. This is what phase 58
      caught only at click-through.

Production (owner steps, after merge — merging `main` deploys the backend):

- [x] **Backup branch taken before seeding (2026-08-06)** — see Prerequisites.
      `protected: true` is still outstanding and is tracked there.
- [x] **ROB201 SEEDED INTO PRODUCTION (2026-08-06).** Run from the backend
      container against the Neon **direct (non-pooler)** endpoint
      `ep-falling-frog-avzgk4ed.c-11.us-east-1.aws.neon.tech`, **without
      `--prune`**:
      `docker compose exec -T -e DATABASE_URL=<neon direct> backend python
      manage.py populate_robotics_2_course`
      Full output — no stale-content warnings, because the course was created
      fresh and there was nothing to prune:
      ```
      Populating ROB201 course...
      Found instructor: cesarvillarreal11@gmail.com
      Course: ROB201 - Robotics 2 (created)
      Created 6 units with lessons and quizzes
      ROB201 population complete (non-destructive).
      ```
      Post-seed counts straight from prod match the blueprint exactly:
      **6 units / 24 lessons / 120 sections / 96 comprehension questions /
      6 unit quizzes / 36 quiz questions.**
      `_get_instructor` resolved deterministically — prod holds exactly one
      `Cesar Villarreal` with `is_instructor=true` (user id 1), so the
      duplicate-namesake finding carried from the adversarial pass could not
      bite here.
- [x] **`/courses/ROB201` verified as a real content read (2026-08-06),**
      signed in as the instructor on stemquests.com. The six-unit outline
      renders in order (Advanced Systems/Safety/Teams → Math & Physics →
      Manipulators → Python → AI & Autonomous Systems → Design & Capstone), all
      24 lessons listed, all six `<topic> Quiz` titles at 6 questions / 20 pts.
      Lesson `/courses/ROB201/learn/89` opens in the player with its sections,
      the comprehension-quiz gate and the 20-pt unit quiz. Course list shows
      ROB201 **above** ROB101, as `Meta.ordering = ['-created_at']` predicted.
- [x] **Deploy verified (2026-08-04, merge `863597c`).** The `/courses/ROB201`
      half of this check is deferred with the seed — the course does not exist
      in prod yet — but everything the deploy itself could break was checked:
      an authenticated `DEMO101/units/` read returned **200 with 5 units** and
      populated `lesson_count`/`is_locked`; `/api/health/?deep=1` returns
      `{"status": "ok", "database": "ok", "content": "ok"}` with the verbatim
      keyword intact; UptimeRobot monitor `803564235` **UP**, 13d 4h unbroken.
- [x] **ROB101 and JAVA101 intact after the deploy** — DEMO101 5/20,
      JAVA101 5/20, ROB101 6/24 units/lessons, unchanged.
- [x] **Re-confirmed intact after the seed (2026-08-06).** DEMO101 5 units /
      20 lessons / 74 sections / 85 comprehension questions / 5 quizzes /
      25 quiz questions; JAVA101 identical; ROB101 6 / 24 / 116 / 96 / 6 / 36 —
      every figure unchanged from before the seed. `/courses/ROB101` also loads
      its full outline in the browser, including the known inconsistent
      `Unit 1 Quiz:` title prefix. `/api/health/?deep=1` →
      `{"status": "ok", "database": "ok", "content": "ok"}`; UptimeRobot monitor
      `803564235` **UP**, 16d 3h unbroken.
- [x] **Migrations confirmed done before merging.** 45 local migration files
      against 45 rows in prod's `django_migrations` for our six apps
      (accounts 3, courses 26, discussions 1, gamification 6, notifications 5,
      quizzes 4). This PR added none, so the Render pre-deploy `migrate` was a
      no-op.

---

## Notes for the implementer

- Backend changes need `docker compose restart backend` to take effect.
- **`pytest` is not on the host PATH** — run it as
  `docker compose exec -T backend pytest`.
- **Push to `lms`, not `origin`.** `origin` is the retired repo and accepts the
  push silently.
- **Expect no migration.** Every change is a new management command plus tests.
- The single highest-risk mistake in this phase is a **`content_key` collision or
  a copy-pasted `rob101-` key**. `_assert_same_course` will raise on a
  cross-course reuse and the `_lesson`/`_quiz` wrappers raise on an in-run reuse,
  so both fail loudly — but only if the builders go through the wrappers. Never
  call `upsert_lesson` / `upsert_quiz` directly from a unit builder.
- The second highest-risk mistake is **seeding on top of the local stub**. Do
  task A before task B, not after.
- XP is not authored anywhere. It is flat constants in
  `backend/gamification/services.py:24-26` (`XP_LESSON = 50`, `XP_QUIZ = 20`,
  `XP_LESSON_QUIZ = 20`), so ROB201 is worth 24×50 + 24×20 + 6×20 = **1,800 XP**,
  the same as ROB101. `Quiz.points=20` is the gradebook value, not XP.
- `LessonQuestion.clean()` requires exactly one correct choice but is **not**
  called on the seed path — nothing will stop a blueprint with zero or two
  correct choices. The tests in D are the only guard.
- Never seed an empty quiz: `start_quiz_session` and `submit_quiz` return 400
  for a quiz with no questions.
- `seed_data.clear_data()` truncates **every** course including ROB101/JAVA101.
  It is gated behind `--clear` and must never be pointed at prod.
- Reference reading, in order: `docs/archive/specs/phase-58-robotics-1-course.md`
  (the ROB101 phase this one mirrors), `backend/courses/management/commands/
  populate_robotics_course.py` (the pattern), `_content_upsert.py` (the upsert
  contract and the `content_key` rules), `docs/specs/phase-65-xp-content-identity.md`
  (why keys are permanent).

---

## Outcomes

**Shipped as specified.** No deviation from the blueprint: all 24 lesson keys,
6 quiz keys, 6 unit titles and every order matches the tables above byte-for-byte.

### Final counts

`6 units / 24 lessons / **120 sections** / 96 lesson questions / 6 quizzes /
36 quiz questions.` Sections came out a uniform **5 per lesson** (the spec
allowed 4–5), so the test pins `== 120` rather than a floor. ROB201 is worth
1,800 XP, same as ROB101.

### Verification recorded

- `/verify-stack` **PASS** — pytest **1133** (baseline 1106, +27), tsc **0
  errors**, eslint **0 errors** (+1 known `react-refresh` warning in
  `ErrorBoundary.tsx`), vitest **154** / 19 files unchanged. Re-run in full
  after the late content edit below; still 1133.
- `makemigrations --check --dry-run` → **No changes detected**. Content-only, as
  scoped.
- Seeded three times: run 2 reported "refreshed" with every count identical, the
  course pk stable (19) and all 24 lesson + 6 quiz pks unmoved; run 3 with
  `--prune` reported and deleted nothing.
- ROB101, JAVA101 and DEMO101 snapshots byte-identical before and after seeding.
- Zero `frontend/` files changed.

### Task A — the stub was deleted, not adopted

The local stub was real and would have been adopted: `Course(code='ROB201',
'Robotics Engineering')` with a `CourseGradingConfig`, three units at orders
**1/2/3** and three `auto:`-keyed lessons that `is_adoptable()` accepts. Deleted
15 rows. ROB201 is now pk **19** against ROB101's pk **10**, which is the proof
the new course was created rather than grafted onto the stub. Its grading config
read 62.50/37.50 in the local DB, not the 60/40 the retired `seed_data` code
wrote — the row had drifted at some point. Immaterial either way; it is gone.

### Click-through (local, browser automation)

All spec steps passed. Instructor outline shows 6 units / 24 lessons / 6 unit
quizzes at "6 questions · 20 pts". Student was invited, enrolled through the
phase-68 invite gate with the enrollment code, and the quest map rendered
**0/30** (24 lessons + 6 boss nodes). Unit 4 lesson 0 rendered its Python fences
with syntax highlighting, its tables as tables, and the TEKS blockquote as a
blockquote. Mastered 4/4 comprehension questions → the `requires_quiz` gate
released → lesson completed (50 XP) + mastery (20 XP). Unit 4 boss quiz passed
**100%, 20.00 points**; a second `award_quiz_pass` added **0 XP**, confirming the
ledger dedupes on `content_key` and not the pk.

### One content change made during the click-through

Markdown tables originally used inline-code backticks in their cells. Tailwind
Typography injects a literal `` ` `` via `content: '"`"'` before and after every
`<code>`, so those cells rendered cluttered. Stripped the backticks from all 14
affected table rows, matching ROB101 (which has zero backticks in tables).
**This is styling, not a bug, and it is platform-wide** — ROB101 (56 inline code
spans) and JAVA101 (250) render the same way in production today. Inline code in
*prose* was left alone for consistency with them; changing it is a frontend/CSS
decision and out of scope here. Reseeded after the edit; counts and pks unmoved.

### Review pass

One `code-reviewer` pass over the full diff: **no BROKEN findings.** It
independently re-derived every calculation in units 2, 3 and 6 (torque, gear
ratios, compound trains, efficiency, centre of mass, tipping angle, payload,
factor of safety, cantilever deflection, tolerance stack, BOM margin, critical
path) and confirmed not only the marked-correct answers but that every
distractor computes to the mistake it represents. It parsed all **48** embedded
Python snippets and traced every output claimed in the surrounding prose. Five
NITs raised; four fixed on the branch:

- Snapshot in `test_seed_data_no_longer_creates_rob201` was vacuous (`before`
  was provably always empty) → rewritten to state the one thing it actually
  guarantees, with the seeded case left to its companion test.
- `test_join_code_is_left_unset` only covered the create path → now seeds a live
  `join_code` and re-runs, pinning the case that would actually hurt.
- Section count was a floor → pinned at `== 120`.
- A docstring cited the stub's grading weights inaccurately → number dropped.
- The fifth NIT was the un-ticked spec checklist, now done.

Answer-position distribution after rotation: **27/21/26/22** across lesson
questions and **11/12/9/4** across quiz questions — the defect phase 58 caught
only by eye, and the one JAVA101 still carries, is pinned in code here.

### Adversarial pass

One `adversarial-tester` pass, 20 hand-written probes: **no BROKEN findings in
the command.** It confirmed the whole student-progress stack survives a reseed
(`LessonProgress`, `LessonQuestionAnswer` including `selected_choice_id` and
`is_correct`, `QuizAttempt`, `LessonQuizAttempt`, XP), that choice pks are
updated in place so the `SET_NULL`-rewrites-an-answer-to-incorrect hazard never
fires, that `content_key` uniqueness is enforced at the DB and not just in the
app, that a cross-course key collision aborts with **no partial ROB201 left**,
that `Unit.is_locked` survives, and that forced failures at both the first and
last statement inside the transaction roll back whole.

It also found a **real gap in this spec's own claim** (corrected above):
registering in `COMMANDS` does not buy adoption, `--prune` or instructor-guard
coverage, because those three test classes hardcode `populate_robotics_course`.
Before the fix, none of them had ever run against ROB201. Closed by:

- Adding `populate_robotics_2_course` to the three `TestDuplicateKeyWithinOneSeedRun`
  parametrize lists (they were already course-agnostic).
- Six new ROB201 tests promoted from the probes: `auto:`-key adoption, adoption
  not re-awarding XP, the default run warning without deleting, `--prune`
  deleting the stray while leaving all 24 blueprint lessons, a cross-course key
  collision aborting the whole seed, and a row holding a *different* authored
  key never being re-keyed.

Test count after: pytest **1139**, `test_populate_courses.py` **39** (was 36).

**Deferred, SUSPICIOUS, not introduced by this phase** — all inherited from the
shared `_content_upsert.py` pattern already live for ROB101 and JAVA101:

1. **A reseed silently reverts an instructor's unit reorder.** `upsert_unit`
   matches on `(course, order)` and stamps the blueprint title onto whatever
   unit sits there, while `upsert_lesson` drags each lesson's FK back to the
   blueprint's unit. No data is lost — lesson pks and everything keyed off them
   are untouched — but the reorder undoes itself with no warning. The spec
   deliberately protects `is_locked` and `join_code` from exactly this class of
   clobbering and says nothing about ordering. Worth a decision in a later phase.
2. **`--prune` cascades student progress for instructor-authored content** with
   only a stdout warning and no confirmation prompt. Documented behaviour, but a
   live footgun. Now at least pinned by a test.
3. **`_get_instructor` uses `.filter(...).first()` with no `order_by`**, so two
   active instructors with the same name resolve non-deterministically, and an
   `is_active=False` instructor can still be assigned course ownership. Same in
   ROB101/JAVA101; low risk in a single-instructor deployment.

### Deliberately not done

`clone_course_for_demo` stays hardcoded to JAVA101, so ROB201 is not in the demo
sandbox. `Course.Meta.ordering` is untouched, so **ROB201 sorts above ROB101** in
every course list — confirmed in the click-through, accepted as cosmetic. The
JAVA101 answer-rotation reseed remains carried.
