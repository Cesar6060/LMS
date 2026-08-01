# Handoff: Phase 65 — XP content identity

## Current state

**Phase 65 is implemented and green on `feat/phase-65-xp-content-identity`.
Nothing is merged and nothing has touched Neon.**

The oldest open correctness bug in the codebase — carried since phase 58 — is
fixed. `XPEvent` deduped on `(user, source_type, source_id)` where `source_id`
was a bare lesson/quiz primary key with no foreign key, while both seed
commands opened every run with `course.units.all().delete()`. That cascade
destroyed the content *and* every student's `LessonProgress`, `QuizAttempt`,
`LessonQuizAttempt`, `AttemptAnswer`, `LessonQuestionAnswer` and
`LessonAttemptAnswer` rows, left the `XPEvent`s orphaned with their XP still
summed into `GameProfile.total_xp`, and then paid the student a second time
when they redid the rebuilt lesson on a new pk.

Both halves are fixed:

- **Identity.** `Lesson.content_key` and `Quiz.content_key` are stable
  author-chosen slugs; `XPEvent.source_key` holds that key and is what
  dedupes. 44 lessons and 11 quizzes carry hand-authored permanent keys.
- **Non-destructive seeding.** The wipe is gone. Both commands upsert through
  `courses/management/commands/_content_upsert.py`, all the way down to
  choices, so student work survives a rebuild at all.

### Verification (all run this session)

| Check | Result |
|---|---|
| `pytest` | **882 passed** (baseline was 766) |
| `makemigrations --check` | No changes detected |
| `migrate --plan` | exactly `courses.0024` → `quizzes.0004` → `gamification.0006` |
| `npx tsc --noEmit` | 0 errors |
| `npm run lint` | 0 errors, 1 pre-existing warning (`ErrorBoundary.tsx:117`) |
| `npx vitest run` | 122 passed |
| `git diff --stat main -- frontend/` | **empty** — zero frontend files changed |

### Manual verification against local Docker

`student1@demo.com` holds real ROB101 progress. Before and after
`populate_robotics_course`, byte-identical:

```
{"total_xp": 10500, "completed_lessons": 14, "lesson_question_answers": 19,
 "quiz_attempts": 5, "xp_events": 16,
 "rob101_pks": [254 … 277]}
```

Every one of the 24 lesson pks unmoved; all 24 lessons adopted by position and
stamped with their blueprint key; 0 `auto:` keys left in ROB101 or JAVA101.

- Re-completing a rebuilt lesson → `xp_awarded 0`, `total_xp` 10500 unchanged.
- Completing a genuinely new lesson → `xp_awarded 50`. New content is still new.
- Default seed run warns `Found blueprint-absent lesson #351 …` and deletes
  nothing; `--prune` deletes it. Both demonstrated live.
- `populate_java_course` and `clone_course_for_demo` both run clean twice in a
  row. DEMO101 still 5 units / 20 lessons / 74 sections / 5 quizzes, all keys
  `demo:`-prefixed and disjoint from JAVA101's.

**Old-code safety proven, not assumed** (the phase-64 lesson). With all three
migrations applied, raw `INSERT`s that omit `content_key`, `content_key` and
`source_key` all succeed and land NULL:

```
lesson insert OK  -> (350, None)
quiz insert OK    -> (88, None)
xpevent insert OK -> (21, None)
```

## The blocker a review pass caught (fixed)

A `code-reviewer` pass on the finished diff found a **release blocker I had
missed**, and it sat on the exact path this phase ships for. Worth recording
because the failure mode is subtle.

Phase 65 has two ways a ledger row ends up pointing at the right content under
the *wrong* key:

1. **Adoption.** The seed stamps a blueprint key onto a row that was carrying
   `auto:...` — but the `XPEvent` that already paid for it still holds the old
   key.
2. **The deploy window.** Old code inserts `XPEvent`s without `source_key` at
   all, and the migration that would have backfilled them already ran.

