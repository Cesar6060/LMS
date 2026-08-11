---
name: verify-stack
description: Run the full verification suite (backend tests, type check, lint, frontend tests, both dependency audits, production build) and report pass/fail with evidence. Use before declaring any task or phase complete.
---

Run all seven checks, in this order — it mirrors what CI runs, so a PASS here means CI should be green. Show the actual output for each. Never assert success without evidence.

1. `docker compose exec -T backend pytest`

   There is no host Python on this machine — a bare `pytest` will not run. This is the only working invocation.

   **~280 seconds.** `backend/pytest.ini` forces `--cov=. --cov-report=term-missing`, so a full run is slow by design. Budget for it; do not assume it hung.

   **Do not run this while a review subagent is also running tests.** Parallel runs collide on the shared `test_gamedev_db` and produce hundreds of bogus errors that look like real failures. If an agent is mid-run, wait for it.

2. `cd frontend && npx tsc --noEmit` — zero errors.

3. `cd frontend && npm run lint` — zero errors. One `react-refresh/only-export-components` warning is known and expected; warnings are not failures, errors are.

4. `cd frontend && npm test` — vitest. Every file passes.

5. `cd frontend && npm audit --omit=dev` — runtime dependencies only.

   CI does not run bare `npm audit`: it fails on any high/critical advisory that is not on a reviewed `ACCEPTED_ADVISORIES` list in `.github/workflows/ci.yml`. If this step reports something, check that list before treating it as new.

6. `docker compose exec -T backend pip-audit --requirement requirements.txt`

   `pip-audit` is installed in the backend image. CI has **no severity filter** here — any known advisory of any severity in a declared dependency fails the build. An advisory in `pip` itself is the known exception; anything else is real.

7. `cd frontend && VITE_API_URL="http://localhost:8000/api" npm run build`

   `vite.config.ts` fails a production build with no `VITE_API_URL`, so the variable is required even locally. This is the exact bundle Cloudflare Pages ships, and it re-runs `tsc -b` — the overlap with step 2 is deliberate.

## If anything fails

- Fix the ROOT CAUSE. Do not suppress errors, skip tests, loosen types, or add an audit exception to make a check pass.
- Re-run the failed check after fixing.
- If the same check fails 3 times, stop and summarize the problem for the user instead of thrashing.

End with a one-line verdict: **PASS** (all seven green) or **FAIL** (what is still red).
