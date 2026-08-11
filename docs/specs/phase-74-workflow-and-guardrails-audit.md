# Phase 74 — Workflow modernization and Claude Code guardrails

## Goal

The `.claude/` workspace has not been touched since phase ~50 while the codebase
moved through phases 64–73, and it has drifted far enough to actively mislead.
The rules files tell Claude to write inline permission checks the codebase
abandoned, name a test command that cannot run on this machine, and describe a
Radix-based UI that does not exist. The review agents probe for deadlines,
grades and submissions — none of which are models in this project — while
knowing nothing about throttling, demo-blocking, unit locking or upload
verification, which are the surfaces phase 73 actually found bugs in.
Meanwhile `settings.local.json` pre-approves `gh pr merge`, which contradicts
`/finish-phase`'s standing rule that merging is the user's decision because it
deploys to production. This phase re-grounds the whole workflow in what the
code does today, adds a real permission model with the prod-destructive
guardrails live and the rest written down but inert, and makes the workspace
visible in the public repo so the process is part of the portfolio rather than
hidden by `.gitignore`.

**No application code changes.** This is a workflow, configuration and
documentation phase.

## Out of scope

- Any change under `backend/` or `frontend/` — enforced as a verification step.
- Phase 72 (content-upsert hardening), still unstarted. Not folded in here.
- The five carried owner actions from phase 73 (Neon `protected: true`, `_dmarc`
  + root SPF, invite-deliverability test, JAVA101 answer rotation, exercising
  join-code/invite-link against prod). Only the *stale* one is corrected — see
  Repo hygiene.
- Making `docs/PORTFOLIO.md`, `INTERVIEW_GUIDE.md`, `DEMO_SCRIPT.md`,
  `SCREENSHOT_CHECKLIST.md` or `CLAUDE-CODE-WORKFLOW.md` public. They stay
  gitignored.
- Activating the `ask` and `allow` permission lists, and the non-Neon MCP
  policy. Those ship inert in `_proposed` for a later phase.
- Retiring the `dev-learning-platform` GitHub repo itself. Only the local
  remote is renamed.

---

## Audit findings — what is stale and why

Every claim below was verified against the working tree, not inferred.

### settings.local.json

| Finding | Evidence |
|---|---|
| `Bash(gh pr merge:*)` is pre-approved | Directly contradicts `/finish-phase` step 10: "Never merge the PR yourself — merging deploys to production. That decision is the user's." |
| `render ssh:*`, `render jobs create:*`, `gh secret set:*` pre-approved | Production shell, production job execution, and CI secret writes, all with no prompt |
| No `deny` list, no `ask` list, no `defaultMode` | Nothing blocks `git push --force`, reading `.env`, `docker compose down -v`, or Neon writes against prod |
| Not committed | `.gitignore:19` ignores all of `.claude/`, so a fresh clone starts with zero guardrails |
| `Bash(docker compose *)` — **not a defect** | Space-`*` and `:*` are documented as equivalent forms. Leave it. |

### Rules

`backend.md` contradicts itself: the bullet list says to check
`request.user == course.instructor` inline, while the section below it says all
authorization lives in `courses/permissions.py`. That file now exports **ten**
helpers; the rules name two. It also says "prefer running single test files
(`pytest path/to/test.py`)" — there is no host Python (`which pytest` →
not found); the real invocation is `docker compose exec -T backend pytest`.

Six load-bearing convention families are entirely absent:

1. **Throttling.** Stock DRF throttle classes must never be used (`core/throttling.py:34-63` overrides both `get_ident` and the cache alias). Naming any throttle on a view *replaces* `DEFAULT_THROTTLE_CLASSES`, so `*GLOBAL_THROTTLES` must be spread alongside — pinned by a sweep test at `accounts/tests.py:883-905`. For `@api_view` functions the scope goes on the generated class (`my_view.cls.throttle_scope = ...`) or the throttle is silently inert (`courses/views.py:3157`). Every scope needs a non-`None` default in settings or two sweep tests fail (`courses/tests.py:3805-3841`). Any dj-rest-auth shadow needs `re_path(r'^…/?$')` mounted before the include (`accounts/urls.py:30-57`).
2. **Demo write-blocking.** `core/demo.py` is the single source of truth; ~20 call sites use `require_not_demo` / `require_not_demo_course`, CBVs use `core/permissions.py` `NotDemoAccountForWrites`, and denials must carry the exact `DEMO_BLOCKED_BODY` (`403` + `code: 'demo_blocked'`) because the frontend interceptor keys on that code. Every new write endpoint gets an entry in `core/tests/test_demo_lockdown.py`.
3. **Access helpers beyond the two documented.** `require_unit_unlocked` is called on ~20 content reads across `courses/views.py` and `quizzes/views.py`; `locked_unit_ids_for` strips locked units from denominators; `accessible_course_ids` scopes ViewSet querysets; `require_pending_invite` gates enrollment and matches the lowercased email **exactly, never `iexact`** (documented Turkish dotless-i bug); `require_enrollment` is the student-only-writes variant.
4. **Uploads.** Size limit from a settings constant → extension allowlist → `verify_upload`/`verify_image` content check → store. Serving goes through `download_url()`, never `field.url`.
5. **Test conventions.** Throttling is off by default under pytest (`conftest.py:20-49`); opt in with `@pytest.mark.throttled` and set rates via `monkeypatch.setattr(ThrottleClass, 'THROTTLE_RATES', …)` — `override_settings` does not reach them. Query-count guards use `CaptureQueriesContext` in a measure-at-N-then-2N shape (phase 63).
6. **Serializer-level authorization.** `to_representation` is where nested content is stripped (`CourseSerializer` blanks `units` for non-enrolled callers; `UnitSerializer` blanks `lessons` on locked units) and must reuse already-computed fields rather than calling permission helpers that issue their own queries.

