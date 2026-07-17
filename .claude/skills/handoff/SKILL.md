---
name: handoff
description: Write a session handoff file so the next Claude session can pick up with zero re-explaining. Run at the end of every work session.
disable-model-invocation: true
---

Write a handoff file at `docs/handoffs/YYYY-MM-DD-<short-topic>.md` (use today's date). Keep it under 60 lines. Use exactly this structure:

# Handoff: <topic>

## Current state
What phase we're in, what was completed this session (files created/modified with paths), and what verified checks passed (pytest, tsc, lint).

## In progress / not done
Anything half-finished, with the exact file and what remains.

## Next steps
Numbered, in priority order. Be specific enough that a fresh session needs no other context.

## Decisions made
Choices made this session and WHY (e.g., "used X pattern because Y"). This prevents the next session from relitigating them.

## Gotchas discovered
Anything surprising that cost time this session (env quirks, flaky tests, ordering requirements).

## Files to read first
The 3-5 files a fresh session should read before touching anything.

---

After writing the file, also:
1. Update the current phase spec in `docs/specs/` — check off completed items.
2. Tell the user the handoff path and suggest they start the next session with:
   "Read docs/handoffs/<filename> and continue from Next steps."
