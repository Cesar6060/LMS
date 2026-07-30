# Handoff: Phase 63 — Shared throttle cache + N+1 query elimination

## Current state
Phase 63 complete, **PR #81 open, NOT merged** (CI was still running at handoff):
https://github.com/Cesar6060/LMS/pull/81 on branch
`feat/phase-63-throttle-cache-and-query-counts` (commit `82dafe2`).
Backend only — `git diff --stat main -- frontend/` is empty, so Pages is a
no-op and only the Render deploy matters. No migration
(`makemigrations --check` clean), no model change, no new dependency.
Delivered:
- `config/settings.py` gained its first-ever `CACHES` block: `default` spelled
  out as LocMemCache, plus a `throttle` alias on `FileBasedCache`
  (`THROTTLE_CACHE_DIR`, `MAX_ENTRIES` 5000). `core/throttling.py` got a `cache`
  property on `ClientIPIdentMixin`, which reaches all four throttle classes.
- `courses/serializers.py`: `_build_lesson_stats` + `LessonStatsMixin` +
  `LessonStatsListSerializer` (bulk per-lesson counts, prefetch-aware),
  `ActiveEnrollmentCountMixin` + `prefetch_active_enrollments()`, and a
  roster progress rewrite. Matching queryset changes in `courses/views.py`.
- `quizzes/` and `discussions/` equivalents (implemented by subagents).
- `GET /api/courses/<code>/invites/` had **no throttle at all** — fixed.
Verified: /verify-stack PASS — 710 backend tests (was 665), tsc 0, eslint 0
errors (1 pre-existing warning), vitest 101, build OK, editor chunk 13.21 kB
gzip (unchanged from phase 62).

## In progress / not done
- **PR #81 is unmerged and CI was still running.** Check it before merging.
- Everything in the spec's checklist is done; 10 deviations are recorded in its
  "Assumptions / deviations" section.
- Carried, untouched by this phase: phase-62 manual fullscreen pass on prod;
  confirming the phase-62 Pages bundle actually shipped (a monitor timed out
  waiting for it — worth re-checking); real-deck slide-import smoke test;
  XP double-award schema fix; JAVA101 answer-rotation reseed; phase-56
  regression click-through; school-device login test; Sentry LoginPage
  TypeError.
- Deferred deliberately: `UserSerializer.preferences` (reverse OneToOne, 1
  query per user across 7 nesting sites) — the only remaining N+1 of any size.

## Next steps
1. Merge PR #81 once CI is green.
2. **After the Render deploy, re-check rate limits.** They were being enforced
   at ~2x their configured values; they will now bite as written. If any value
   was tuned against the doubled behaviour it may need raising. Leave
   `THROTTLE_CACHE_DIR` unset — the default is correct on Render.
3. Confirm throttling still fires in prod (demo-login at 10/min is the safe one
   to hammer) and that normal browsing is NOT throttled — a bad `MAX_ENTRIES`
   or an unwritable cache dir would show up as either no throttling or
   spurious 429s.
4. Phase-62 remainders (manual fullscreen pass, bundle confirmation) and the
   phase-61 real-deck smoke test.

## Decisions made
- **FileBasedCache, not DatabaseCache on Neon.** The `anon`/`user` scopes run on
  every request; routing them through Postgres would have added ~4 queries to
  the hottest path — trading a limit-accuracy bug for a latency bug.
- **`cache` is a property, not a class attribute.** A bound attribute freezes
  one thread's backend at import and makes `override_settings` unreachable.
  Verified in DRF's source that `self.cache` is only ever read, never assigned.
- **Context-caching in the serializer, not `annotate()` per queryset.**
  `LessonListSerializer` is instantiated by six views; an annotation must be
  repeated in all six and breaks silently when a seventh forgets.
- **The stats mixin prefers a prefetch cache when one exists.** Course detail
  uses the bulk path deliberately: prefetching sections there would pull every
  section's markdown `content` into memory just to count rows.
- **`to_attr` prefetch for enrollments, not an annotation.** `student_count`
  and `is_enrolled` both called `.filter()`, which rebuilds the queryset no
  matter how it was prefetched.

## Gotchas discovered
- **`cache.clear()` in the throttle tests was clearing the wrong alias** and,
  because the new cache is file-backed, throttle history survived *entire
  pytest sessions*. The existing 19 throttle tests passed anyway — no two share
  a scope+ident pair — so this would have shipped green. Always clear
  `caches['throttle']`.
- **Annotating over a read-only model `@property` raises.** Django assigns
  annotations with `setattr`. `Quiz.question_count` is such a property; annotate
  under a different name and use `source=`.
- **`IntegerField(source='missing_attr')` silently DROPS the field** — DRF turns
  a missing read-only source into `SkipField` rather than raising. That is an
  invisible response-shape change; `QuizQuestionCountField` guards it.
- **`.count()` on a prefetched related manager still queries.** Only `len()` of
  `.all()` reads the cache. Same for `.filter()`, which never reuses a prefetch.
- `FileBasedCache.__init__` creates its directory eagerly, so the cache dir
  appears as soon as anything touches the alias — not on first write.
- `npm run build` fails without `VITE_API_URL`; that guard is intentional.

## Files to read first
1. docs/specs/phase-63-throttle-cache-and-query-counts.md — checklist + the 10 deviations + measured before/after numbers.
2. backend/config/settings.py — the CACHES block and its reasoning.
3. backend/core/throttling.py — the `cache` property.
4. backend/courses/serializers.py — `LessonStatsMixin` / `LessonStatsListSerializer`, the pattern the other apps copy.
5. backend/courses/tests.py (TestPhase63* classes) — the query-count guard style.