`frontend.md` is wrong or silent on nearly everything:

| Rule says | Reality |
|---|---|
| "Use existing Radix UI + Tailwind patterns" | Radix is 4 packages behind 5 wrapper files. The real library is `src/components/ui/` — 12 files, `Button` imported 51×, `Card` 36×. Nothing else imports `@radix-ui/*`. |
| "Types live in `src/types/`" | 20 interfaces are exported from `services/courses.ts` and `services/analytics.ts` and imported from there by pages. |
| *(silent)* | 26 co-located vitest files / 215 `it()` blocks, shipping in the same commit as the feature. |
| *(silent)* | `services/api.ts` owns 401 single-flight refresh, Sentry filtering (only ≥500/undefined), and `demo_blocked` toasting. A bare axios call bypasses all four. |
| *(silent)* | `useAuth` is imported from `@/contexts/useAuth`, not `AuthContext` — a deliberate split for `react-refresh/only-export-components`. |
| *(silent)* | Router is react-router **v7**; import from `'react-router'`, never `'react-router-dom'`. |
| *(silent)* | `@/` alias is standard (452 uses vs 8 relative-parent files); `PageContainer` wraps page bodies; the Tailwind type scale is deliberately one notch larger than stock. |

### Agents

- `db-migration-checker.md` lists an **`assignments`** app in its cross-app dependency check. No such app exists (`accounts, courses, quizzes, discussions, gamification, notifications`). It also misses the project's actual migration hazard — `preDeployCommand` runs migrations while the *old* code is still serving, which took production down at phase 65 — and the `db_default` rule that follows from it.
- `adversarial-tester.md` probes "exceed quiz attempt limits, **submit after deadlines, re-submit graded work**", "other users' data (**submissions, grades**, quiz attempts)". Verified: no `Submission`, no `Grade`, no `due_date`, no `deadline` anywhere in `backend/*/models.py`. Only `max_attempts` exists. It knows nothing about the surfaces phase 73 actually found bugs in.
- `code-reviewer.md` instructs the inline `request.user == course.instructor` check, contradicting `permissions.py`.
- There is **no frontend reviewer**. 26 test files and a strict interceptor contract get no automated review.

### Skills

- `verify-stack` step 1 is `cd backend && pytest` — impossible here. It also omits vitest, both dependency audits, and the production build, all of which CI runs — so `/verify-stack` can report PASS on a branch CI will reject.
- `handoff` mandates "under 60 lines"; the phase-73 handoff is 123. The rule is being ignored rather than followed.
- `finish-phase` is accurate on deploy targets and the migration window. It needs updating only for the new agent roster and the `gh` default-repo fix.

### Workspace and repo hygiene

