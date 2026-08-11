---
paths:
  - "backend/**/migrations/*.py"
  - "backend/**/models.py"
---

# Django Migration Safety (Render pre-deploy window)

## The hazard: migrations run while the OLD code is serving

`render.yaml` (service `stemquest-api-va`, `branch: main`) has:

```yaml
preDeployCommand: python manage.py migrate --noinput
```

- Runs after the build, on a separate instance, BEFORE the new version takes
  traffic. If it fails or times out (30 min cap), the whole deploy aborts and
  the current version keeps serving.
- So do NOT hand-apply to Neon before merging. The platform enforces ordering;
  a manual apply is only for watching a migration land or recovering a deploy.
- It guarantees ORDERING ONLY, never COMPATIBILITY. Between `migrate` finishing
  and the new code taking traffic, the old code runs against the new schema.

**Phase 65 (2026-08-02) worked example.** Before `preDeployCommand` existed,
migrations were hand-applied and the ordering rested on the merger remembering.
A merge landed first, so Render deployed code that SELECTs `Lesson.content_key`
against a schema without that column — and because Django puts every concrete
field in its default SELECT, EVERY lesson query 500'd. The course experience was
down until the migrations were applied by hand. See
`docs/handoffs/2026-08-02-phase-65-deploy-and-hardening.md` and the
`preDeployCommand` comment block in `render.yaml`.

## Rules

- **Additive only.** New columns land nullable, or carry `db_default=`.
- **NEVER plain `default=` on a new NOT NULL field.** Django's `AddField`
  backfills existing rows and then DROPS the database default. The old code
  does not know the column exists, INSERTs without it, and 500s on NOT NULL.
  Real usage: `backend/courses/models.py:801` (`image`/`image_alt`, `''`,
  migration `courses/0023`), `courses/models.py:132` (`Unit.is_locked`, `False`,
  `courses/0025`), `backend/gamification/models.py:50-52` (avatar slots,
  `'none'`, `gamification/0005` — the phase-64 lesson: `GameProfile` rows are
  created lazily by `get_or_create`, so the gap was a live 500).
- **Nothing dropped in the same deploy** as the code that stops using it. Mark
  the field DORMANT (unused, still present), drop the column in a later change.
- **Callable defaults need three operations**, in this order:
  1. bare `AddField` — nullable, NOT unique, NO default;
  2. `RunPython` stamping a distinct value per existing row;
  3. `AlterField` adding `unique=True` and the callable default (per-INSERT
     from here on).
  One `AddField(default=callable)` evaluates the callable ONCE and writes the
  same value to every row. Real example:
  `backend/courses/migrations/0024_lesson_content_key.py` (and the twin
  `backend/quizzes/migrations/0004_quiz_content_key.py`).
- **A new unique constraint** requires proving the backfill cannot produce a
  duplicate — per-row distinct values, or a NULLable column (Postgres allows
  many NULLs under a unique index, which is also what keeps old INSERTs legal).
- **Reverse migrations must leave a working schema.** Give every `RunPython` a
  reverse callable, even a documented no-op (see `noop_reverse` in
  `courses/0024`) — never an accidental no-op where data must be restored.
- **If a migration cannot satisfy all of the above, split it across two
  deploys** — compatible half first (add + backfill), destructive half after the
  new code is live — and say so explicitly in the PR description.

## Verifying after deploy

- `/api/health/?deep=1` runs only `SELECT 1`. It CANNOT see a missing column and
  reported 200 through the total phase-65 course outage.
- Always pair it with a real authenticated content read (a course's units and
  lessons) before calling a deploy good.
