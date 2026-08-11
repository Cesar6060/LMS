# Handoff: Phase 74 — workflow modernization and Claude Code guardrails

## Current state
**PR #107 is open against `Cesar6060/LMS`, not merged.**
https://github.com/Cesar6060/LMS/pull/107 — branch `phase-74-workflow-guardrails`,
three commits: `b59a312` (pending phase-69 docs, landed first so the phase diff
stays readable), `65ac40f` (the phase), `8a573d8` (review fixes).

`/verify-stack` **PASS**, all seven: pytest **1310 passed** / 292s / 97% cov,
tsc 0, lint 0 errors (1 known `react-refresh` warning), vitest **26 files / 269
tests**, `npm audit --omit=dev` 0, `pip-audit` clean, production build ok. The
frontend three were re-run after the review fixes; pytest was not, because no
Python file changed — `git diff main...HEAD --stat -- backend/ frontend/` is
**empty**, so no application code shipped in this phase.

What shipped:
- **`.claude/settings.json`** (new, committed). Active deny: the 11
  prod-destructive rules. Denies outrank allows everywhere, so the pre-approvals
  in the gitignored `settings.local.json` are overridden without touching it.
  `mcp__neon__run_sql` sits in `ask`, not `deny` — same tool for reads and DDL,
  and prod verification reads with it. Inert `_proposed` tier stages the next
  round with a per-rule threat rationale.
- **`.claude/hooks/guard-bash.sh` + `.py`** — `PreToolUse` guard on `Bash`,
  closing the shell-wrapper gap the deny list cannot match. 73 cases green,
  34 ms worst case, fails open on anything it cannot parse.
- **Rules split 2 → 9 files**, path-scoped, all ≤80 lines, every claim
  re-verified against current code.
- **Agents**: `code-reviewer`, `adversarial-tester`, `db-migration-checker`
  rewritten against the real surface; new **`frontend-reviewer`**.
- **Skills**: `verify-stack` at full CI parity (7 checks); `finish-phase` gains
  the third reviewer and the default-repo check; `handoff` 60 → 120 lines;
  `start-phase` points at the split rules.
- **`.gitignore` narrowed** — `CLAUDE.md` + 20 `.claude/` files now tracked;
  `settings.local.json`, the lock file and the five private `docs/` files stayed
  out (verified with `git ls-files`). `CLAUDE.md` itself rewritten around the ten
  audit findings, 74 lines.
- **Hygiene**: remotes renamed (`origin` → LMS, old repo kept as `old-origin`),
  `gh repo set-default Cesar6060/LMS`, lock file deleted, retired
  `stemquest-api.onrender.com` URLs replaced.

## In progress / not done
1. **Nothing blocking.** CI was still running when this was written — check
   `gh pr checks 107` before merging. `secret-scan` matters most: `.claude/` is
   newly in scope for both the history and working-tree gitleaks scans.
2. Six spec verification boxes remain open, all recorded in the spec's
   "Implementation results" table: two `/context` checks, `secret-scan` green,
   the Neon deny check, a `/start-phase` dry run, and browsing the repo after
   merge.
3. The settings-parse check and the `frontend-reviewer` dispatch were met by a
   fresh **headless** process, not a fresh interactive session — weaker evidence
   than the spec asked for.

## Next steps
1. **Merge PR #107 in the GitHub UI** once CI is green. Claude cannot — and
   should not — do this; `gh pr merge` is now denied by policy and blocked by the
   hook.
2. **First interactive session after merge: run the two `/context` checks.** Open
   a backend serializer, confirm `backend-serializers.md` + `backend.md` load and
   no `frontend-*.md` does; open a `*.test.tsx`, confirm `frontend-tests.md`
   loads. The entire payoff of splitting nine rules files rests on those `paths:`
   globs actually scoping the loads, and nothing so far proves it.
3. **Confirm `mcp__neon__delete_branch` is denied and a Neon read still works.**
   That MCP server disconnected mid-session so neither half was exercised.
4. Phase 72 (content-upsert hardening) is still unstarted.
5. Carried owner actions, untouched: Neon `production` `protected: false`;
   `_dmarc` + root SPF absent; invite-deliverability test; JAVA101 answer
   rotation; exercising join-code/invite-link against prod once.

## Decisions made
- **`mcp__neon__run_sql` is not denied.** One tool for reads and DDL; denying it
  removes the prod-verification read path. It goes in `ask`, which changes
  nothing functionally today (unlisted MCP tools already prompt) but survives
  someone later adding a broad `mcp__neon__*` allow.
- **The hook matches shell tokens, not raw text.** Substring matching failed both
  ways at once: `'gh' pr merge` and `gh pr me""rge` got through, while
  `gh pr create --body "do not gh pr merge"` — `/finish-phase` boilerplate — was
  blocked, as were `grep -rn eval`, `curl -f` against prod health, and
  `docker compose exec ... bash -c`. `shlex` kills both families.
- **`python3 -c` is deliberately NOT blocked** even though it is the same evasion
  class as `sh -c`. This project's tooling uses it constantly; blocking it would
  make the hook the thing someone disables. Recorded as a known limit alongside
  variable indirection, base64 pipelines and `source`.
- **Deny rules are a safety net, not a security boundary.** Stated in
  `settings.json`'s `_README` and inherited by the hook.
- **The hook blocks the `POST /api/auth/demo-login/` half of the post-deploy
  check.** Kept, because prod writes from a session are exactly what it exists to
  stop; `/finish-phase` now warns, and the refusal message names the case.
- **Join-code throttle stays 60/hour** (phase 73). The phase-69 spec and handoff
  both said 10/hour; both now carry the correction. Per-IP idents bucket a whole
  classroom behind one school NAT.

## Gotchas discovered
- **The hook is live the moment `settings.json` is saved** — mid-session, no
  restart. It then blocks any Bash command whose *text* contains a blocked
  pattern, which broke `git commit -m` with a message about the hook. Use
  `git commit -F <file>`. (Token matching fixed the quoted-argument cases, but a
  needle as a bare command word in any position still blocks.)
- **New agents and rewritten agent files are NOT picked up mid-session.** The
  registry loads at session start, so `frontend-reviewer` had to be smoke-tested
  from a fresh `claude -p` process, and dispatching `code-reviewer` mid-session
  would have run the *old* prompt.
- **bash 3.2 mis-parses a quoted heredoc inside `$(...)`.** A heredoc on the
  interpreter also eats the hook's stdin, so the tool-call JSON never arrives and
  everything silently passes. Keep hook programs in their own file.
- **`[ -f ]` is not enough for a fail-open guard.** `python3` exits 2 on a file it
  cannot open and 2 is the block code, so an unreadable program is a total Bash
  outage. Use `[ -r ]` and normalise any non-2 exit to 0.
- Review subagents catch wrong `file:line` citations well — 5 of ~55 sampled were
  wrong. Do not trust a citation because an agent wrote it.

## Files to read first
1. `docs/specs/phase-74-workflow-and-guardrails-audit.md` — the audit, the
   checklist, and an "Implementation results" section with every deviation, the
   review round, and the open items.
2. `.claude/settings.json` — the permission model, including the `_README` that
   explains what it is and is not.
3. `.claude/hooks/guard-bash.py` — what it catches and, more importantly, what it
   does not.
4. `CLAUDE.md` (rewritten, loaded every session) and `.claude/rules/` — nine
   files now, with `backend.md` and `frontend.md` as the always-on cores.