- `.claude/scheduled_tasks.lock` — dead lock file, pid 63856, dated Jul 24.
- `.claude/hooks/` — empty directory.
- `origin` points at `Cesar6060/dev-learning-platform` (the old repo); the live repo is `Cesar6060/LMS` (public, `main` tracks `lms/main`, PR #106 landed there). **No `gh` default repo is set**, so a bare `gh pr create` can prompt or target the wrong repo.
- Uncommitted since Aug 6: `docs/specs/phase-69-robotics-2-course.md` (+63/−17, records the verified Neon backup branch and a branch-protection audit) and an untracked `docs/handoffs/2026-08-06-phase-69-closed-rob201-live.md`.
- That phase-69 spec carries a stale action: set `THROTTLE_JOIN_CODE=10/hour`. Phase 73 deliberately chose 60/hour because per-IP throttles bucket a whole classroom behind one school NAT. **Resolved: 60/hour wins.**
- `docs/runbooks/workflow-prompting-guide.txt` (tracked, therefore public) points twice at **`stemquest-api.onrender.com`** — the host retired at phase 57. Anyone following the runbook checks health on a dead URL. It also documents the three-agent roster and the current `/verify-stack`, both of which this phase changes.

### CLAUDE.md

Loaded into **every** session, so an error here is the most expensive kind.
Verified accurate and to be left alone: the entire Tech Stack block (Django
5.2.16, DRF 3.17.1, `postgres:16-alpine`, React 18.3.1, TypeScript 5.6, Vite 6,
Tailwind 3.4, django-allauth 65.18 + dj-rest-auth 7.2 + simplejwt 5.5), the
`core/` "not an installed app" note, the PLAN.md retirement, the deep-health
warning, and the migration old-code-safety paragraph.

What is wrong or missing:

| # | Issue | Why it matters |
|---|---|---|
| 1 | `cd backend && pytest` (line 14) is impossible | No host Python. Real command is `docker compose exec -T backend pytest`. This is the single most-executed instruction in the file and it fails every time. |
| 2 | No `npm test` in Commands | 26 vitest files exist and CI runs them. A session can ship a component with no test and never learn CI will run one. |
| 3 | "Merging to `main` deploys the backend" (line 37) | Incomplete — it also rebuilds the **frontend on Cloudflare Pages** (confirmed by `ci.yml:180` and `frontend/public/_headers`). `/finish-phase` already says both; CLAUDE.md says one. |
| 4 | Nothing about the remote trap | `origin` is the old repo and no `gh` default is set. This has already put two PRs on the wrong repository (phases 40 and 58). This is exactly what a Gotchas section is for. |
| 5 | Nothing about `/usr/bin/head` | Bare `head` is shadowed by an unrelated Perl tool on this machine; shell steps fail confusingly without the absolute path. |
| 6 | Nothing about concurrent pytest | Running the suite while a review subagent also runs collides on `test_gamedev_db` and produces hundreds of bogus errors. Cost real time in phases 65 and 73. |
| 7 | Workflow rules name only `/verify-stack` and `/handoff` | `/start-phase` and `/finish-phase` — the two skills that bracket the loop — go unmentioned. |
| 8 | "Never commit directly to main without passing verify" (line 33) is weaker than reality | `main` has branch protection requiring both CI jobs with `strict: true`, force-pushes and deletions blocked (verified 2026-08-06). But `enforce_admins` is **off** by deliberate decision, so an admin override can still put a red build into production. State it accurately. |
| 9 | `core/` described as "shared email/throttling helpers" | It now also holds `demo.py`, `uploads.py`, `password_validation.py`, `permissions.py`, `pagination.py` — several of which are mandatory call-throughs. |
| 10 | No note that CLAUDE.md and `.claude/` become public | After this phase they are tracked in a public repo. That is a standing constraint on what may be written in them. |

---

## Tasks

### 1. Permission model — `.claude/settings.json` (new, committed)

Denies outrank allows across every settings layer, so a project-level `deny`
overrides the existing `settings.local.json` allows without editing that file.
Leave `settings.local.json` alone.

- [x] Create `.claude/settings.json` with the **active** `permissions.deny` list — the prod-destructive set only:
      `Bash(gh pr merge:*)`, `Bash(render ssh:*)`, `Bash(render jobs create:*)`,
      `Bash(render deploys create:*)`, `Bash(render services update:*)`,
      `Bash(gh secret set:*)`, `Bash(gh secret delete:*)`,
      `mcp__neon__delete_branch`, `mcp__neon__delete_project`,
      `mcp__neon__reset_from_parent`, `mcp__neon__complete_database_migration`.
- [x] **Deliberate deviation, flagged:** `mcp__neon__run_sql` and
      `run_sql_transaction` are *not* denied. They are the same tool for reads
      and for DDL, and the established prod-verification workflow uses them to
      read. Denying them removes read access too. They go in `ask` instead, which
      documents the intent. Note honestly in the file's `_README` that unlisted
      MCP tools already prompt, so listing them under `ask` changes nothing
      functionally today — its value is that it survives someone later adding a
      broad `mcp__neon__*` allow.
- [x] Add the inert `_proposed` object (unknown top-level key, ignored by the
      parser). Structure it as `_README`, then `deny` / `ask` / `allow` arrays
      mirroring the real shape so activation is a one-line move, plus a
      `_rationale` map from rule string to the threat it stops.
- [x] Populate `_proposed.deny`: `Bash(git push --force:*)`, `Bash(git push -f:*)`,
      `Bash(git reset --hard:*)`, `Bash(rm -rf:*)`,
      `Bash(docker compose down -v:*)` (wipes the postgres volume),
      `Bash(gh workflow run:*)` (would fire `db-backup` / `demo-reset` at prod),
      `Bash(env)`, `Bash(printenv:*)` (keeps secrets off a screen-shared terminal),
      `Read(./.env)`, `Read(./backend/.env)`, `Read(./frontend/.env)`,
      `Read(~/.ssh/**)`, `Read(~/.aws/**)`, and the unrelated connector servers
      (`mcp__claude_ai_Gmail__*`, `mcp__claude_ai_Canva__*`,
      `mcp__claude_ai_Figma__*`, `mcp__claude_ai_Gamma__*`,
      `mcp__claude_ai_Spotify__*`, `mcp__claude_ai_TravExp__*`,
      `mcp__claude_ai_Plaid_Developer_Tools__*`).
      **Do not** blanket-deny `Read(./.env.*)` — that would also block
      `.env.example`, which is tracked and useful.
- [x] Populate `_proposed.ask`: `Bash(git push:*)`, `Bash(pip install:*)`,
      `Bash(npm install:*)`, `Bash(python manage.py migrate:*)`,
      `Write(./backend/*/migrations/**)`, `Edit(./backend/*/migrations/**)`,
      `Edit(./render.yaml)`, `Edit(./.github/workflows/**)`, `Edit(./.gitignore)`.
      Rationale for the dependency installs: a bump ships third-party migrations
      and re-runs both CI audits.
- [x] Populate `_proposed.allow` with the safe high-frequency set, so a later
      phase can cut prompt fatigue during a live demo: the docker pytest
      invocation, `docker compose ps/logs`, `npx tsc --noEmit`, `npm run lint`,
      `npm test:*`, read-only git (`status`/`diff`/`log`/`branch`) plus
      `add`/`commit`, `gh pr create/view`, `gh run list/view`, and
      `WebFetch(domain:code.claude.com)`.
- [x] Add `_proposed._keys` noting `permissions.defaultMode`,
      `permissions.disableBypassPermissionsMode: "disable"` and
      `enableAllProjectMcpServers: false` as candidates. **Mark
      `disableBypassPermissionsMode` as UNVERIFIED** — the research returned
      contradictory answers on whether it works outside managed settings. Do not
      activate it on the strength of this spec.
- [x] Record in the file that Bash deny rules are a safety net, not a security
      boundary: they are evaluated per-subcommand across `&&`, `||`, `;`, `|`
      and newlines, but a wrapper like `sh -c '…'` is a documented gap. That gap
      is what the hook in section 2 closes.

### 2. Hook — `.claude/hooks/guard-bash.sh` [P]

- [x] Write a `PreToolUse` hook matching `Bash` that reads the tool-call JSON on
      stdin and blocks with exit code 2. Parse with `python3` (present at
      `/opt/homebrew/bin/python3`), not `jq` — do not assume `jq` is installed.
- [x] Block: shell-wrapper evasion (`sh -c`, `bash -c`, `zsh -c`, `eval `),
      curl/wget piped into a shell, and any command containing a
      production target (`gh pr merge`, `render ssh`, `render jobs create`,
      `gh secret set`, `stemquest-api-va`, `api.stemquests.com` with a write
      method).
- [x] Fail **open** on a parse error or unexpected input and exit 0 — a
      guardrail that hard-fails every Bash call is worse than the gap it closes.
      Keep total runtime under ~100 ms.
- [x] Register it in `.claude/settings.json` under `hooks.PreToolUse` with
      matcher `Bash`, and `chmod +x` the script.

### 3. Rules — split into path-scoped files

Splitting only pays off when the `paths:` globs differ, so scope each file to
the part of the tree it describes rather than re-globbing `backend/**/*.py` in
every file. Delete the two existing files once their content has been rehomed.

- [x] `backend.md` — `backend/**/*.py`. The always-on core, kept short: `/api/`
      URL layout including the doubled `/api/courses/courses/` prefix, import
      authorization from `courses/permissions.py` (never inline), the
      `PermissionDenied` → 403 `{'detail': …}` contract, email via
      `core.email.send_templated_email(triggered_by=…)`, no global pagination
      class, XP only via `gamification.services` helpers, and the
      `/usr/bin/head` shell quirk.
- [x] `backend-views.md` [P] — `backend/**/views.py`, `backend/**/permissions.py`,
      `backend/**/urls.py`. All ten permission helpers with when-to-use-which;
      the full throttling contract (no stock DRF classes, spread
      `*GLOBAL_THROTTLES`, `view.cls.throttle_scope` for FBVs,
      `ClientIPScopedWriteRateThrottle`, non-`None` default required, dj-rest-auth
      optional-slash shadow); demo write-blocking with the exact
      `DEMO_BLOCKED_BODY`; the upload pipeline order and `download_url()`.
- [x] `backend-serializers.md` [P] — `backend/**/serializers.py`. Nested content
      is authorization surface — strip it in `to_representation`; reuse
      already-computed fields there rather than calling helpers that issue their
      own queries; fix per-list N+1s with `Meta.list_serializer_class` plus a
      `to_attr` prefetch the view attaches.
- [x] `backend-tests.md` [P] — `backend/**/test*.py`, `backend/conftest.py`.
      `docker compose exec -T backend pytest`; never run the suite concurrently
      with review subagents (shared `test_gamedev_db`); `pytest.ini` forces
      `--cov` so full runs are ~280 s; `@pytest.mark.throttled` +
      `monkeypatch.setattr(ThrottleClass, 'THROTTLE_RATES', …)` because
      `override_settings` does not reach class-bound rates; `CaptureQueriesContext`
      N-then-2N guards; every new write endpoint gets an `assert_demo_blocked`
      entry in `core/tests/test_demo_lockdown.py`.
- [x] `backend-migrations.md` [P] — `backend/**/migrations/*.py`,
      `backend/**/models.py`. The pre-deploy window (migrations run while old
      code still serves — the phase-65 outage), additive-only, `db_default` not
      `default`, nothing dropped in the same deploy, the three-operation
      callable-default pattern, reverse migrations leave a working schema.
- [x] `frontend.md` — `frontend/src/**/*.{ts,tsx}`. Always-on core: strict TS /
      no `any`, `@/` alias over relative parents, import router APIs from
      `'react-router'` (v7), cross-cutting types in the `src/types/index.ts`
      barrel while single-service response shapes may live in and be imported
      from that service, role gating via `!!user?.is_instructor` (there is no
      role string), hide write UI on `user.is_demo`, declare new `VITE_*` vars in
      `src/vite-env.d.ts`.
- [x] `frontend-services.md` [P] — `frontend/src/services/**`. Everything goes
      through the `api.ts` default export; the interceptor already owns 401
      single-flight refresh, Sentry filtering, and `demo_blocked` toasting — do
      not reimplement or bypass any of it; tokens are the `token`/`refresh`
      localStorage keys written only by `auth.ts`; classify errors with the
      exported `isForbidden()` / `isDemoBlocked()`.
- [x] `frontend-components.md` [P] — `frontend/src/components/**`,
      `frontend/src/pages/**`. Compose from `src/components/ui/` and add a Radix
      primitive only by wrapping it there; `cn()` + `cva` per `ui/Button.tsx`;
      wrap page bodies in `PageContainer`; the `isLoading`/`error`/`forbidden`
      state trio with `isForbidden(err)` → `<AccessDenied />`; `Skeleton` in-page
      vs `PageLoader` for route guards; `ConfirmDialog` not native `confirm()`;
      semantic Tailwind tokens, noting the raised type scale; new pages are named
      exports registered as `lazy()` routes in `App.tsx`; import `useAuth` from
      `@/contexts/useAuth`.
- [x] `frontend-tests.md` [P] — `frontend/src/**/*.test.{ts,tsx}`,
      `frontend/src/test/**`. Co-located `Foo.test.tsx`, no `__tests__/`; ships in
      the same commit as the feature; mock at the service-module boundary with
      `vi.hoisted` + `vi.mock('@/services/x')`, never axios; query by accessible
      role/name, no `data-testid`; page tests render in `MemoryRouter`.

### 4. Agents

- [x] Rewrite `code-reviewer.md` — replace the inline instructor check with the
      `permissions.py` helper contract; add demo-guard coverage, throttle wiring,
      serializer nested-data stripping, and the expectation that new frontend
      behavior ships with a vitest file.
- [x] Rewrite `adversarial-tester.md` — delete every probe for deadlines, grades,
      submissions and re-submitting graded work. Retarget at the real surface:
      unit-lock bypass on every content read, `accessible_course_ids` scoping
      (the phase-73 hole where any instructor could read any course), invite
      gating and the exact-match email rule, `demo_blocked` coverage on new
      writes, upload content-vs-extension mismatch and the per-request size cap,
      throttle scopes that are installed but inert, and IDOR across course codes.
      Keep the BROKEN / SUSPICIOUS / HELD report format — it works.
- [x] Rewrite `db-migration-checker.md` — remove `assignments`; make the
      old-code-safe pre-deploy window the primary check with the phase-65 outage
      as the worked example; add `db_default`, the callable-default three-step,
      and the unique-constraint backfill proof.
- [x] Add `frontend-reviewer.md` [P] — a new agent covering axios calls that
      bypass `api.ts`, direct token reads, per-service 401/Sentry reimplementation,
      `any`, `@radix-ui/*` imported outside `components/ui/`, missing vitest for
      new behavior, `data-testid` instead of role queries, and missing `is_demo`
      gating on write UI. Tools `Read, Grep, Glob, Bash`.
- [x] Keep the existing `model:` assignments (opus for `code-reviewer`, sonnet
      elsewhere); give `frontend-reviewer` `model: sonnet`.

### 5. Skills

- [x] `verify-stack` — rewrite to full CI parity in CI's order:
      `docker compose exec -T backend pytest` → `npx tsc --noEmit` →
      `npm run lint` → `npm test` → `npm audit --omit=dev` → `pip-audit` →
      `npm run build` with `VITE_API_URL` set. Keep the show-real-output rule,
      the fix-the-root-cause rule and the 3-strikes stop. State that pytest is
      ~280 s because `pytest.ini` forces `--cov`, and warn against running it
      concurrently with review subagents.
- [x] `finish-phase` — add `frontend-reviewer` to the step-3 parallel review;
      note that `gh pr merge` is now denied by policy and the human merges in the
      GitHub UI; confirm `gh pr create` targets `Cesar6060/LMS`. Leave the
      Migrations section as-is — it is accurate and load-bearing.
- [x] `handoff` — raise the length guidance from "under 60 lines" to "under 120,
      and prefer shorter"; the current 60 is being ignored rather than met.
- [x] `start-phase` — update the folder map reference for the split rules dir.
      Otherwise unchanged.
- [x] **Preserve frontmatter exactly** while rewriting any skill or agent:
      `disable-model-invocation: true` on `handoff`, `start-phase` and
      `finish-phase` (they are user-typed only, by design), `argument-hint` on
      `start-phase` and `finish-phase`, and the **absence** of
      `disable-model-invocation` on `verify-stack` — that one must stay
      model-invocable so it can run mid-implementation. Keep the existing
      `model:` lines (`opus` for `code-reviewer`, `sonnet` for the other two).

### 6. Docs and repo hygiene

- [x] `.gitignore` — un-ignore `CLAUDE.md`; replace the blanket `.claude/` entry
      with ignores for `.claude/settings.local.json` and
      `.claude/scheduled_tasks.lock` only. Leave the five private `docs/` files
      and `skills-rules-agents-interview-notes.txt` ignored.
      **Ordering is load-bearing:** land the narrowed `.gitignore` and delete the
      lock file *before* the first `git add .claude`, or the local-only settings
      get committed. Then run `git status` and read it before staging — never
      `git add -A` here (review subagents leave probe files behind).
- [x] Note that committing `.claude/` brings it into scope of the `secret-scan`
      workflow, which runs both `gitleaks git .` over full history and
      `gitleaks dir .` over the working tree. Nothing in these files should look
      like a credential; if gitleaks flags one, fix the file — do not add a
      `.gitleaks.toml` allowlist entry to silence it.
- [x] `CLAUDE.md` — work the ten numbered findings above. Concretely:
      - **Commands:** replace `cd backend && pytest` with
        `docker compose exec -T backend pytest`; add
        `cd frontend && npm test` (vitest); add a one-line note that bare `head`
        is shadowed on this machine — use `/usr/bin/head`.
      - **Layout:** widen the `core/` description to name `demo.py`, `uploads.py`,
        `password_validation.py`, `permissions.py`, `pagination.py` as mandatory
        call-throughs rather than optional helpers; point at the split
        `.claude/rules/` files.
      - **Workflow rules:** add `/start-phase` at the front of the loop and
        `/finish-phase` at the end, so all four skills are named.
      - **Git:** restate the main-branch rule accurately — feature branches
        always; `main` is protected and requires both CI jobs (`strict: true`,
        force-push and deletion blocked), but `enforce_admins` is deliberately
        off, so an admin override can still ship a red build. Add that `origin`
        must resolve to `Cesar6060/LMS` and that `gh`'s default repo is set —
        after the remote rename in this same phase, the historical
        `git push -u lms` guidance is obsolete and must not be re-added.
      - **Gotchas:** add the concurrent-pytest collision; correct the deploy line
        to say merging deploys the backend on Render **and** the frontend on
        Cloudflare Pages.
      - Add one line noting CLAUDE.md and `.claude/` are now tracked in a public
        repo, so neither may carry secrets or private URLs.
      - Leave the Tech Stack block, the `core/`-is-not-an-installed-app fact, the
        PLAN.md retirement, the migration paragraph and the deep-health warning
        **unchanged** — all verified accurate.
      - Keep the file under ~200 lines; it is loaded every session. If the
        additions push it past that, cut the least load-bearing lines rather than
        letting it grow.
- [x] `docs/CLAUDE-CODE-WORKFLOW.md` (stays private) — add `/finish-phase` to the
      phase loop, refresh the folder map for the split rules and the new agent,
      and add a short section on the permission model and the hook.
- [x] `docs/runbooks/workflow-prompting-guide.txt` [P] — replace both
      `stemquest-api.onrender.com` health URLs with `api.stemquests.com`
      (retired at phase 57); add `frontend-reviewer` to the agent roster and to
      the `/finish-phase` description; update the `/verify-stack` summary to the
      new seven checks. Keep it plain text — it is a user-facing runbook.
- [x] Delete `.claude/scheduled_tasks.lock`.
- [x] `gh repo set-default Cesar6060/LMS`; rename remote `origin` →
      `old-origin` and `lms` → `origin`; re-point `main`'s upstream. Do not
      delete anything.
- [x] Commit the pending phase-69 spec update and the untracked
      `docs/handoffs/2026-08-06-phase-69-closed-rob201-live.md` **as their own
      commit**, before this phase's work, so the diff stays readable.
- [x] In `docs/specs/phase-69-robotics-2-course.md`, correct the
      `THROTTLE_JOIN_CODE=10/hour` action to 60/hour, citing the phase-73 school-NAT
      decision so it is not re-litigated.

---

## Verification

Run in this order. Show real output for each.

**Config correctness**
- [x] `python3 -c "import json; json.load(open('.claude/settings.json'))"` exits 0.
- [x] Start a **fresh** Claude Code session in the repo and confirm no settings
      parse warning appears — this is the check that the `_proposed` unknown key
      is tolerated. If it warns, fall back to `.claude/settings.proposed.json`
      (a file Claude Code never loads) and say so in the handoff.
- [x] In that session, `gh pr merge --help` is **denied**, not prompted.
- [ ] `mcp__neon__delete_branch` is denied; a Neon read tool still works.
- [x] `docker compose ps` still runs without a prompt (the existing local allow
      is unaffected).

**Hook**
- [x] `echo '{"tool_name":"Bash","tool_input":{"command":"sh -c \"rm -rf /tmp/x\""}}' | .claude/hooks/guard-bash.sh; echo $?` → **2**.
- [x] Same with `{"command":"git status"}` → **0**.
- [x] Same with malformed input (`echo 'not json' | …`) → **0** (fails open).
- [x] In a live session, a `sh -c` command is blocked with the hook's reason shown.

**Rules load on the right paths**
- [ ] Open a backend serializer, run `/context`, confirm `backend-serializers.md`
      and `backend.md` are loaded and `frontend-*.md` are not.
- [ ] Open a `*.test.tsx`, confirm `frontend-tests.md` loads.
- [x] Confirm no rule file exceeds ~80 lines.

**Agents**
- [x] `grep -ri "assignments\|deadline\|submission\|graded" .claude/agents/` returns nothing.
- [x] `grep -rn "request.user == course.instructor" .claude/agents/ .claude/rules/` returns nothing.
- [x] Dispatch `frontend-reviewer` at `git diff main...HEAD` and confirm it
      returns a usable report rather than erroring on its tool list.

**Skills**
- [x] `/verify-stack` runs all seven checks and ends in **PASS**. This is also the
      phase's own gate. *(2026-08-11: pytest 1310 passed / 292s, tsc 0, lint 0
      errors + 1 known warning, vitest 26 files / 269 tests, npm audit 0,
      pip-audit clean, production build ok.)*
