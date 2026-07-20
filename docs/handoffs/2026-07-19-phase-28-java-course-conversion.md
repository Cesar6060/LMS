# Handoff: Phase 28 — Java course conversion + catalog re-scope (ADR-018)

## Current state
Phase 28 **implemented + verified, NOT yet committed** on branch
`feat/phase-28-java-course-conversion` (cut from merged `lms/main`).
- **Course fully converted C# → Java** with neutral CS examples (no games) in
  `backend/courses/management/commands/populate_java_course.py` (git-renamed from
  `populate_csharp_course.py`; ~3200 lines). 5 units / 20 lessons / 74 sections /
  85 comprehension questions / 5 unit quizzes. All 18 embedded C# videos removed.
  Command made **non-destructive** (no user deletion; only creates/refreshes JAVA101).
- Copy re-scopes: `frontend/src/pages/instructor/CreateCoursePage.tsx` placeholder,
  `README.md` tagline (→ Computer Science), `backend/courses/management/commands/seed_data.py`
  (demo course → "Game Programming with Godot"), `backend/courses/tests.py` fixture titles.
- Spec: `docs/specs/phase-28-java-course-conversion.md` (has "As-built deltas" section).
- **DB now shows** JAVA101 (5u/20L), CS101, ROB201; old Godot VGD101 deleted; 7 users intact.
- **Verified:** pytest **196 passed**; tsc **0 errors**; lint **0 err / 23 warn**;
  `populate_java_course` runs clean; C#-artifact + game-term greps clean.

## In progress / not done
- **Nothing committed yet.** No PR opened.
- **Manual click-through unchecked** (only unchecked spec item) — needs the user in-app.

## Next steps
1. Commit: `feat:` for `populate_java_course.py` (rename+rewrite) + frontend/seed/tests/README;
   separate `docs:` for the spec + this handoff. No Co-Authored-By; conventional format.
2. Open PR into `Cesar6060/LMS:main` (remote `lms`).
3. User does the manual click-through: log in as instructor (`instructor@demo.com`),
   open JAVA101, spot-check Hello World (Java), Naming Conventions (camelCase),
   Formatting Text, User Input (Scanner), For-Each; take a unit quiz.
4. Next phase per PLAN.md Part 9: **Phase 29 — authoring efficiency** (top functional priority).

## Decisions made
- **New additive course JAVA101, not in-place VGD101 overwrite** (user redirect): lets it
  show in the app without a destructive reset. Command made non-destructive + renamed.
- **No games / neutral CS examples** (user: "focus solely on principles of computer science").
- **18 C# videos removed** (user choice) — C# videos wrong in a Java course; text lessons cover all.
- **No `subject` field** (ADR-018 open question → deferred; premature with 1 course).
- Course code is now `JAVA101`; old Godot VGD101 deleted (user: "no reason to keep it").

## Gotchas discovered
- `head` shadowed in this shell (HTTP tool); `--include=*.py` fails under zsh globbing — use plain grep.
- `python` not on host PATH — use `python3`, or `docker compose exec -T backend python ...`.
- `populate_java_course` is a **manual** command — NOT run by any test/migration, so pytest
  can't catch content errors. Real safety net = running it + grep sweeps + click-through.
- Converted unit-by-unit via sequential subagents (concurrent edits to one file risk lost-update races).

## Files to read first
- `docs/specs/phase-28-java-course-conversion.md` (esp. "As-built deltas").
- `backend/courses/management/commands/populate_java_course.py` (the course).
- `PLAN.md` Part 9 (Phase 29 row) — gitignored, on disk.
