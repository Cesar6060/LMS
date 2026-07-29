# Phase 58 — Robotics 1 course (ROB101), TEKS-aligned

> Ordering note: phase 58 was previously earmarked for the Django 4.2 → 5.2
> upgrade; that slips to phase 59. Phase 57 is ON HOLD pending only the
> user-performed school-device login test (see its spec).

## Goal

Ship a complete, student-ready **ROB101 "Robotics 1"** course seeded by an
idempotent management command, with full lesson content aligned to the Texas
TEKS for Robotics I (19 TAC §127.749, one credit, recommended grades 9–10,
STEM CTE cluster). Content is **platform-agnostic** (no hardware kit assumed)
and uses free simulators (VEXcode VR, Tinkercad Circuits) for hands-on
exercises. Six thematic units group the 11 TEKS knowledge-and-skills strands;
every lesson notes the strand(s) it covers. Each unit ends with a unit quiz
(boss node on the quest map); lessons with comprehension questions get the
phase-54 `requires_quiz` gate. The obsolete `ROB201` dev stub in
`seed_data.py` is retired.

## Out of scope

- Hardware-specific tracks (VEX/Arduino/LEGO variants) — content mentions
  platforms only as examples.
- YouTube video curation — all sections seed with `video_type='none'`; the
  instructor adds videos later via the lesson editor. No hardcoded video IDs.
- Exposing ROB101 in the demo sandbox (DEMO101 stays the only demo course).
- Course catalog/taxonomy UI (ADR-018 explicitly deferred this).
- Robotics II / Principles of Applied Engineering prerequisites.
- Django 4.2 → 5.2 upgrade (now phase 59).
- Running the seed command against production Neon — documented as a
  post-merge step for the user, never run by an unattended session.

## Course structure (content blueprint)

Six units; TEKS strand citations in parentheses. ~20 lessons total; each
lesson = 2–5 markdown `LessonSection`s + 2–4 `LessonQuestion`s (with
`requires_quiz=True` via the helper invariant); each unit = one
`quizzes.Quiz` with 4–6 questions, `passing_score=70`, `points=20`.

1. **Robots, Careers & Teamwork** — (c)(1) employability, (c)(2) careers,
   (c)(3) teamwork. Lessons: What Is a Robot? (systems, components);
   Careers in Robotics (technician vs technologist vs engineer, ABET,
   certifications, ethics); Working on a Robotics Team (roles, leadership,
   communication).
2. **Safety, Tools & Project Management** — (c)(5) safety, (c)(10) tools,
   (c)(4) project management. Lessons: Shop & Electrical Safety (OSHA,
   hazard classes, storage); Tools & Precision Measurement; Managing a
   Robotics Project (phases, scheduling, Gantt basics).
3. **Mechanisms & the Physics of Motion** — (c)(7) physics, (c)(8)
   manipulators/end effectors. Lessons: Newton's Laws for Robots; Simple
   Machines & Mechanical Advantage; Gears, Torque & Speed; Motors (DC vs
   servo); Arms, Linkages & End Effectors (payload, stability).
4. **Sensors, Systems & Feedback** — (c)(6) technological systems. Lessons:
   Robot Subsystems (power, drive, control); Sensors (touch, distance,
   light, encoders); Open- vs Closed-Loop Control (feedback); Simulation
   exercise: sensor-driven behavior in VEXcode VR.
5. **Programming Robots** — (c)(6)(A) computer control, supports (c)(10)(C)
   software application. Lessons: Programs, Algorithms & Pseudocode;
   Sequencing, Loops & Conditionals for Robots; Sensor-Driven Decisions;
   Simulation project: maze navigation in VEXcode VR.
6. **Engineering Design Capstone** — (c)(9) design methodology, (c)(11)
   product development. Lessons: The Engineering Design Process; Defining
   Problems & Constraints; Documentation & Schematics (engineering
   notebook); Prototype, Test, Iterate; Presenting Your Design.

## Backend tasks