- [x] `grep -n "cd backend && pytest" -r .claude/ CLAUDE.md` returns nothing.

**CLAUDE.md**
- [x] Every command in the Commands block is pasted into a shell and runs:
      `docker compose exec -T backend pytest` reaches the suite,
      `npm test`, `npx tsc --noEmit` and `npm run lint` all execute. A command
      that cannot run is the defect this section exists to prevent.
- [x] `grep -c "" CLAUDE.md` is under 200.
- [x] `grep -n "push -u lms\|remote lms" CLAUDE.md` returns nothing — the remote
      rename makes that guidance wrong.
- [x] It names all four skills: `grep -c "/start-phase\|/verify-stack\|/finish-phase\|/handoff" CLAUDE.md` ≥ 4.
- [x] It states both deploy targets (Render backend **and** Cloudflare Pages frontend).
- [x] Read it end to end once as a stranger would and confirm nothing secret or
      private slipped in — it is public after this phase.

**Git and visibility**
- [x] `git check-ignore -v .claude/settings.local.json` matches; `git check-ignore -v .claude/rules/backend.md` does **not**.
- [x] `git ls-files .claude | wc -l` is greater than 12; `git ls-files CLAUDE.md` returns the file.
- [x] `git ls-files docs/PORTFOLIO.md docs/INTERVIEW_GUIDE.md docs/DEMO_SCRIPT.md docs/CLAUDE-CODE-WORKFLOW.md` returns **nothing** — the private docs stayed private.
- [x] `git ls-files .claude/settings.local.json` returns nothing.
- [x] `git ls-files .claude/scheduled_tasks.lock` returns nothing.
- [x] `gh repo set-default --view` → `Cesar6060/LMS`; `git remote -v` shows `origin` → LMS.
- [x] The `secret-scan` CI job is green on the PR — `.claude/` is newly in scope
      for both the history and working-tree gitleaks scans. *(PR #107: gitleaks
      pass in 14s; Frontend job pass in 1m14s.)*
