# Phase 28 — Catalog re-scoping + Java course conversion (ADR-018)

## Goal
Execute ADR-018 (Computer Science + Robotics catalog), and — per user direction
this session — make the flagship seeded course a **Java** intro-programming course
instead of C#, focused **solely on the principles of computer science** (no game
design/game-dev framing). The existing `populate_csharp_course.py` course "Video
Game Development - C# Fundamentals" is rewritten so every code example, quiz, and
explanation teaches **Java** using **neutral, general computer-science examples**
(bank balances, temperatures, counters, user data — not `playerHealth`/game
scenarios). Around that core rewrite, the phase also does the small copy
re-scopes ADR-018 called for: the frontend create-course placeholder, the README
tagline, and the `seed_data.py` demo course framing. Per the resolved open
question, **no `subject`/`category` field is added** — with one CS course and no
Robotics content yet, a taxonomy + filter UI is premature; add it later when
there are enough courses to filter.

## Decisions locked this session (2026-07-19)
- **Phase 28 = the Java conversion.** The C#→Java rewrite is the heart of the
  phase; the small copy re-scopes fold into it (one cohesive "Java-based intro
  CS course" phase).
- **No subject field.** Course model unchanged; no migration; catalog keeps its
  existing client-side free-text search. (ADR-018 open question → deferred.)
- **Course code stays `VGD101`.** It's an internal unique key referenced by
  `tests.py` fixtures; renaming is churn for no user benefit (same rationale as
  ADR-017 leaving `gamedev_db`). Cosmetically odd but low-risk. Course *title*
  changes; *code* does not.
- **Neutral CS examples — no game framing (updated 2026-07-19).** The course
  focuses **solely on the principles of computer science**. Replace game-themed
  example variables/scenarios (`playerHealth`, `enemyDistance`, `GameManager`,
  score, "build a console game") with neutral, general-purpose examples: bank
  balances, temperatures, counters, user names/ages, shopping totals, etc. Drop
  **all** game-dev framing — no "game-dev track" identity, no Unity/Minecraft/game
  hooks. This **supersedes** the earlier "keep game-themed examples" decision.
- **Language pivot supersedes** the earlier "title + description only / keep all
  examples" answers, which assumed the course stayed C#. Full content conversion
  is in scope for `populate_csharp_course.py`.
- **Remove the 18 embedded C# YouTube video sections (updated 2026-07-19).** Every
  lesson's "Video: … in C#" `LessonSection` (Bro Code C# tutorials) is deleted
  during conversion — a C# video in a Java course is wrong content. The text
  lessons, code examples, and quizzes fully cover each topic. Java videos can be
  curated back in as a later content pass. Do NOT keep C# video IDs.

## As-built deltas (implemented 2026-07-19 — supersede the tasks below where they conflict)
Mid-implementation the user redirected the delivery. Final state actually shipped:
- **New additive course `JAVA101`, not an in-place `VGD101` overwrite.** The Java
  course is created as its own course (code **`JAVA101`**, "Introduction to
  Programming with Java") so it appears in the app alongside existing courses
  without a destructive reset. (The "keep VGD101 code" decision no longer applies.)
- **Command renamed + made non-destructive:**
  `populate_csharp_course.py` → **`populate_java_course.py`**. The old destructive
  steps (delete all non-instructor users, recreate 5 test students, wipe VGD101)
  were **removed**. It now only creates/idempotently-refreshes `JAVA101` and its
  content — no user changes, no other course touched. All the Java curriculum
  content lives in this one file.
- **Old Godot `VGD101` course deleted** from the dev DB (user: "no reason to keep
  the video game design course"). `seed_data.py`'s demo course was retitled
  "Game Programming with Godot" in code but is not seeded in the current DB.
- Everything else below (neutral Java content, 18 videos removed, no `subject`
  field, README/frontend/tests copy) shipped as written.

## Out of scope (do NOT touch)
- **No `subject`/`category`/`track` model field**, no migration, no `django-filter`,
  no catalog filter UI. Deferred (resolved open question).
- **Course code `VGD101`** — unchanged everywhere (model seed, `tests.py`
  fixtures L42/L114/L150). Do not rename.
- **Full GDScript→Java rewrite of `seed_data.py`.** `seed_data.py` is a dev/demo
  fixture; only its *course framing copy* is re-scoped (see Backend task 2),
  NOT a language conversion of its Godot content.
- **Infra identifiers** left by ADR-017: `gamedev_db`, `gamedev_user`,
  `gamedev_platform` module/docstrings, `gamedev-platform-frontend` package name,
  `*-gaming` CSS theme classes (they name a visual aesthetic, not subject matter).
- **App branding** — already "STEM Quest" (Header, index.html, README H1). Not this phase.
- **No new course content beyond converting the existing units.** Do not add new
  lessons/units; no Robotics content (separate future work).
- Gamification (Phase 30), authoring efficiency (Phase 29), analytics (Phase 31),
  redesign (Phase 33) — all later phases.

## Course structure being converted (`populate_csharp_course.py`, 3251 lines)
Manual command `python manage.py populate_csharp_course`. **Not invoked by any
test or migration** — so pytest is unaffected by content changes. Units:

| Unit | Title | Lessons | Unit quiz |
|---|---|---|---|
| 1 (order 0) | **Getting Started** | Hello World; Comments; Code Organization – Brackets & Blocks; Naming Conventions | "Script Structure Quiz" (L649) |
| 2 (order 1) | **Variables & Operators** | Number Types – int/float/double; Text and Boolean Types; Arithmetic Operators; Assignment Operators | "Variables & Operators Quiz" (L1007) |
| 3 (order 2) | **Strings & User Input** | String Interpolation; String Methods; User Input | "Working with Text Quiz" (L1662) |
| 4 (order 3) | **Control Flow** | Comparison Operators; If Statements; Switch Statements; While Loops; For Loops; Nested Loops; ForEach Loops | "Control Flow Quiz" (L2155) |
| 5 (order 4) | **Methods & Functions** | Built-in Methods; Creating Your Own Methods | "Methods Quiz" (L3184) |

Each lesson has `content` (markdown), `LessonSection` slides, and comprehension
`LessonQuestion`s; each unit has a `Quiz`. **All of these hold hardcoded C#
strings** that must be converted.

## C# → Java translation reference (apply throughout)
The implementer must apply these consistently. This is the correctness core of
the phase.

| Concept | C# (current) | Java (target) |
|---|---|---|
| Print line | `Console.WriteLine("Score: " + score)` | `System.out.println("Score: " + score)` |
| Print no newline | `Console.Write(...)` | `System.out.print(...)` |
| Read input | `Console.ReadLine()` | `Scanner` → `new Scanner(System.in).nextLine()` (add `import java.util.Scanner;`) |
| Parse int | `int.Parse(s)` / `Convert.ToInt32` | `Integer.parseInt(s)` |
| String interpolation | `$"HP: {playerHealth}"` | **no Java equivalent** → `"HP: " + playerHealth`, or `String.format("HP: %d", playerHealth)` / `System.out.printf` |
| String type | `string name` | `String name` |
| Boolean type | `bool alive` | `boolean alive` |
| Entry point | `static void Main()` | `public static void main(String[] args)` |
| Imports/usings | `using System;` | `import java.util.Scanner;` (only where needed) |
| for-each | `foreach (var x in items)` | `for (int x : items)` (enhanced for) |
| Method naming | PascalCase `PrintScore()` | **camelCase** `printScore()` |
| Class naming | PascalCase (same) | PascalCase (same) |
| Constants | `const int MAX` | `static final int MAX` / `UPPER_SNAKE_CASE` convention |
| Built-in string ops | `.ToUpper()`, `.Length`, `.Substring()` | `.toUpperCase()`, `.length()`, `.substring()` |
| Math | `Math.Max`, `Math.Abs` | `Math.max`, `Math.abs` |
| Comments | `//`, `/* */` | same (no change) |

**Content that needs genuine rewriting, not mechanical swap:**
- **"Introduction to C#" intro** (L185, L189): drop "pronounced C-sharp / created
  by Microsoft / Unity" framing. Replace with neutral Java framing — e.g. Java is
  one of the world's most widely used languages, runs on billions of devices
  (from Android phones to enterprise servers) via the JVM, and is a common first
  language for learning computer science. Replace the "Game Development" bullet
  with a neutral application area (e.g. Android apps, web/enterprise back-ends,
  data processing). **No game framing.**
- **"Naming Conventions" lesson** (Unit 1, L530): C# teaches PascalCase methods;
  **Java uses camelCase for methods/variables**, PascalCase for classes,
  UPPER_SNAKE for constants. This lesson must teach Java conventions, not a swap.
- **"String Interpolation" lesson** (Unit 3, L1265): Java has no string
  interpolation. Rewrite to teach **concatenation + `String.format`/`printf`**;
  retitle the lesson (e.g. "Formatting Text" or "Combining Strings").
- **"User Input" lesson** (Unit 3, L1450): rewrite around `Scanner` (import,
  `nextLine`/`nextInt`), replacing `Console.ReadLine`.
- **Unit quizzes**: every question/answer referencing `Console.WriteLine`,
  `Main`, `string`, `bool`, `$"..."`, `foreach`, etc. must be updated to the
  Java equivalent. Rename "Script Structure Quiz" → e.g. "Program Structure Quiz".

## Proposed course copy (review/adjust on sign-off)
- **Title:** `Introduction to Programming with Java`
- **Description:** `Learn the fundamental principles of computer science in Java —
  variables, data types, operators, conditionals, loops, and methods. A hands-on
  introductory course where you write and run real code from day one.`

(Pure CS framing; no games; drops C#/Unity. Implementer may refine wording.)

## Backend tasks
- [x] **1. Convert `backend/courses/management/commands/populate_csharp_course.py`
  to Java.** Work unit-by-unit (1→5). For each unit: convert every lesson
  `content`, every `LessonSection`, every `LessonQuestion` + choices, and the
  unit `Quiz` questions/answers using the translation reference above.
  - [x] Course title → "Introduction to Programming with Java"; description → Java framing (keep `code='VGD101'`).
  - [x] Unit 1 "Getting Started": Hello World (`System.out.println` + `public static void main`), Comments, Brackets & Blocks, **Naming Conventions (Java camelCase rewrite)**, "Script Structure Quiz" → Java program-structure quiz.
  - [x] Unit 2 "Variables & Operators": Number Types (Java int/double/float, `f` suffix), Text and Boolean Types (`String`/`boolean`), Arithmetic + Assignment Operators, unit quiz.
  - [x] Unit 3 "Strings & User Input": **String Interpolation → String formatting** (concat + `String.format`/`printf`, retitle), String Methods (`.toUpperCase()`/`.length()`), **User Input via `Scanner`**, unit quiz.
  - [x] Unit 4 "Control Flow": Comparison Operators, If, Switch, While, For, Nested, **ForEach → enhanced for-each**, unit quiz.
  - [x] Unit 5 "Methods & Functions": Built-in Methods (Java equivalents), Creating Your Own Methods (camelCase), unit quiz.
  - [x] Update the command's docstring (L2) and `help` text (L20) to say "Java" (internal, but keep consistent).
  - [x] **Replace game-themed example variables/scenarios** (`playerHealth`, `enemyDistance`, `GameManager`, score, "console game") **with neutral CS examples** (bank balance, temperature, counter, user age/name, shopping total). No game framing anywhere in lesson content, sections, or quizzes.
- [x] **2. Re-scope `backend/courses/management/commands/seed_data.py` course
  framing (copy only, no language conversion — low priority, dev fixture).** Its
  `code='VGD101'` demo course is Godot/GDScript game content. Reframe the
  **title + description** to drop the "Video Game Development" subject-branding so
  the demo no longer presents video-game development as the platform's subject.
  The fixture content is inherently Godot, so a fully game-neutral rewrite is out
  of scope; either retitle honestly (e.g. "Game Programming with Godot", clearly a
  demo variety course) **or** leave the fixture untouched if a clean game-neutral
  title isn't achievable without a content rewrite. **Leave the GDScript
  lesson/quiz content as-is**, and leave `CS101` "Principles of Computer Science"
  and `ROB201` "Robotics Engineering" demo courses untouched.
- [x] **3. (Optional, low priority) `backend/courses/tests.py`** — the fixtures at
  L43 `'Intro to Game Development'`, L44, L78 `'Advanced Game Dev'` are internal
  test data (not user-facing). Updating them to neutral CS titles is cosmetic;
  do it only if trivially quick. **Do NOT change the `VGD101` code strings**
  (L42/L114/L150) — tests assert on them.
- [x] **No model / migration / serializer / endpoint changes** (no subject field).

## Frontend tasks
- [x] **1. `frontend/src/pages/instructor/CreateCoursePage.tsx:88`** — placeholder
  `"e.g., Introduction to Game Development"` → a neutral CS example, e.g.
  `"e.g., Introduction to Programming with Java"` (or `"e.g., Introduction to Computer Science"`).
- [x] **No type/service/form changes** — no subject field is added, so
  `types/index.ts`, `services/courses.ts`, `CourseSettingsDialog.tsx`,
  `CoursesPage.tsx` are untouched.

## Docs / repo tasks
- [x] **`README.md:3`** — tagline `...built for video game development education...`
  → CS framing, e.g. `...built for Computer Science education, featuring...`.
  (Leave the `gamedev-platform/` directory label in the ASCII tree — internal.)

## Verification
`/verify-stack` first, then the content-specific checks (pytest will NOT catch
content errors — the manual command run + grep sweep are the real safety net).

- [x] **pytest** — 196 passed (baseline unchanged; the populate command isn't
  exercised by tests, and `VGD101` fixtures are preserved). If any count changes,
  investigate before proceeding.
- [x] **tsc** `npx tsc --noEmit` — 0 errors (placeholder edit is a string only).
- [x] **lint** `npm run lint` — 0 errors, ~23 warnings (baseline).
- [x] **Populate command runs clean** — against a scratch/dev DB:
  `docker compose exec -T backend python manage.py populate_csharp_course`
  completes without error and creates the course + all 5 units/lessons/quizzes.
  (Recommended: run after each unit's conversion while implementing, not just at the end.)
- [x] **C#-artifact grep sweep** — after conversion,
  `grep -nE "Console\.(Write|Read)|using System|\bstring \b|\bbool \b|\\$\"|foreach|int\.Parse|Convert\.To|static void Main" backend/courses/management/commands/populate_csharp_course.py`
  returns **nothing** (all C# idioms converted). Spot-check that no PascalCase
  method names remain in example code.
- [x] **Copy sweep** —
  `grep -rniE "video game|game dev|C# Fundamentals|playerHealth|enemyDistance|GameManager" backend/courses/management/commands/populate_csharp_course.py frontend/src README.md`
  returns nothing (the `populate_csharp_course.py` *filename* is acceptable; the
  course *title*/*description*/lesson copy and all example variables must be game-free).
  Also spot-check the file for lingering "game"/"player"/"enemy"/"score" wording.
- [ ] **Manual click-through (hand to user — no browser automation in agent env):**
  1. Run the populate command, open the course in the app — title reads
     **"Introduction to Programming with Java"**.
  2. Open Unit 1 → Hello World: code shows `System.out.println` and
     `public static void main`, not C#.
  3. Spot-check one lesson per unit (esp. Naming Conventions = camelCase, String
     formatting, User Input = Scanner, ForEach = enhanced for) — Java, correct, renders cleanly.
  4. Take one unit quiz — questions/answers are about Java, and a correct Java
     answer scores correctly.
  5. Create-course form placeholder shows the new CS example, not "Game Development".

## Notes
- **Base branch:** cut Phase 28 from `lms/main` **after PR #15 (Phase 27) merges**.
  If #15 is still open when starting, branch from the merged main once it lands
  (don't stack on the phase-27 branch).
- This is a large, error-prone content rewrite in one 3251-line file. Converting
  **unit-by-unit with a populate-command run after each** is strongly recommended
  over a single big-bang edit. Consider parallelizing the per-unit conversions if
  using subagents during implementation.
- Keep commits conventional; a content rewrite is `feat:` (new Java curriculum).
  Split the `docs:` handoff/spec-checklist commit per repo convention.
- After implementing: `/verify-stack`, `/handoff`, then open a PR into `Cesar6060/LMS:main`.
- `PLAN.md` + `CLAUDE.md` are gitignored — don't expect them in the diff.
