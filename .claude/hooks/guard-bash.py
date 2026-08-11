"""Bash guard for the PreToolUse hook. Invoked by guard-bash.sh.

Reads the tool-call JSON on stdin. Exit 2 blocks the call and shows stderr to
Claude; exit 0 allows it. Anything unexpected falls through to exit 0 — see the
fail-open note in guard-bash.sh.
"""

import json
import re
import sys

# Unconditionally blocked: these do something to production and nothing else.
PROD_COMMANDS = (
    ('gh pr merge', 'merges a PR, which deploys the backend on Render and the frontend on Cloudflare Pages'),
    ('render ssh', 'opens a shell on the production service'),
    ('render jobs create', 'runs a job against production'),
    ('render deploys create', 'triggers a production deploy'),
    ('render services update', 'reconfigures the production service'),
    ('gh secret set', 'writes a CI secret'),
    ('gh secret delete', 'removes a CI secret'),
)

# Production hosts. Reads are fine and load-bearing — deploy verification hits
# /api/health/?deep=1. Only writes are blocked.
PROD_HOSTS = ('stemquest-api-va', 'api.stemquests.com')

WRITE_METHOD = re.compile(
    r'(-X|--request)\s+["\']?(POST|PUT|PATCH|DELETE)\b'
    r'|(^|\s)(-d|--data|--data-raw|--data-binary|--form|-F)(\s|=)',
    re.IGNORECASE,
)

SHELL_WRAPPER = re.compile(r'(^|[\s;&|(=])(sh|bash|zsh|dash|ksh)\s+(-[A-Za-z]*\s+)*-[A-Za-z]*c\b')
EVAL_CALL = re.compile(r'(^|[\s;&|(])eval\b')
CURL_PIPED_TO_SHELL = re.compile(r'\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(sh|bash|zsh|dash|ksh)\b')


def block(reason):
    sys.stderr.write('Blocked by .claude/hooks/guard-bash.sh: ' + reason + '\n')
    sys.exit(2)


def main():
    payload = json.load(sys.stdin)
    if payload.get('tool_name') != 'Bash':
        return
    command = payload.get('tool_input', {}).get('command')
    if not isinstance(command, str) or not command.strip():
        return

    # Collapse whitespace, newlines included, so a wrapped command still matches.
    flat = ' '.join(command.split())
    lowered = flat.lower()

    if SHELL_WRAPPER.search(flat) or EVAL_CALL.search(flat):
        block(
            'a shell wrapper (sh -c / bash -c / eval) hides the real command from the '
            'deny list, so it is refused whatever it contains. Run the command directly.'
        )

    if CURL_PIPED_TO_SHELL.search(flat):
        block('piping a download into a shell executes unreviewed remote code.')

    for needle, why in PROD_COMMANDS:
        if needle in lowered:
            block(
                "'%s' %s. That decision belongs to the user - say what needs doing and "
                "let them run it." % (needle, why)
            )

    for host in PROD_HOSTS:
        if host in lowered and WRITE_METHOD.search(flat):
            block(
                'this looks like a write request against production (%s). Reads against '
                'prod are fine; writes are not. If this is the sanctioned post-deploy '
                'check (POST /api/auth/demo-login/ for a token, then a content read), ask '
                'the user to run it or drive it through the browser.' % host
            )


try:
    main()
except SystemExit:
    raise
except Exception:
    # Malformed JSON, missing keys, anything unexpected: allow the call.
    pass

sys.exit(0)