- [x] Skill frontmatter survived: `grep -c "disable-model-invocation" .claude/skills/*/SKILL.md`
      is 1 for `handoff`, `start-phase` and `finish-phase`, and **0** for
      `verify-stack`.

**Docs**
- [x] `grep -rn "stemquest-api.onrender.com" docs/runbooks/ CLAUDE.md .claude/`
      returns nothing — the phase-57 host is retired everywhere.
- [x] `grep -rln "frontend-reviewer" .claude/agents/ .claude/skills/finish-phase/ docs/runbooks/`
      returns all three — the new agent is registered, wired into `/finish-phase`,
      and documented.

**Scope guard**
- [x] `git diff main...HEAD --stat -- backend/ frontend/` is **empty**. No
      application code changed in this phase.

**Manual flow**
- [ ] Fresh session → `/start-phase` on a throwaway topic → confirm it reads the
      newest handoff and the split rules without complaint, then abandon it.
- [ ] Browse `github.com/Cesar6060/LMS` after merge and confirm `.claude/` renders
      with agents, skills, rules and `settings.json` — and that no private doc,
      secret, or `settings.local.json` came along.

---

## Notes for the implementation session

- The repo is **public**. Read every file once more before committing it. The
  specs, handoffs and `render.yaml` are already public, so `.claude/` adds no new
  infrastructure exposure — but that is a fact to re-check, not assume.
