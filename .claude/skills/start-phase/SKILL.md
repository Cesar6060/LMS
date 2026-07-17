---
name: start-phase
description: Interview the user and write a phase spec before any implementation begins. Run at the start of each new phase.
disable-model-invocation: true
argument-hint: [phase-number-or-name]
---

You are starting a new phase: $ARGUMENTS

Do NOT write any implementation code during this skill. Follow these steps:

1. Read the most recent file in `docs/handoffs/` for current project state.
2. Read ONLY the section of PLAN.md for this phase (search for the phase heading — do not read the whole file).
3. Use subagents (Explore) to investigate the parts of the codebase this phase touches. Report what exists already and what patterns to follow.
4. Interview the user with AskUserQuestion. Dig into the hard parts: edge cases, UI/UX decisions, permission boundaries (instructor vs student), data model tradeoffs. Don't ask obvious questions. Keep going until scope is unambiguous.
5. Write the spec to `docs/specs/phase-<N>-<name>.md` with:
   - **Goal** — one paragraph
   - **Out of scope** — explicit list
   - **Backend tasks** — models, migrations, endpoints (with URL patterns and permission checks), as a checklist
   - **Frontend tasks** — types, services, components, pages, as a checklist
   - **Verification** — the exact checks that prove the phase works end to end (specific pytest cases, tsc, a manual flow to click through)
6. Tell the user to review the spec, then start a FRESH session (or /clear) and prompt:
   "Read docs/specs/phase-<N>-<name>.md and implement it. Work through the checklist in order. Run /verify-stack before marking anything complete."
