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
- **SHIPPED 2026-07-30 (user merged):** PR #81 merged as `8968bfc`, both CI
  checks green. Post-deploy verified on prod, not inferred:
  - Shared throttle cache works. `POST /api/auth/demo-login/` allowed exactly
    10 then 429'd on the 11th, and all 6 follow-ups also 429'd with zero 200s
    leaking through. Under the old per-worker LocMemCache those 10 would have
    split ~5/5 across workers (first 429 near #21, with 200s alternating in
    after). This is simultaneously the proof that the phase-63 backend is
    deployed and that the fix works.
  - 12 unauthenticated API GETs all returned 401, no spurious 429s — the cache
    dir is writable and MAX_ENTRIES is sane.
  - Throttle window expired cleanly; demo-login recovered to 200.
- **CLOSED — phase-62 Pages bundle DID ship.** `.max-md\:aspect-auto`
  (phase-62-only class) is present in the served
  `https://stemquests.com/assets/index-BDsu5Bnn.css`. The monitor that timed
  out waiting for it was a false alarm; do not re-investigate.
- **CLOSED — phase-62 manual fullscreen pass.** User confirmed working on prod
  2026-07-30. This was the last untested path from phase 62.
- **CLOSED — school-device login test** (open since phase 57). User confirmed
  working on a real school device 2026-07-30.
- Still open, carried: phase-61 real-deck slide-import smoke test (see the
  throttle note in Next steps); XP double-award schema fix; JAVA101
  answer-rotation reseed; phase-56 regression click-through; Sentry LoginPage
  TypeError.
- Deferred deliberately: `UserSerializer.preferences` (reverse OneToOne, 1
  query per user across 7 nesting sites) — the only remaining N+1 of any size.

## Next steps
1. **Decide on `THROTTLE_SLIDE_IMPORT`.** Phase 63 halved its real-world
   ceiling and this is the one scope where the doubling was load-bearing. One
   slide = one upload and decks cap at 100 pages
   (`frontend/src/lib/slideImport.ts:17`), so at 300/hour it went from ~6 full
   decks per hour to exactly 3, before retries — and a cancelled-then-retried
   import burns the budget twice. Raising it to 600/hour restores the previous
   effective behaviour. For every other scope the halving IS the intended fix;
   only this one had headroom that mattered. Gotcha: setting the var via the
   Render API does NOT trigger a deploy — restart the service after.
2. Phase-61 real-deck smoke test — export a Google Slides deck to PDF and
   import it into a live lesson. Still the one flow never exercised against R2
   signed URLs, and now also the practical check on item 1.
3. Next phase candidate: **XP double-award** (carried since phase 58). Oldest
   open correctness bug — `XPEvent.source_id` is a bare int keyed on
   lesson/quiz PKs, so rebuilding course content re-awards XP students already
   earned. Verify the "needs a migration" claim against the gamification models
   before scoping; that assumption is inherited from the phase-58 handoff and
   has not been checked.

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
