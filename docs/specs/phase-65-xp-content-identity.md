# Phase 65 — XP content identity

## Goal

Close the oldest open correctness bug in the codebase (carried since phase 58): a course
content rebuild re-awards XP that students already earned. `XPEvent` dedupes on
`(user, source_type, source_id)` where `source_id` is a **bare database primary key**
with no foreign key and no cascade, while `populate_robotics_course` and
`populate_java_course` begin every run with `course.units.all().delete()` (and
`clone_course_for_demo` does the same on every refresh). That cascade destroys the
Lessons and Quizzes *and* every student's `LessonProgress`, `QuizAttempt`,
`LessonQuizAttempt`, `AttemptAnswer`, `LessonQuestionAnswer` and
`LessonAttemptAnswer` rows, while leaving the `XPEvent` rows orphaned and their XP
still summed into the denormalized `GameProfile.total_xp`.
The student then redoes the rebuilt lesson on a **new** primary key and is paid
again — permanently inflating XP, level, streak freezes and XP-threshold badges.
This phase fixes both halves: content gets a **stable author-chosen key** that XP
dedupes on instead of the PK, and the seed commands become genuinely
non-destructive upserts so a rebuild no longer wipes student work at all. It also
ships a read-only `audit_xp` command so the damage already done to prod can be
measured before anyone decides to touch a student's XP.

Scale: **44 lessons and 11 quizzes** need authored keys (ROB101 has 24 + 6,
JAVA101 has 20 + 5), across two seed files totalling 8,000 lines — but both already
funnel every child row through three shared private helpers, so the per-unit diff
is one `key=` argument per lesson and per quiz.

## Out of scope

- **No frontend work.** Nothing in the API surfaces `XPEvent`, `source_id` or a
  content key — `profile_payload` returns totals and badges only. `tsc`, `lint` and
  `vitest` must still pass, but zero `frontend/` files should change. If a frontend
  change appears necessary, stop and flag it.
- **No repair of existing prod XP.** The audit command reports; it never writes.
  Deciding what to do about inflated totals is a follow-up, informed by the report.
- **XP never decreases.** No cascade delete of `XPEvent`, no recompute of `total_xp`
  from the ledger, no revocation. Deleting content never takes XP, a level, a streak
  freeze, an avatar unlock or a badge away from a student who already earned it.
- **`XPEvent.source_id` is not dropped.** It stays, dormant, as the audit trail of
  which PK originally paid. The column drop is a later change of its own.
- **No new `unique_together` constraints on `Quiz`, `quizzes.Question`,
  `quizzes.Choice` or `LessonQuestion`.** They have none today, so prod may hold
  duplicate `(parent, order)` rows; adding constraints could fail the migration
  against unknown data. The upsert helpers are defensive instead. Adding the
  constraints is a follow-up once `audit_xp` proves the data is clean.
- **No change to XP values, the leveling formula, badge criteria, or the streak
  freeze rules** beyond the one deliberate streak fix in "Adjacent fixes".
- **No retroactive rewrite of `XPEvent.amount`.** The audit reports amount drift;
  correcting it would silently change student totals and needs its own decision.
