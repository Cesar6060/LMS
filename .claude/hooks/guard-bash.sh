#!/bin/bash
# PreToolUse hook for Bash. Closes the gap the deny list cannot cover.
#
# permissions.deny in .claude/settings.json matches per-subcommand across &&, ||,
# ;, | and newlines — but a wrapper like `sh -c 'gh pr merge 106'` hides the real
# command inside a string argument and slips through. This hook reads the raw
# tool call and looks at the whole command text.
#
# Contract: exit 2 blocks the call and shows stderr to Claude. Exit 0 allows it.
# It FAILS OPEN on anything it does not understand — a guardrail that hard-fails
# every Bash call would be worse than the gap it closes. No network, no disk
# writes, one python3 process: well under 100 ms.
#
# The matching itself lives in guard-bash.py, parsed with python3 rather than jq
# on purpose — jq is not guaranteed to be installed on this machine, python3 is.
# Keeping the program in its own file (instead of a heredoc) avoids bash 3.2's
# heredoc-inside-command-substitution quoting bug, which silently broke an
# earlier version of this hook.

set -u

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD_PY="$HOOK_DIR/guard-bash.py"

# Missing program: fail open rather than blocking every Bash call.
[ -f "$GUARD_PY" ] || exit 0

PY=""
for candidate in "$(command -v python3 2>/dev/null)" /opt/homebrew/bin/python3 /usr/bin/python3; do
  if [ -n "$candidate" ] && [ -x "$candidate" ]; then
    PY="$candidate"
    break
  fi
done

# No interpreter: fail open.
[ -z "$PY" ] || exec "$PY" "$GUARD_PY"
exit 0
