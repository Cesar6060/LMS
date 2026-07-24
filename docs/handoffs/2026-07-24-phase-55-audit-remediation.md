# Handoff: Phase 55 — audit remediation (security, hygiene, drift, test infra)

## Current state

Phase 55 complete. **PR #60 open, not merged**: https://github.com/Cesar6060/LMS/pull/60
Branch `feat/phase-55-audit-remediation`, 8 commits, 130 files. All 101 spec
checklist items done; `docs/specs/phase-55-audit-remediation.md` has an
"Outcome" section recording every deliberate deviation.

`/verify-stack` PASS: **569 backend tests** (was 503), **50 frontend tests**
(there was no runner before), `tsc` 0 errors, `eslint` 0 errors, coverage
baseline **94%**. `pip-audit --requirement requirements.txt` clean.

Landed: allauth 65.14.1 + simplejwt 5.5.1 + pyjwt 2.13.0 + pillow 12.3.0 +
pinned requests (A1); cross-course lesson-move guard (A2); avatar hardening
(A3); soft-delete unenroll + demo lockdown (A4); `TRUST_CF_HEADERS` (A5);
pagination on notifications + roster (A6); axios 1.18.1 (A7); dependabot + CI
audit gates (A8); `.gitignore` fix that recovered `docs/archive/PLAN.md` into
the repo (B1); docs corrections (B3/B4); 67 historical docs archived (B5);
clutter removed (B6); seeding-gate drift fixed (C1); legacy batch quiz flow
deleted (C2/C3); dormant columns dropped (C4); content write path closed (C5);
Redis stub removed (C6); real per-lesson completion (C7); vitest (D1);
coverage (D2); first `core/` tests (D3); notification signal tests (D4).

## In progress / not done

- **Migration `0021` is applied LOCALLY ONLY.** Not applied to Neon. See
  Next steps — the order matters and is not the usual one.
- **47 merged remote `lms/*` branches not pruned** — user chose to leave them
  this session. The 6 unmerged ones stay regardless. Recorded as a follow-up.
- **Manual click-through not performed** (local or prod). The five scenarios
  are listed in the spec's "Manual click-through" section — the C5 lesson-create
  path and the A3 avatar upload are the two most worth doing by hand.

## Next steps

1. **Review and merge PR #60.** Do NOT migrate first — see step 2.
2. **After the merge deploys and Render is healthy**, apply the migration:
   `DATABASE_URL=<neon> python manage.py migrate courses 0021`.
   Then verify `course_map` and a lesson detail call, and watch Sentry.
3. Post-deploy: `https://stemquest-api-va.onrender.com/api/health/?deep=1` →
   `{"status":"ok","database":"ok"}`, and `https://stemquests.com` loads.
4. Phase 56: Django 4.2 → 5.2 LTS (4.2 is past EOL; 4.2.30 is its final patch).
5. Phase 56b (or fold into 56): react-router 7 → 8, which requires React 18 → 19.

## Decisions made

- **Deploy order inverts for `0021`: merge FIRST, then migrate.** Every prior
  phase shipped additive migrations where migrating first is correct. This one
  is subtractive — old code on `main` still `SELECT`s both dropped columns, so
  migrating first would 500 `LessonViewSet` **and `course_map`** for the length
  of the Render deploy. Caught by db-migration-checker; written into the spec.
- **react-router stays on 7.x.** v8.3.0 needs React ≥19.2.7. Also found the
  spec's premise was outdated: the open-redirect that genuinely applied here is
  already fixed in 7.18.1; only RSC-mode CSRF remains, and this is a declarative
  SPA. Allowlisted in CI so the debt stays visible rather than silenced.
- **eslint stays on 9.** eslint 10 needs react-hooks@7, whose new
  React-Compiler rules flag 52 existing sites — a lint-policy migration, not a
  bump. Dev-only, no runtime exposure.
- **C1 fixed in `_create_lesson_questions`, not at the 20 create sites**, so the
  invariant (gate on iff questions exist) is structural and cannot drift again.
- **Retired the phase-54 migration test rather than "keeping it working."** Once
  the column is dropped, 0020's data function is only runnable against
  historical state a head-migrated test DB does not have. The rule it protected
  is now pinned forward by `TestSeedingGateMatchesProduction`.

## Gotchas discovered

- **`frontend/.npmrc` pins `os=linux`.** Host `npm install` therefore skips
  platform binaries and `npm test` dies on a missing `@rollup/rollup-darwin-arm64`.
  Run frontend checks **in the container** (`docker compose exec -T frontend ...`),
  which is what CLAUDE.md's commands already say.
- **CI leaves `DEBUG` unset**, so `TRUST_CF_HEADERS` (default `not DEBUG`) was
  silently ON for the whole CI run — the opposite of the documented dev/test
  default. Now pinned `False` in the workflow's test step.
- **`Image.verify()` does not check format.** It accepts anything Pillow can
  decode, so an extension allowlist alone is bypassable by lying about the name
  and content-type. Must read `image.format` *before* `verify()` (which
  invalidates the object) and compare it to the declared extension.
- Serializers built without `context={'request': request}` make C7's
  `is_completed` silently return `False` rather than erroring. Both `reorder`
  responses had this.
- `npm audit --json` with `|| true` returns `{"error": ...}` on a registry
  failure — a naive gate reads no `vulnerabilities` key and passes green.

## Files to read first

1. `docs/specs/phase-55-audit-remediation.md` — especially "Outcome",
   "Deploy notes", and "Follow-ups" at the bottom.
2. `backend/courses/migrations/0021_drop_dormant_lesson_quiz_columns.py` — the
   one unapplied migration, with its rationale in the module docstring.
3. `.github/workflows/ci.yml` — the new audit gates and their allowlist policy.
4. `docs/runbooks/workflow-prompting-guide.txt` — now the single workflow guide.
5. `README.md` — corrected on auth (JWT), the demo course (DEMO101), and CI.