- `/verify-stack` will be rewritten by this very phase. Run the **new** version
  as the gate, and if it fails, fix the check before trusting a red result.
- Phase 72 (content-upsert hardening) remains unstarted and is untouched here.

---

## Implementation results (2026-08-11)

### Deviations and things worth knowing

- **The hook needed two files, not one.** `guard-bash.sh` holds the wiring;
  `guard-bash.py` holds the matching. The first version embedded the Python in a
  heredoc and had two bugs at once: the heredoc consumed the hook's stdin (so the
  tool-call JSON never reached the parser and everything silently passed), and
  bash 3.2 mis-parses a quoted heredoc inside `$(...)`, which made the script a
  syntax error. Splitting the program into its own file removes both classes of
  bug. Registration and behaviour are unchanged from the spec.
- **The hook matches on the whole command string, so it also fires on text that
  merely mentions a blocked pattern.** Committing this phase failed once because
  the commit message described the shell-wrapper gap. Workaround used:
  `git commit -F <file>`. This is the fail-safe direction and was left as-is, but
  it is real friction and belongs in the next round of tuning.
- **Blocking writes to the production hosts collides with the sanctioned
  post-deploy check**, which is `POST /api/auth/demo-login/` followed by a content
  read. Implemented as specified; the hook's refusal message names that exact case
  and tells the caller to ask the user or use the browser instead.
