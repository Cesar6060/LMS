# Handoff: Phase 58 — ROB101 Robotics 1 course

## Current state
Phase 58 implemented end-to-end on `feat/phase-58-robotics-course`;
**PR #76 open on Cesar6060/LMS, awaiting user merge**. Delivered:
- `backend/courses/management/commands/populate_robotics_course.py` —
  idempotent, atomic, seeds 6 units / 24 lessons / 116 sections /
  96 lesson questions / 6 boss quizzes (70%/20pts/3 attempts); all 11
  TEKS §127.749 strands cited; unit content written by 6 parallel
  subagents, assembled from fragments.
- ROB201 stub removed from `seed_data.py`.
- 15 tests in `backend/courses/tests.py` (TestPopulateRoboticsCourse).
Verified: `/verify-stack` PASS — 631 backend tests, tsc 0, eslint 0.
Seed run twice locally (counts stable, pk stable). Browser click-through
done (instructor outline, student enroll via code, quest map 30 nodes,
lesson 1 + comprehension 4/4, Unit 1 boss quiz 6/6). Review agents ran:
code-reviewer APPROVE WITH NITS (nits fixed), adversarial-tester's
3 BROKEN fixed (atomic rebuild, is_instructor filter, CommandError).

## In progress / not done
- **PR #76 merge** — user decision; no migrations, deploy is code-only.
- **Post-merge prod seed (user-run)**: `DATABASE_URL=<neon> python
  manage.py populate_robotics_course` from dev machine, then check
  /courses/ROB101 on stemquests.com. First-time-only once students
  enroll — re-runs clear ROB101 progress/attempts (spec note added).
- Stray branch `feat/phase-58-robotics-course` pushed to old repo
  `origin` (dev-learning-platform) by mistake before remote check;
  deletion was permission-blocked. Harmless; user may delete.

## Next steps
1. User: merge PR #76, then run the prod seed above and click through
   ROB101 on stemquests.com as instructor.
2. Deferred finding worth a future phase item: XP double-award across
   content rebuilds (`XPEvent.source_id` is a bare int keyed on
   lesson/quiz PKs; JAVA101 identical). Needs gamification schema work.
3. JAVA101 has the same "correct answer always option 1" seeding defect
   ROB101 just fixed — re-seeding prod JAVA101 would fix it but touches
   a live course; user's call.
4. Phase 59: Django 4.2 → 5.2 LTS (slipped from 58).
5. Still open from earlier phases: school-device login test (phase 57),
   normal-student regression click-through (phase 56), Sentry LoginPage
   TypeError on /login.

## Decisions made
- Six unit builders written by parallel subagents as class-body
  fragments, cat-assembled into one file — matches populate_java_course
  single-file shape and the spec's "grep the command" verification.
- Choice rotation done at seed time (deterministic md5 of question
  text), not frontend shuffle — no UI change, idempotency preserved.
- XP double-award deferred: proper fix needs a migration; spec declares
  this phase migration-free and says stop if one appears.
- Blueprint's 24 enumerated lessons beat the spec's "~20 lessons /
  ~26 nodes" estimates; actual map is 30 nodes.

## Gotchas discovered
- `/finish-phase` and `/handoff` skills have disable-model-invocation;
  execute their SKILL.md steps manually when user asks for them.
- `origin` is the retired repo and still accepts pushes — always push
  to `lms` (Cesar6060/LMS); local main tracks `lms`.
- First "Start Check" click on the lesson comprehension quiz returned a
  transient "Failed to start quiz session"; retry succeeded (200). Not
  reproduced; watch for it in the phase-56 regression pass.
- Local dev DB still shows an old ROB201 course row from a pre-phase
  seed; stub removal only stops future seeding. Prod never had ROB201.

## Files to read first
1. docs/specs/phase-58-robotics-1-course.md — checklist + evidence.
2. backend/courses/management/commands/populate_robotics_course.py —
   helpers at the tail (lines ~4700+); content above.
3. backend/courses/tests.py — TestPopulateRoboticsCourse (end of file).
4. docs/handoffs/2026-07-28-phase-57-cutover-executed.md — carried items.
