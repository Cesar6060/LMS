---
paths:
  - "backend/**/test*.py"
  - "backend/conftest.py"
---

# Backend Test Rules

## Running

- There is no host python/pytest. The only working invocation is
  `docker compose exec -T backend pytest` (service `backend`, `docker-compose.yml:18`;
  WORKDIR `/app` = repo `backend/`, so paths are relative: `courses/tests.py`).
- NEVER start a run while a review subagent is running tests. Both runs create the same
  `test_gamedev_db` (`docker-compose.yml:5`) and collide, producing hundreds of bogus
  errors. If another agent is testing, wait.
- `backend/pytest.ini:8` forces coverage —
  `addopts = -v --tb=short --cov=. --cov-report=term-missing` — so a full run is ~280s.
  While implementing, target it (`... pytest courses/tests.py -k roster`); run the full
  suite only before finishing.

## Throttling is off by default

- `backend/conftest.py:20` autouse `neutralise_throttles` patches
  `SimpleRateThrottle.THROTTLE_RATES` to all-`None` (`conftest.py:47-48`), so real rates
  never 429 unrelated tests. Scope keys are kept: DRF raises `ImproperlyConfigured` on a
  missing key but treats `None` as "no limit".
- Opt back in with `@pytest.mark.throttled` (`pytest.ini:12`). The marker branch also
  clears the file-backed `throttle` cache alias before and after the test
  (`conftest.py:39-45`) so counters don't leak between runs.
- Set the rate you need on the throttle class, not in settings:
  `monkeypatch.setattr(ScopedRateThrottle, 'THROTTLE_RATES', {'invite_send': '2/hour'})`
  (`courses/tests.py:3764`). DRF binds `THROTTLE_RATES` to the class at import time, so
  `override_settings(REST_FRAMEWORK=...)` does NOT reach it; a subclass patch shadows the
  conftest patch, which is why this works.

## Query-count guards (phase 63)

- N+1 fixes get a `CaptureQueriesContext` guard, imported inside the test body along with
  `django.db.connection`. Two shapes:
  - fixed count: one `with CaptureQueriesContext(connection) as ctx:` around the request,
    then assert on filtered `ctx.captured_queries` (`courses/tests.py:5434`).
  - measure-at-N-then-2N (preferred for lists): capture as `small` at 12 rows, create 12
    more, capture as `big` at 24, assert
    `len(big.captured_queries) == len(small.captured_queries)`
    (`courses/tests.py:5458-5484`, `discussions/tests.py:363-384`, `quizzes/tests.py:664`).

## Demo lockdown

- Every new write endpoint gets a case in `backend/core/tests/test_demo_lockdown.py`.
  Identity / shared-surface writes: add a method to `TestDemoBlockedWrites`
  (`test_demo_lockdown.py:130`) hitting the endpoint with the `demo_client` fixture (`:46`),
  call `assert_demo_blocked(response)` (`:123` — 403 plus the exact `DEMO_BLOCKED_BODY`),
  assert nothing was written. Learning writes that must stay open get the mirror case in
  `TestDemoAllowedWrites` (`:417`) asserting the success status.

## Permission boundaries

- Every new endpoint needs the full matrix: owning instructor (success), enrolled student,
  other-course/other instructor, anonymous — the existing convention. See the
  `# ---- Permission matrix ----` block at `courses/tests.py:2903` (`test_enrolled_student_403`
  / `test_unauthenticated_401` / `test_wrong_course_instructor_403`) and the parametrized
  set at `courses/tests.py:2078-2090`.
- Assert the exact code (403 denied, 401 anonymous) AND that the write did not happen.

## Don't "fix" the accepted-upload cases

- `backend/core/tests/test_uploads.py:78`, `:100`, `:112` pin that ordinary course material
  — markdown opening with `<div>`/`<p>`/`<br>`/comments/tables/links, shebang scripts, plain
  text — is ACCEPTED by the HTML sniff, so tightening `core/uploads.py` can't re-break it.