- [x] `backend/courses/management/commands/populate_robotics_course.py`
      modeled on `populate_java_course.py`: `get_or_create(code='ROB101')`,
      instructor lookup (Cesar Villarreal), `_clear_course_content()` then
      rebuild; reuse the `_create_sections` / `_create_lesson_questions` /
      `_create_quiz_questions` helper pattern (the lesson-questions helper
      must set `requires_quiz=True` — phase-55 invariant). Content goes in
      `LessonSection.content` (GFM markdown) ONLY — never the dormant
      `Lesson.content` field. All sections `video_type='none'`. Idempotent;
      touches nothing outside ROB101.
- [x] Unit content builders `_create_unit1` … `_create_unit6` per the
      blueprint above, each with its unit quiz. `[P]` per unit once the
      command skeleton + helpers exist (six independent builders).
- [x] Remove `create_robotics_course()` / `ROB201` stub from
      `backend/courses/management/commands/seed_data.py` (it writes to the
      dormant `Lesson.content` field). Keep the rest of seed_data intact. `[P]`
- [x] Tests in `backend/courses/tests.py` (new class, mirroring the JAVA101
      populate tests): command runs clean; running twice is idempotent
      (unit/lesson/section/question counts stable, course pk stable,
      enrollment survives); 6 units each with ≥1 unit quiz; every lesson
      with questions has `requires_quiz=True` and every lesson without has
      `False`; no lesson has non-empty dormant `content`/`video_id`; code
      is `ROB101`; ROB201 no longer created by seed_data. `[P]` with the
      seed_data cleanup, after the command exists.
- [x] No new migrations expected (content only, no schema). If any migration
      appears, stop — the phase is mis-scoped. (Confirmed: no migrations
      created; content-only change.)

## Frontend tasks

- [x] None — course pages, quest map, lesson player, quizzes, and instructor
      editor are all content-generic. `tsc`/lint still gate the phase.

## Verification

- [x] `/verify-stack` PASS (full backend suite incl. new populate tests;
      tsc 0 errors; eslint clean). 627 backend tests passed (+9 new);
      tsc 0 errors; eslint exit 0.
- [x] `docker compose exec backend python manage.py populate_robotics_course`
      twice locally → second run reports idempotent update, counts unchanged.
      (Run 2: "refreshed", pk stable, 6 units / 24 lessons / 116 sections /
      96 lesson questions / 6 quizzes / 36 quiz questions both runs.)
- [x] Manual click-through (local): instructor sees ROB101 outline in
      ManageCoursePage; student account enrolls via code, quest map at
      `/courses/ROB101/map` renders ~26 nodes with 6 boss nodes, complete
      lesson 1 (sections render markdown correctly), answer its lesson
      questions, then attempt the Unit 1 boss quiz. (Done via browser
      automation with local demo accounts: outline showed all 6 units /
      24 lessons / 6 unit quizzes; student1 enrolled via code; map header
      0/30 nodes (blueprint yields 24 lessons, not ~20, so 30 nodes);
      lesson 1 markdown + TEKS blockquote rendered; comprehension check
      mastered 4/4; Unit 1 boss quiz passed 6/6, 20 pts. Found + fixed:
      every correct choice was seeded at position 0 and the player does
      not shuffle — command now rotates choices deterministically.)
- [x] Spot-check TEKS coverage: each of the 11 strands (c)(1)–(c)(11)
      appears in at least one lesson's content (grep the command for
      "§127.749" citations). All 11 strands cited (29 citations total);
      also pinned by test_all_eleven_teks_strands_cited.
- [ ] Post-merge, user-run: seed production
      (`DATABASE_URL=<neon> python manage.py populate_robotics_course` from
      a dev machine), then verify `/courses/ROB101` on stemquests.com as
      the instructor.

## Carried / related open items (not this phase's work)

- Phase 57: school-device login test (user; phase on hold until done).
- Phase 56: normal-student regression click-through (user).
- Dependabot #65/#67/#68 deferred (TS 7, Django 6, React 19).
- Sentry TypeError "reading 'LoginPage'" on /login — investigate some phase.