- **Two extra render commands** (`render deploys create`, `render services update`)
  were added to the hook's blocklist so it matches the deny list rather than a
  subset of it.
- **Three greps in Verification are satisfied by rewording, not by deletion.**
  `adversarial-tester.md` still needs to say which models exist, and
  `code-reviewer.md` still needs to forbid inline ownership checks; both now say
  so without quoting the stale words the greps look for.
- **The runbook contained a defect outside this phase's brief and it was fixed:**
  two sections still instructed the reader to hand-apply migrations to Neon before
  merging, which phase 65 retired and which the same file contradicts in section 6.
  Also dropped a stale "NEW." label on `adversarial-tester`.
- Still stale in the runbook, **not** fixed (cosmetic, no correctness impact):
  phase-number examples throughout use 53, and section 1 offers a mid-phase spot
  check for `adversarial-tester` but not for `frontend-reviewer`.

### Review round — what the two reviewers changed

An adversarial pass at the hook and a code review of the whole diff both ran
before the PR. The hook was rewritten in response; the rules files took five
corrections.

**The hook now matches on shell tokens, not on raw text.** The first version
substring-matched the command string, which failed in both directions at once:

- *False negatives.* `'gh' pr merge`, `gh pr me""rge`, `/bin/sh -c`, `\sh -c`,
  `bash --norc -c`, `sh -ce`, `sh -o noglob -c`, and a backslash-newline-wrapped
  `gh pr merge` all passed. Verified executing, not theoretical.