In both cases the next award's key lookup misses, and because the legacy
`(user, source_type, source_id)` uniqueness is still live, the insert that
follows raises `IntegrityError` — a **500 on an ordinary student action**
(re-passing a unit quiz, re-mastering a lesson quiz; neither is gated the way
lesson completion is). Reproduced before fixing:

```
django.db.utils.IntegrityError: duplicate key value violates unique constraint
  "gamification_xpevent_user_id_source_type_sour_fc16027d_uniq"
DETAIL:  Key (user_id, source_type, source_id)=(2, lesson_quiz, 1) already exists.
```

Note that dropping the legacy index would NOT have fixed this — it would have
converted the 500 into a silent double award, i.e. the phase-58 bug.

**Fix:** `_award_xp` now heals lazily. If the key misses but the *source id*
has already been paid under the same source type, the existing row is re-keyed
in place and no XP moves. No manual backfill step, no separate command. The
insert is wrapped in a savepoint so a lost race resolves against the unique
index rather than escaping into the caller's transaction.

`TestStrandedLedgerRows` pins both entry paths, plus that healing does not
advance a streak, is scoped to one source type, and does not leak across users.
`TestAdoption.test_xp_earned_before_adoption_is_not_re_awarded_after_it` pins
the whole thing end to end through the real seed command.

Three smaller findings from the same pass, also fixed:

- **`demo_key(None)` could hijack a lesson from another course.**
  `filter(content_key=None)` becomes `IS NULL` in SQL, matching an arbitrary
  keyless row anywhere; the upsert would reassign its unit, and `prune_stale`
  would then delete it on the same run. `demo_key` is now total, and
  `upsert_lesson`/`upsert_quiz` raise on a falsy key.
- **`audit_xp` could not see stranded rows** — the very thing it needs to be
  the pre-deploy canary for. New `STRANDED ROWS` report.
- **Blob deletes ran inside the seed transaction.** Storage is not
  transactional, so a rollback would have left live rows pointing at deleted
  R2 objects. Deferred to `transaction.on_commit`.

## Not done — deliberately

- **Nothing is merged; Neon is untouched.** Per `CLAUDE.md`, the PR opens and
  stops.
- **No repair of existing prod XP.** `audit_xp` reports; it never writes.
  Deciding what to do about inflated totals is the follow-up, and the report
  is its input.
- **JAVA101's answer-rotation defect is still open** and was deliberately not
  fixed while in the file. Rotating its choices now would reorder every stored
  choice and, because children are matched positionally, silently re-point
  historical student selections. It needs its own change with its own data
  migration.

## Deploy runbook (for whoever ships this)

1. Hand-apply to Neon **before** deploying code, in this order:
   `courses.0024_lesson_content_key`, `quizzes.0004_quiz_content_key`,
   `gamification.0006_xpevent_source_key`. All additive and nullable; the
   `gamification` one depends on the other two so the keys exist when its
   backfill runs.
2. Deploy the code.
3. Run `python manage.py populate_robotics_course` and
   `populate_java_course` **without** `--prune`. This is what adopts prod's
   existing content by position and stamps the blueprint keys. Read the
   blueprint-absent warnings before deciding whether `--prune` is wanted.
4. Run `python manage.py clone_course_for_demo`.
5. Run `python manage.py audit_xp` against prod and **put the numbers in the
   next handoff.** Do not repair anything.

## Numbers from the local audit (prod will differ)

```
ORPHANED XP EVENTS   student1@demo.com  3 events   90 XP
LEDGER DRIFT         student1@demo.com  profile 10500  ledger 530  delta +9970  Lv 15 -> Lv 3
AMOUNT DRIFT         None
CONTENT KEYS         no duplicates; ROB101 and JAVA101 fully adopted
```

The 3 orphans are genuine — real damage from earlier destructive reseeds,
surfaced by the migration backfill. **The +9970 ledger drift is NOT damage**:
phase 64 deliberately hand-set this account to Lv 15 to unlock every cosmetic.
Do not read the local drift number as evidence of prod inflation; prod's own
`audit_xp` run is the only thing that answers that.

## Behavior changes to know about