- **Does not fix carried remainders**: `THROTTLE_SLIDE_IMPORT` ceiling, phase-61
  real-deck slide-import smoke test, JAVA101 answer-rotation reseed, phase-56
  regression click-through, Sentry LoginPage TypeError, the four open Dependabot
  majors (#68 react-dom, #86 eslint 10, #87 vite 8, #88 tailwind 4). All still open.

---

## Design decisions (settled in the interview — do not relitigate)

1. **Both halves get fixed.** Stable content key *and* non-destructive seeding. The
   key makes the XP ledger immune to any delete-and-recreate (including an
   instructor deleting a lesson in the UI); the seed rewrite stops the rebuild
   destroying student progress in the first place. Neither alone is sufficient:
   a key does not save `LessonProgress`, and a non-destructive seed does not help
   when content is deleted through some other path.

2. **The key is author-chosen, not positional and not random.** Every seeded lesson
   and quiz carries an explicit hand-written slug in the seed source
   (`rob101-what-is-a-robot`). Positional keys (`ROB101:1:2`) were rejected: a
   reorder would re-key every lesson below the insertion point, and swapping two
   lessons would silently transfer one student's XP to a different lesson. Random
   UUIDs were rejected: they do not survive a genuine delete-and-recreate, so they
   would add schema without adding the guarantee.

3. **Non-seeded content gets an automatic key.** `content_key` defaults to a
   callable returning `auto:<uuid4 hex>`, so every creation path that exists
   today — the instructor lesson/quiz endpoints, tests, fixtures — keeps working
   with **zero code changes** and still gets a unique, stable key. The `auto:`
   prefix is also what makes adoption (decision 5) safe to detect.
   **This default is load-bearing, not a convenience.** There is no `conftest.py`,
   no factory_boy and no fixture directory in this backend: content is built by
   ~30 module-local pytest fixtures and roughly 120 inline `Lesson.objects.create`
   / `Quiz.objects.create` calls spread across seven test modules. A `NOT NULL`
   key with no default would break every one of them. With the default, none change.

4. **XP never decreases** (see Out of scope). Orphaned `XPEvent` rows are kept and
   labelled, not deleted. This matches how `UserBadge` and `longest_streak` already
   behave: an earned thing is permanent.

5. **Existing prod content is adopted by position, then stamped.** A seed run that
   finds a lesson at `(unit.order, lesson.order)` whose `content_key` is missing or
   `auto:`-prefixed writes the blueprint key onto it. From then on the match is by
   key. No separate manual prod step, no course content hardcoded into a migration.
   A lesson whose key is already a non-`auto:` blueprint key is **never** re-keyed
   by position — that would undo decision 2.

6. **Seeds prune only behind `--prune`.** A default run creates and updates, warns
   about content in the DB that is not in the blueprint, and deletes nothing.
   `--prune` opts into the deletion, which still cascades student progress for the
   removed lesson — that is the point of making it explicit.

7. **The upsert goes all the way down.** Sections, lesson questions, quiz questions
   and choices upsert on `(parent, order)`, so the three student-owned tables that
   CASCADE off a question survive a reseed: `quizzes.AttemptAnswer`
   (`quizzes/models.py:102`), `LessonQuestionAnswer` (`courses/models.py:432`) and
   `LessonAttemptAnswer` (`courses/models.py:530`). Upserting a choice in place also
   avoids the `SET_NULL` path on `selected_choice`, which matters because
   `LessonQuestionAnswer.save()` (`courses/models.py:455-461`) recomputes
   `is_correct` from the choice — a NULLed choice silently rewrites a student's
   answer to *incorrect*. Accepted tradeoff: children are keyed *positionally*, so
   reordering questions in the blueprint re-associates historical answers.
   Acceptable — they carry no XP, the reorder is rare and deliberate, and giving
   every choice a slug is not worth it.

8. **The migration must be old-code-safe.** Migrations are hand-applied to Neon
   *before* the new code deploys (see `CLAUDE.md` and the phase-64 `db_default`
   finding). Therefore `content_key` and `XPEvent.source_key` land **nullable**:
   Postgres allows many NULLs under a unique index, so old code that inserts
   without the column keeps working through the whole deploy window.

---

## The identity model

```python
# courses/models.py, quizzes/models.py
def generate_content_key():
    return f'auto:{uuid.uuid4().hex}'

content_key = models.CharField(
    max_length=100, unique=True, null=True, blank=True,
    default=generate_content_key,
    help_text='Stable identity across content rebuilds. Seeded content uses an '
              'author-chosen slug; anything else gets auto:<uuid>.',
)
```

Key namespaces, all globally unique in one flat space:

| Prefix / shape | Meaning | Set by |
|---|---|---|
| `rob101-what-is-a-robot` | authored blueprint content | the seed source |
| `demo:java101-hello-world` | a `clone_course_for_demo` copy | the clone command |
| `auto:<uuid4hex>` | instructor-created, test-created, unadopted | the model default |
| `orphan:lesson:41` | an `XPEvent` whose source PK no longer exists | the backfill |

`XPEvent` gains `source_key = CharField(max_length=100, null=True, blank=True)` and
`unique_together ['user', 'source_type', 'source_key']`, **added alongside** the
existing `['user', 'source_type', 'source_id']`. Both write, the key is what dedupes.

Blueprint slug convention: `<course code lowercased>-<topic slug>`. **No unit or
lesson number in the key** — a lesson must be able to move between units without
becoming new content. Quizzes use `<course>-quiz-<unit topic>`.

---

## Backend tasks

### Schema (three migrations, all additive and nullable)

- [ ] `courses/models.py`: add `generate_content_key()` and `Lesson.content_key`
      as specified above. Docstring note: this is the XP identity, changing it
      re-awards XP.
- [ ] `quizzes/models.py`: add `Quiz.content_key` (import the same helper from
      `courses.models` — one definition, not two).
- [ ] `courses/migrations/0024_*`: **three operations in order** — `AddField`
      `content_key` as `null=True, blank=True` with **no** unique and **no**
      default; `RunPython` stamping `auto:<uuid4hex>` on every existing row
      (forward) with a no-op reverse; `AlterField` to add `unique=True` and the
      `default=generate_content_key`. A single `AddField` with a callable default
      would evaluate the callable **once** and violate uniqueness on the second row.
- [ ] `quizzes/migrations/0004_*`: same three-step shape for `Quiz`.
- [ ] `gamification/models.py`: add `XPEvent.source_key`; add the new
      `unique_together`; extend the class docstring to say the **key**, not the id,
      is the correctness core now, and mark `source_id` DORMANT (kept as the audit
      trail of which PK paid; see the phase-53 `Lesson.content` precedent).
- [ ] `gamification/migrations/0006_*`: `AddField` `source_key` nullable +
      `AlterUniqueTogether`, plus a `RunPython` that backfills every existing row:
      resolve `source_id` → `Lesson.content_key` (for `lesson` / `lesson_quiz`) or
      `Quiz.content_key` (for `quiz`); when the row no longer exists write
      `orphan:{source_type}:{source_id}`. Must `dependencies` on the courses and
      quizzes migrations above so the keys exist when it runs. Reverse is a no-op.
- [ ] `makemigrations --check` clean at the end.

### Shared upsert helpers — `courses/management/commands/_content_upsert.py`

A leading underscore keeps Django from registering it as a command. Every helper is
pure DB work with no stdout, returns the object, and is safe to call repeatedly.

- [ ] `upsert_unit(course, order, title) -> Unit` — `update_or_create` on
      `(course, order)` (already `unique_together`).
- [ ] `upsert_lesson(unit, key, order, **fields) -> Lesson` — implements decision 5:
      match on `content_key=key` first; if absent, adopt the row at
      `(unit, order)` **only when** its key is null or `auto:`-prefixed, and stamp
      `key` onto it; otherwise create. Never re-keys a row that already holds a
      different non-`auto:` key.
- [ ] `upsert_quiz(unit, key, order, **fields) -> Quiz` — same adoption rule.
      `Quiz` has no `(unit, order)` uniqueness, so the positional lookup takes the
      lowest-pk match and logs a warning if there is more than one.
- [ ] `upsert_sections(lesson, sections_data)` — `update_or_create` on
      `(lesson, order)`; deletes only sections whose `order` is beyond the end of
      `sections_data`. Must call `section.image.delete(save=False)` before deleting
      a section that has an image, matching the existing rule in
      `clone_course_for_demo.py:86-89` — otherwise every reseed orphans R2 blobs.
- [ ] `upsert_lesson_questions(lesson, questions_data)` and
      `upsert_quiz_questions(quiz, questions_data)` — `update_or_create` on
      `(parent, order)` for the question, then on `(question, order)` for each
      choice; trailing extras deleted. Defensive against pre-existing duplicates:
      take the lowest pk, delete the rest, warn.
- [ ] `prune_stale(course, seen_lesson_keys, seen_quiz_keys, *, dry_run)` — returns
      the lessons/quizzes/units in `course` that the run did not touch. `dry_run`
      (the default) only reports; otherwise deletes.
- [ ] Every helper is exercised by its own test (see below) — this module is where
      the real risk lives, not in the 8,000 lines of prose it is called from.

### Seed command rewrites

The two big seeders already funnel all child creation through three private methods
(`_create_sections`, `_create_lesson_questions`, `_create_quiz_questions`), so the
per-unit diff is small: add a `key=` argument to each `Lesson.objects.create` /
`Quiz.objects.create` and let the helpers do the rest.

- [ ] `populate_robotics_course.py`: delete `_clear_course_content`; add
      `add_arguments` with `--prune`; rewrite `_create_sections` /
      `_create_lesson_questions` / `_create_quiz_questions` to delegate to
      `_content_upsert`; collect the keys each unit touched and call
      `prune_stale` at the end. Fix the module docstring, which currently claims
      the command is "NON-DESTRUCTIVE" while destroying every student's progress
      in ROB101 — that claim becomes true in this phase.
- [ ] `[P]` `_create_unit1` + `_create_unit1_quiz` — author keys for its 4 lessons
      and 1 quiz, switch to `upsert_*`.
- [ ] `[P]` `_create_unit2` + `_create_unit2_quiz` — same.
- [ ] `[P]` `_create_unit3` + `_create_unit3_quiz` — same.
- [ ] `[P]` `_create_unit4` + `_create_unit4_quiz` — same.
- [ ] `[P]` `_create_unit5` + `_create_unit5_quiz` — same.
- [ ] `[P]` `_create_unit6` + `_create_unit6_quiz` — same.
      (24 `Lesson.objects.create` + 6 `Quiz.objects.create` + 6
      `Unit.objects.create` across the six, one unit created per method.)
- [ ] `populate_java_course.py`: same treatment — drop `_clear_course_content`,
      add `--prune`, delegate the three child helpers. Also **wrap `handle` in
      `transaction.atomic()`** — robotics does (`:42-48`), java does not
      (`:34-39`), so a mid-run failure leaves JAVA101 half-rebuilt today. Its five
      `Unit.objects.create` calls all live in `_create_course_content`
      (`:93-117`), unlike robotics, so convert them there, not per unit.
- [ ] `[P]` JAVA101 unit 1 (`_create_unit1_getting_started_lessons`,
      `_create_unit1_quiz`).
- [ ] `[P]` JAVA101 unit 2 (`_create_unit2_variables_lessons`,
      `_create_unit2_operators_lessons`, `_create_unit2_quiz`).
- [ ] `[P]` JAVA101 unit 3 (`_create_unit3_text_lessons`, `_create_unit3_quiz`).
- [ ] `[P]` JAVA101 unit 4 (`_create_unit4_conditionals_lessons`,
      `_create_unit4_loops_lessons`, `_create_unit4_quiz`).
- [ ] `[P]` JAVA101 unit 5 (`_create_unit5_methods_lessons`, `_create_unit5_quiz`).
      (20 `Lesson.objects.create` + 5 `Quiz.objects.create` across the five.)
- [ ] `clone_course_for_demo.py`: `_clone()` copies **all concrete fields**, so it
      would copy the source's `content_key` verbatim and blow the unique index on
      the first run. Every clone must override the key with `demo:<source key>` —
      stable across re-clones, distinct from the source. Replace
      `demo.units.all().delete()` with the same upsert path, keyed on the
      `demo:`-prefixed keys, keeping the existing `section.image.delete(save=False)`
      blob cleanup for sections that actually go away.
- [ ] `seed_data.py`: `clear_data()` is already gated behind `--clear`, so leave the
      wipe alone — but note in its docstring that despite saying "demo data" it
      truncates **every** course in the database (`:77-92`). The real work here is
      giving its content deterministic `seed:`-prefixed keys at the ten
      `get_or_create` / `create` sites (`:232, :236, :259, :401, :475, :523, :531,
      :669, :686, :692`) so a re-run without `--clear` does not churn identities.
- [ ] `seed_demo_account.py` needs **no change** — it creates no content rows, only
      user-owned progress, and finds lessons by `unit.lessons.order_by('order')`.
      Confirm that rather than assuming it.

### Gamification service and backfill

- [ ] `services.py::_award_xp(user, source_type, source_key, amount, source_id=None)`
      — dedupe on `source_key`; keep writing `source_id` into the row. Update the
      docstring: the key is the guarantee, the id is history.
- [ ] `award_lesson_completion` / `award_quiz_pass` / `award_lesson_quiz_pass`:
      pass `obj.content_key` as the key and `obj.id` as `source_id`. The four view
      call sites (`courses/views.py:518`, `courses/views.py:2508`,
      `quizzes/views.py:274`, `quizzes/views.py:478`) already pass the model
      instance and need **no change** — verify that, do not edit them.
- [ ] A lesson or quiz with a null `content_key` (only possible mid-deploy) must not
      500: fall back to `f'legacy:{source_type}:{obj.id}'` rather than dedupe on None.
- [ ] `backfill_gamification.py`: it currently awards from bare id lists. Switch the
      three loops to fetch `content_key` alongside the id
      (`values_list('lesson__content_key', 'lesson_id')`) and pass both.

### Audit command — `gamification/management/commands/audit_xp.py`

Read-only. Never writes, never prompts, always exits 0.

- [ ] Orphan report: `XPEvent` rows whose source no longer exists — determined by
      checking `Lesson` / `Quiz` existence, **not** just the `orphan:` prefix, so the
      command is correct whether or not the backfill has run. Per-user count and XP
      total, plus a grand total.
- [ ] Ledger drift: per profile, `sum(XPEvent.amount)` vs `GameProfile.total_xp`.
      Report every profile where they differ, with the delta and the derived level
      at each figure — this is the number that says how inflated prod actually is.
- [ ] Amount drift: rows whose `amount` differs from the current `XP_LESSON` /
      `XP_QUIZ` / `XP_LESSON_QUIZ` constant for their `source_type` (the
      `get_or_create(defaults=...)` hazard — an existing row keeps its old amount
      forever and nothing reconciles it).
- [ ] Duplicate-content report: content keys held by more than one live row, and
      lessons/quizzes still on an `auto:` key inside ROB101/JAVA101 (i.e. adoption
      did not take).
- [ ] `--user <email>` to scope to one student; `--verbose` for per-row detail;
      default output is a summary table.

### Adjacent fixes

- [ ] **Streak no longer ticks on a no-op award.** `services.py:206-208` calls
      `_update_streak` whenever `advance_streak=True`, regardless of whether the
      `XPEvent` was created. Gate it on `created`. This is a **deliberate semantic
      change**: re-completing already-paid content no longer extends a streak. Today
      it is masked by the `_just_completed` flag in `courses/serializers.py:679`, so
      no current caller is affected — but it is one new caller away from live.
      Record it in the handoff as a behavior change, not just a bug fix.
- [ ] **Document the badge asymmetry.** `_badge_satisfied` reads live progress rows
      for `lessons_done`, `course_complete` and `perfect_quiz`, so deleting content
      retroactively un-satisfies them — while `UserBadge` rows are never revoked, so
      the badge sticks. That asymmetry is now *intentional* (decision 4). Say so in
      the `_badge_satisfied` / `_evaluate_badges` docstrings and pin it with a test.
- [ ] **Document the amount-drift hazard** in `_award_xp`'s docstring, pointing at
      `audit_xp` as the way to detect it. No automatic rewrite (Out of scope).

### Backend tests

- [ ] **The regression test this phase exists for** (`gamification/tests.py`, new
      `TestContentRebuildXP`): student completes a lesson (+50), the lesson is
      deleted and recreated with the **same `content_key`**, the student completes
      it again → `total_xp` is still 50 and exactly one `XPEvent` exists. Repeat for
      a unit quiz and a lesson comprehension quiz. Every existing "idempotent" test
      re-awards the *same, still-existing* object, which is precisely why this bug
      survived from phase 58 to 65.
- [ ] `[P]` A lesson recreated with a **different** key *does* award again — new
      content is genuinely new. Pins that the fix is not just "never award twice".
- [ ] `[P]` Deleting a lesson leaves its `XPEvent` and `total_xp` untouched
      (decision 4: XP never decreases).
- [ ] `[P]` `_award_xp` with a null `content_key` falls back to `legacy:` and does
      not 500 or dedupe on None.
- [ ] `[P]` Streak: a re-award of already-paid content does **not** advance the
      streak; a genuine new award still does.
- [ ] `[P]` Badge asymmetry pin: earn `lessons_done`, delete the lessons, badge is
      still held and is not re-awarded.
- [ ] `[P]` Backfill command still idempotent with keys, and skips instructors.
- [ ] **Upsert helper tests** (new `courses/test_content_upsert.py`) — one per
      helper: adoption of an unkeyed row by position; refusal to re-key a row that
      holds a different blueprint key; child upsert preserves the question pk and
      with it all three student-owned answer tables (`AttemptAnswer`,
      `LessonQuestionAnswer`, `LessonAttemptAnswer`); a choice whose text changes
      keeps its pk so `LessonQuestionAnswer.selected_choice` is not `SET_NULL`ed
      into a silently-wrong `is_correct=False`; trailing children deleted; section
      image blob deleted when its section goes; defensive handling of a
      pre-existing duplicate `(quiz, order)`.
- [ ] **Seed command tests** (new `courses/test_populate_courses.py`) — there is
      currently **no test coverage at all** for `populate_robotics_course` or
      `populate_java_course`, and this phase rewrites both:
  - running the command twice produces identical unit/lesson/quiz counts, and every
    `Lesson.pk` is unchanged between runs;
  - a student's `LessonProgress`, `QuizAttempt` and `LessonQuestionAnswer` survive a
    second run intact (the headline guarantee);
  - a student's XP is unchanged after a reseed + re-completion;
  - adoption: pre-create a lesson at the blueprint's position with an `auto:` key,
    run the seed, assert it was adopted (same pk) and stamped with the blueprint key;
  - `--prune` deletes blueprint-absent content and the default run does not, but
    does warn.
- [ ] `[P]` `clone_course_for_demo` test: re-clone twice, demo lesson pks stable,
      keys all `demo:`-prefixed, no unique-constraint error, no key collision with
      the source course. Extend the existing `courses/test_seed_demo_account.py`.
- [ ] `[P]` `audit_xp` tests: clean database reports zero of everything; a manually
      orphaned `XPEvent` is counted; a hand-edited `total_xp` shows as drift; an
      `XPEvent` with a stale `amount` shows as amount drift; the command writes
      nothing (assert row counts and `total_xp` unchanged after a run).
- [ ] `[P]` Catalog/permission regressions still green: the instructor-inert path,
      `core/tests/test_demo_lockdown.py`, and the phase-63 query-count guards on
      the profile endpoint.

---

## Frontend tasks

**None.** No type, service, component or page changes. `AvatarSlot`, the gamification
payloads and every API shape are untouched. The frontend checks below run to prove
this phase did not disturb them, not because anything should change.

---

## Verification

### Automated — `/verify-stack` must PASS
- [ ] `docker compose exec -T backend pytest` — baseline is **766 passed** (phase 64
      + aura retirement). Expect roughly +35. Named checks that must be green:
  - `gamification/tests.py::TestContentRebuildXP` — the delete-and-recreate no-double-award
    case for all three source types, plus the different-key-does-award counter-case.
  - `courses/test_populate_courses.py` — pk stability across two runs, student
    progress and XP survival, adoption of an `auto:`-keyed row, `--prune` behavior.
  - `courses/test_content_upsert.py` — every helper, including the `AttemptAnswer`
    survival case and the section-image blob cleanup.
  - the streak-not-ticked-on-noop test and the badge-asymmetry pin.
  - `core/tests/test_demo_lockdown.py` unchanged and still passing.
- [ ] `docker compose exec -T backend python manage.py makemigrations --check` clean.
- [ ] `docker compose exec -T backend python manage.py migrate --plan` shows exactly
      the three new migrations, in dependency order (courses and quizzes before
      gamification).
- [ ] `cd frontend && npx tsc --noEmit` → 0 errors, and `git diff --stat frontend/`
      is **empty**.
- [ ] `cd frontend && npm run lint` → 0 errors (1 pre-existing warning is baseline).
- [ ] `cd frontend && npx vitest run` → 116 passing, unchanged.

### Manual — against local Docker, before the PR
- [ ] `python manage.py populate_robotics_course` on a DB where `student1@demo.com`
      has ROB101 progress and XP. Record `total_xp`, completed-lesson count and a
      `LessonQuestionAnswer` count before; assert all three are identical after.
      This is the phase in one command.
- [ ] Run it a **second** time; confirm the output reports 0 created / N updated and
      no lesson pk moved.
- [ ] Complete a rebuilt lesson as `student1@demo.com` → **no** XP toast, `total_xp`
      unchanged. Complete a genuinely new lesson → +50 as normal.
- [ ] `python manage.py audit_xp` on the local DB → reports the orphans left behind
      by earlier destructive reseeds, and zero ledger drift for a profile that was
      never inflated.
- [ ] `python manage.py populate_java_course` and `clone_course_for_demo` both run
      clean twice in a row, and the demo course still opens on the site.

### Deploy — do NOT do this during implementation
- [ ] Three migrations must be hand-applied to Neon **before** the code deploys, in
      order: `courses.0024`, `quizzes.0004`, `gamification.0006`. All three are
      additive and nullable by design (decision 8), so the running old code is safe
      throughout the window — verify that claim by asserting an insert that omits
      the new columns still succeeds, the way phase 64 proved its `db_default`.
- [ ] After deploy, run `audit_xp` against prod and put the numbers in the handoff.
      That report is the input to a later decision about repairing inflated totals.
      **Do not repair anything in this phase.**
- [ ] Per `CLAUDE.md`: open the PR and stop. Never merge and never touch Neon from
      the implementation session.

---

## Notes for the implementation session

**This is a large phase.** Work it in this order, and treat each step as a commit
that leaves the suite green — the schema and service work is what actually fixes the
bug, and it is verifiable on its own before the 8,000-line seed rewrite starts:

1. Schema + migrations (three files).
2. Service + backfill switched to keys, plus `TestContentRebuildXP`. **The bug is
   fixed at the end of this step** — everything after is defence in depth.
3. `_content_upsert.py` and its tests.
4. The three delegating child helpers in both seed commands (sequential).
5. The `[P]` per-unit key authoring (parallel).
6. `clone_course_for_demo`, `seed_data`, `audit_xp`, adjacent fixes.

If step 5 runs long, it is a clean seam: the phase can ship steps 1-4 and carry the
remaining unit keys, because an unkeyed lesson simply keeps its `auto:` key and
still never double-awards.

- Backend changes need `docker compose restart backend`.
- Backend tests run via `docker compose exec -T backend pytest`. **Never run pytest
  concurrently with review subagents** — the shared test DB produces hundreds of
  bogus errors (phase-64 finding). A clean serial run is the only trustworthy one.
- `head` is shadowed locally — use `/usr/bin/head`.
- The `[P]` per-unit seed items are only parallel-safe **after** `_content_upsert.py`
  and the three delegating child helpers land. Do that as one sequential commit,
  verify a seed run is a no-op against existing content, then fan out. Two subagents
  must never be given units in the same file simultaneously unless they are
  editing disjoint `_create_unitN` methods — they are, but the file is 4,800 lines,
  so have each report its exact line range.
- `populate_robotics_course.py` is 4,802 lines and `populate_java_course.py` is
  3,179. Read only the method you are changing; the prose content is not your
  concern and must not be reflowed.
- Authoring 44 lesson keys and 11 quiz keys is the bulk of the mechanical work.
  Derive each slug from the lesson title, lowercase, hyphenated, course-prefixed —
  and once written, a key is permanent. Changing one later re-awards XP.
- `_stable_choice_order` (`populate_robotics_course.py:4732-4742`) is the existing
  precedent for deriving a deterministic value from content — read it before
  writing the upsert helpers. Note that JAVA101's `_create_lesson_questions` does
  **not** call it; that is the carried "answer always option 1" defect, and it is
  **not** in scope here. Do not fix it while you are in the file.
- The instructor question-edit endpoints (`PUT /api/lessons/<id>/questions/<qid>/`
  at `courses/views.py:2204`, `PUT /api/questions/<id>/` at
  `quizzes/serializers.py:296-309`) already delete and re-create their choices,
  which `SET_NULL`s student selections. Pre-existing, out of scope, worth a line in
  the handoff.
- `courses/models.py:95-114` documents the phase-53 DORMANT pattern; follow it
  verbatim for the `XPEvent.source_id` comment block.
