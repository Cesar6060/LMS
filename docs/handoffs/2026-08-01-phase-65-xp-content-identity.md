# Handoff: Phase 65 — XP content identity

## Current state

**SHIPPED. Merged as `f308029f` (PR #90) 2026-08-02 01:29 UTC; migrations
applied to Neon 02:0x UTC after an outage caused by the wrong ordering.
Production is verified healthy and its XP ledger is clean.**

Sequence of what actually happened:
1. PR merged before the Neon migrations → Render deployed code that SELECTs
   `content_key` against a schema without it → every course read 500'd.
2. A first repair attempt ran `migrate` against the LOCAL Docker database
   (the `DATABASE_URL` placeholder was not substituted), which reported
   success while changing nothing on Neon.
3. Confirmed directly against Neon that all three columns were absent and
   `django_migrations` still ended at `courses.0023`.
4. Applied all three migrations to Neon over the DIRECT (non-pooler)
   endpoint. Prod recovered on the next request — no restart, no rollback.

**Post-fix verification against production:**

| Endpoint | Before | After |
|---|---|---|
| `DEMO101/units/` | 500 | **200** — 5 units, 20 lessons |
| `/api/health/?deep=1` | 200 | 200 |
| `/api/gamification/profile/` | 200 | 200 |

Phase 65 itself is implemented and green.

## Production audit — nothing to repair

`audit_xp` against Neon reports **clean across every dimension**: no orphans,
no stranded rows, no ledger drift, no amount drift, no duplicate keys.

The reason is worth stating plainly: **production holds 0 `XPEvent` rows.**
The double-award bug was real and would have bitten, but no student had
earned XP in prod yet, so there is no inflation to measure and nothing to
decide about repair. The follow-up this phase was supposed to tee up does not
exist. The local-dev drift figures (+9970, 3 orphans) were dev-only artifacts
and say nothing about prod.

**Outstanding: adoption has not run.** 55 rows still carry `auto:` keys
(ROB101 24 lessons + 6 quizzes, JAVA101 20 lessons + 5 quizzes). This is
SAFE — every row has a unique stable key and the ledger dedupes on it, so the
bug is fixed either way. What adoption adds is protection for a *future*
delete-and-reseed: content on a blueprint key keeps its XP identity through
one, content on an `auto:` key does not. With 0 XP events there is nothing at
risk today, but it is worth doing before students start earning. Run both
seed commands WITHOUT `--prune` to perform it.

## Incident: prod 500s on every course read after the merge

`render.yaml` has `branch: main` and no migrate step (`buildCommand` is
`pip install` + `collectstatic`), so the merge deployed code that SELECTs
`content_key` against a Neon database that does not have the column. Django
includes every concrete field in its default SELECT, so **every `Lesson`
query fails**.

Isolated against prod ~20 min after the merge:

| Endpoint | Result | Reads `Lesson`? |
|---|---|---|
| `/api/health/` shallow | 200 | no |
| `/api/health/?deep=1` (`SELECT 1`) | 200 | no — DB reachable |
| `/api/auth/demo-login/` | 200 | no |
| `/api/gamification/profile/` | 200 | no |
| `DEMO101/units/` | **500** | **yes** |

Note the monitoring gap this exposed: **deep health stayed 200 throughout.**
It only runs `SELECT 1`, so it cannot see a missing column — the uptime check
said healthy while the course experience was entirely down. Worth adding a
canary that reads one real content row.

**Fixed** by applying the three migrations to Neon. Additive and nullable, so
it was a pure forward repair — no rollback, no data risk, no restart.

Two traps this hit, both worth remembering:
- **A `migrate` that prints "No migrations to apply" is not proof you hit the
  right database.** The first attempt silently targeted local Docker. Always
  print `connection.settings_dict['HOST']` before trusting a prod migration.
- **Use the DIRECT Neon endpoint for DDL**, not the `-pooler` host.

**The ordering constraint is not optional and is the whole point of decision
8.** Migrations must be hand-applied to Neon BEFORE the code deploys. The PR
body carried this warning; the merge went ahead first anyway. If this repo
keeps auto-deploy on `main`, consider a `preDeploy` migrate step in
`render.yaml` or a branch protection rule, because the ordering currently
depends entirely on the person merging remembering it.

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

- **No repair of existing prod XP** (see below). Note this is separate from
  the incident above: the incident is a schema gap, not an XP problem.
- **No repair of existing prod XP.** `audit_xp` reports; it never writes.
  Deciding what to do about inflated totals is the follow-up, and the report
  is its input.
- **JAVA101's answer-rotation defect is still open** and was deliberately not
  fixed while in the file. Rotating its choices now would reorder every stored
  choice and, because children are matched positionally, silently re-point
  historical student selections. It needs its own change with its own data
  migration.

## Deploy runbook

**Step 1 was skipped on the real deploy — do it now if it has not been done.**

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
- **`/api/health/?deep=1` cannot detect a schema gap.** It runs `SELECT 1`,
  which succeeds against any reachable database regardless of whether the
  columns the code needs exist. It reported healthy through a total course
  outage. A canary that reads one real `Lesson` row would have caught it.
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