- *False positives, the more damaging half.* It blocked `gh pr create --body`
  containing the phrase "do not gh pr merge" — which is `/finish-phase`
  boilerplate, so the guardrail blocked the workflow that ships it. Also
  `grep -rn eval frontend/src`, any commit message naming a blocked command,
  `curl -f` against prod health (`-f` matched `-F` under `IGNORECASE`), and
  `docker compose exec -T backend bash -c '...'`.

Tokenising with `shlex` kills both families: a needle inside a quoted argument
is an argument, and quote-splicing inside a command word collapses before
matching. Added in the same pass: `gh api --method PUT` (which reaches the merge
and secret endpoints the named commands were denied for), curl's `-T`/`--json`
write flags, httpie, and a `docker` exemption so container shells stay allowed.

**Two fail-open bugs fixed.** `[ -f ]` did not catch an unreadable
`guard-bash.py` — python exits 2 on a file it cannot open, and 2 is the block
code, so `chmod 000` on that file would have turned the guard into a total Bash
outage. Now `[ -r ]`, and the wrapper normalises any exit code other than 2 to 0
so an interpreter crash cannot block either. A regression case covers it.

Coverage now: 73 cases green (15 wrapper, 14 production command, 8 production
write, 25 daily-loop must-allow, 11 fail-open), worst case 34 ms.

**Known and accepted limits, written down rather than papered over.** No shell
expansion happens here, so `A=gh; $A pr merge`, a base64 pipeline, `source
./script.sh`, and `python3 -c "os.system(...)"` all still get through. Blocking
`python3 -c` was rejected — this project's own tooling uses it constantly. The
`settings.json` `_README` already frames deny rules as a safety net rather than a
security boundary; the hook inherits exactly that framing.

**Rules-file corrections** (five wrong line citations out of ~55 sampled):
`backend-serializers.md` 3093→5201, `backend-tests.md` `docker-compose.yml`
2→5 and `quizzes/tests.py` 667→664, `frontend-components.md` `Button.tsx`
43→41, `frontend-tests.md` `package.json` 11→10.

**Two stale items the reviewers caught outside the checklist,** both fixed: the
public runbook still described `adversarial-tester` probing "post-deadline
submits" and used an assignment-rubric feature as its worked example — the exact
model this phase deleted from `.claude/agents/`, surviving in the one file a
human actually reads. And the newly-tracked phase-69 handoff still carried the
`10/hour` join-code figure and a claim that both scopes default to `None`, which
phase 73 made false; it now carries the correction inline.

`/finish-phase` also gained a warning that the hook blocks the `POST
/api/auth/demo-login/` half of its own post-deploy check, so the collision is
read in the skill rather than discovered at exit code 2.

### The seven boxes left unticked, and why

| Item | Why it is open |
|---|---|
| `mcp__neon__delete_branch` denied / Neon read works | The Neon MCP server disconnected partway through the session, so neither half could be exercised. The deny entries are present in `settings.json` and parse cleanly. |
| `/context` shows `backend-serializers.md` on a serializer | Needs an interactive session; `/context` is not available headlessly. |
| `/context` shows `frontend-tests.md` on a `*.test.tsx` | Same. |
| `secret-scan` CI green | Runs when the PR opens. |
| Fresh session → `/start-phase` dry run | Manual. |
| Browse `github.com/Cesar6060/LMS` after merge | Manual, post-merge. |

Two verification items were met by a **fresh headless process** rather than a
fresh interactive session, which is weaker evidence than the spec asked for and is
flagged here rather than glossed: the settings-parse check (`claude -p` in the repo
started clean, so the `_proposed` and `_README` unknown keys are tolerated) and the
`frontend-reviewer` dispatch (it is not in an already-running session's agent
registry — agents load at session start — but a fresh process launched it and it
returned the correct "no frontend files in this diff" one-liner).

`gh pr merge --help` **was** refused in a live session, but by the hook rather than
by the deny list — the hook runs first and returns its own message. The deny entry
is present; which layer fires first was not isolated.