1. **A no-op award no longer advances the streak.** `_update_streak` is now
   gated on whether an `XPEvent` was actually created, so re-completing
   already-paid content does not extend a streak. Deliberate. Today it is
   masked by the `_just_completed` flag in `courses/serializers.py`, so no
   current caller is affected — but it was one new caller away from live.
2. **`clone_course_for_demo` no longer wipes DEMO101.** Demo progress against
   content JAVA101 still has now survives a refresh. The command still prunes
   unconditionally, because DEMO101 is a mirror.
3. **Badge asymmetry is now documented and pinned, not fixed.** Criteria read
   live progress rows, so deleting content un-satisfies them — but `UserBadge`
   is never revoked, so the badge sticks. Intentional (decision 4);
   `TestBadgeAsymmetry` stops anyone "fixing" it.

## Gotchas discovered

- **`AddField` with a callable default evaluates the callable ONCE.** All rows
  get the same value and the unique index then fails. Every one of the three
  migrations is `AddField` (bare) → `RunPython` (stamp per row) → `AlterField`
  (add unique + default). Do not collapse them.
- **`source_id` had to become nullable.** The legacy uniqueness on it is still
  live, so an award carrying no id cannot use a sentinel like 0 — every such
  row would collide with every other. NULL keeps them distinct. This is
  deviation 1 in the spec.
- **`Lesson` is `unique_together ['unit', 'order']`**, so upserting into an
  occupied slot raises IntegrityError. `_content_upsert` parks the occupant
  above `PARK_OFFSET` and `prune_stale` settles it back to a real order — on
  every run, pruning or not.
- **Django nulls `pk` after `delete()`**, which made the first `PruneReport`
  useless for logging which rows went. `_delete_keeping_pk` restores it.
- **Rolling a migration back and re-applying it re-stamps fresh `auto:` keys**
  and thereby breaks the link to existing `XPEvent.source_key` values. Fine in
  dev (re-run the seeds to re-adopt), but it is a reminder that these
  migrations are not casually reversible against real data.
- **`node_modules` is a container volume** — run `tsc`/`vitest`/`lint` via
  `docker compose exec -T frontend`, not from the host (carried from phase 64).
- **Never run pytest concurrently with review subagents** (carried).
- **A live legacy unique index turns a stale key into a 500, not a no-op.**
  This is the trap behind the blocker above: keeping the old constraint
  "alongside" the new one is not free, because any row whose key drifts while
  its id stays put now violates it. If `source_id` is ever dropped, re-check
  `_award_xp`'s healing path — it is what makes the two constraints coexist.
- **`transaction.on_commit` callbacks never fire under pytest-django's default
  transactional test case.** Tests asserting blob cleanup need
  `django_capture_on_commit_callbacks`.

## Files to read first

1. `docs/specs/phase-65-xp-content-identity.md` — checklist + the Deviations
   section at the bottom.
2. `backend/courses/management/commands/_content_upsert.py` — where the real
   risk of this phase lives, and the most heavily tested new module.
3. `backend/gamification/models.py` — the `XPEvent` docstring explains why the
   key and not the id is the correctness core, and why `source_id` is DORMANT.
4. `backend/gamification/management/commands/audit_xp.py` — what to run
   against prod after the deploy.

## Carried remainders (all still open, none touched this phase)

- `THROTTLE_SLIDE_IMPORT` ceiling
- Phase-61 real-deck slide-import smoke test (still the only flow never
  exercised against R2 signed URLs)
- JAVA101 answer-rotation reseed (see above — now has a written reason)
- Phase-56 regression click-through; phase-64 manual click-through (8 items)
- Sentry LoginPage TypeError
- Dependabot majors: #68 react-dom, #86 eslint 10, #87 vite 8, #88 tailwind 4
- Instructor question-edit endpoints (`courses/views.py:2204`,
  `quizzes/serializers.py:296-309`) still delete and re-create their choices,
  which `SET_NULL`s student selections. Pre-existing, out of scope here, but
  it is the same failure mode `_content_upsert` was written to avoid — worth
  pointing those two at the shared helper in a later phase.
