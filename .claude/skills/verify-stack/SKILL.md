---
name: verify-stack
description: Run the full verification suite (backend tests, type check, lint) and report pass/fail with evidence. Use before declaring any task or phase complete.
---

Run these checks in order. Show the actual output for each — never assert success without evidence.

1. `cd backend && pytest` — all tests pass
2. `cd frontend && npx tsc --noEmit` — zero errors
3. `cd frontend && npm run lint` — zero errors

If anything fails:
- Fix the ROOT CAUSE. Do not suppress errors, skip tests, or loosen types to make checks pass.
- Re-run the failed check after fixing.
- If the same check fails 3 times, stop and summarize the problem for the user instead of thrashing.

End with a one-line verdict: PASS (all green) or FAIL (what's still red).
