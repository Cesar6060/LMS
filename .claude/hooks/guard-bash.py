"""Bash guard for the PreToolUse hook. Invoked by guard-bash.sh.

Reads the tool-call JSON on stdin. Exit 2 blocks the call and shows stderr to
Claude; exit 0 allows it. Anything unexpected falls through to exit 0 — see the
fail-open note in guard-bash.sh.

Matching works on SHELL TOKENS, not on raw text. An earlier version substring-
matched the command string, which failed in both directions: `'gh' pr merge`
and `gh pr me""rge` slipped past, while `gh pr create --body "...do not gh pr
merge..."` — boilerplate in this project's own /finish-phase skill — was
blocked. Tokenising kills both families at once: a needle inside a quoted
argument is an argument, and quote-splicing inside a command word is not.

This remains a SAFETY NET, NOT A SECURITY BOUNDARY. Shell expansion is not
performed here, so `A=gh; $A pr merge`, a base64 pipeline, `python3 -c ...`, or
a command sourced from a file all get through by construction. The job is to
stop an accident, not a determined bypass.
"""

import json
import os
import re
import shlex
import sys

SHELLS = frozenset(('sh', 'bash', 'zsh', 'dash', 'ksh'))

# Prefixes that wrap another command; strip them and judge what follows.
# `docker` is deliberately NOT here: `docker compose exec ... sh -c` runs inside
# the container, which is ordinary and must stay allowed.
PREFIX_WRAPPERS = frozenset(('command', 'env', 'sudo', 'nohup', 'time', 'nice', 'stdbuf'))

# argv patterns that act on production and nothing else. Matched positionally.
PROD_ARGV = (
    (('gh', 'pr', 'merge'), 'merges a PR, which deploys the backend on Render and the frontend on Cloudflare Pages'),
    (('gh', 'secret', 'set'), 'writes a CI secret'),
    (('gh', 'secret', 'delete'), 'removes a CI secret'),
    (('render', 'ssh'), 'opens a shell on the production service'),
    (('render', 'jobs', 'create'), 'runs a job against production'),
    (('render', 'deploys', 'create'), 'triggers a production deploy'),
    (('render', 'services', 'update'), 'reconfigures the production service'),
)

# Production hosts. Reads are fine and load-bearing — deploy verification hits
# /api/health/?deep=1. Only writes are blocked.
PROD_HOSTS = ('stemquest-api-va', 'api.stemquests.com')

# Exact tokens, case-sensitive: `-f` and `-D` are ordinary GET flags and must
# not be confused with `-F` and `-d`.
WRITE_FLAGS = frozenset((
    '-d', '--data', '--data-raw', '--data-binary', '--data-urlencode',
    '-F', '--form', '-T', '--upload-file', '--json', '--post-data',
))
WRITE_METHODS = frozenset(('POST', 'PUT', 'PATCH', 'DELETE'))
METHOD_FLAGS = frozenset(('-X', '--request', '--method'))
SHORT_METHOD = re.compile(r'^-X(POST|PUT|PATCH|DELETE)$', re.IGNORECASE)
C_FLAG = re.compile(r'^-[A-Za-z]*c[A-Za-z]*$')
# Shell options that consume the following token, so it is not the command word.
OPTION_TAKES_VALUE = frozenset(('-o', '+o', '--rcfile', '--init-file'))

# Tokenising is linear but not free: ~370 ms at 200 KB. Above this size, fall
# back to a coarse substring scan. Nothing the phase loop runs comes close.
MAX_TOKENIZE = 100000

# Shell operators shlex hands back as their own tokens when punctuation_chars
# is on. They end one command segment and start the next.
OPERATORS = frozenset((';', '&&', '||', '|', '&', '|&', '(', ')', '\n'))
ASSIGNMENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')


def block(reason):
    sys.stderr.write('Blocked by .claude/hooks/guard-bash.sh: ' + reason + '\n')
    sys.exit(2)


def base(token):
    """Command name without its path: /bin/sh -> sh."""
    return os.path.basename(token)


def segments(tokens):
    """Split a token list into command segments at shell operators."""
    out, current = [], []
    for token in tokens:
        if token in OPERATORS:
            if current:
                out.append((current, token))
                current = []
        else:
            current.append(token)
    if current:
        out.append((current, ''))
    return out


def argv_of(tokens):
    """Drop leading VAR=value assignments and wrapper commands."""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if ASSIGNMENT.match(token) or base(token) in PREFIX_WRAPPERS:
            i += 1
            continue
        break
    return tokens[i:]


def wraps_a_shell(tokens, argv):
    """True if this segment hands a command string to a shell.

    Covers `sh -c`, `/bin/sh -c`, `bash --norc -c`, `sh -ce`, `sh -o noglob -c`,
    and the same forms reached through `find -exec` or `xargs`. Skipped when the
    segment runs docker: a shell inside the container is normal.
    """
    if argv and base(argv[0]) == 'docker':
        return False
    for i, token in enumerate(tokens):
        if base(token) not in SHELLS:
            continue
        skip_next = False
        for following in tokens[i + 1:]:
            if skip_next:
                # The value of an option that takes one, e.g. `-o noglob`.
                skip_next = False
                continue
            if not following.startswith('-'):
                break
            if C_FLAG.match(following):
                return True
            skip_next = following in OPTION_TAKES_VALUE
    return False


def prod_write_request(tokens, argv):
    """True if this segment is a write request aimed at a production host."""
    if not argv or base(argv[0]) not in ('curl', 'wget', 'http', 'https', 'xh'):
        return None
    host = next((h for h in PROD_HOSTS for t in tokens if h in t), None)
    if host is None:
        return None
    for i, token in enumerate(tokens):
        if token in WRITE_FLAGS or SHORT_METHOD.match(token):
            return host
        if token in METHOD_FLAGS and i + 1 < len(tokens):
            if tokens[i + 1].upper() in WRITE_METHODS:
                return host
        # httpie puts the bare method first: `http POST https://...`
        if i == 1 and token.upper() in WRITE_METHODS:
            return host
    return None


def gh_api_write(argv):
    """`gh api --method PUT ...` reaches merge and secret endpoints directly."""
    if len(argv) < 2 or base(argv[0]) != 'gh' or argv[1] != 'api':
        return False
    for i, token in enumerate(argv):
        if SHORT_METHOD.match(token):
            return True
        if token in METHOD_FLAGS and i + 1 < len(argv):
            if argv[i + 1].upper() in WRITE_METHODS:
                return True
    return False


def check(tokens):
    for seg, _op in segments(tokens):
        argv = argv_of(seg)
        if not argv:
            continue

        if base(argv[0]) == 'eval':
            block(
                'eval hides the real command from the deny list, so it is refused '
                'whatever it contains. Run the command directly.'
            )

        if wraps_a_shell(seg, argv):
            block(
                'a shell wrapper (sh -c / bash -c) hides the real command from the '
                'deny list, so it is refused whatever it contains. Run the command '
                'directly. (Running a shell inside a container via docker is fine.)'
            )

        name = base(argv[0])
        for pattern, why in PROD_ARGV:
            if name == pattern[0] and tuple(argv[1:len(pattern)]) == pattern[1:]:
                block(
                    "'%s' %s. That decision belongs to the user - say what needs "
                    "doing and let them run it." % (' '.join(pattern), why)
                )

        if gh_api_write(argv):
            block(
                'a write through `gh api` reaches the same production endpoints as '
                'the denied gh commands (merge, secrets). Reads via gh api are fine.'
            )

        host = prod_write_request(seg, argv)
        if host:
            block(
                'this looks like a write request against production (%s). Reads '
                'against prod are fine; writes are not. If this is the sanctioned '
                'post-deploy check (POST /api/auth/demo-login/ for a token, then a '
                'content read), ask the user to run it or drive it through the '
                'browser.' % host
            )

    # A download piped into a shell: curl/wget anywhere upstream of a shell.
    saw_download = False
    for seg, op in segments(tokens):
        argv = argv_of(seg)
        if argv and base(argv[0]) in SHELLS and saw_download:
            block('piping a download into a shell executes unreviewed remote code.')
        if argv and base(argv[0]) in ('curl', 'wget'):
            saw_download = op in ('|', '|&')
        elif op not in ('|', '|&'):
            saw_download = False


def coarse(command):
    """Substring fallback for a command too large to tokenise.

    Imprecise in both directions on purpose — a false positive on a 100 KB
    command costs nothing, and this path is not reachable by anything the phase
    loop runs.
    """
    flat = ' '.join(command.split()).lower()
    for pattern, why in PROD_ARGV:
        if ' '.join(pattern) in flat:
            block(
                "'%s' %s. (Command too large to parse precisely, so this is a "
                "coarse text match.)" % (' '.join(pattern), why)
            )


def main():
    payload = json.load(sys.stdin)
    if payload.get('tool_name') != 'Bash':
        return
    command = payload.get('tool_input', {}).get('command')
    if not isinstance(command, str) or not command.strip():
        return

    if len(command) > MAX_TOKENIZE:
        coarse(command)
        return

    # A backslash before a newline is a line continuation: the shell splices the
    # lines into one command. Do the same before tokenising, or `gh \<nl> pr
    # \<nl> merge` looks like three separate commands.
    command = command.replace('\\\n', ' ')

    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    # An unbalanced quote is not a runnable command; fail open rather than
    # guessing at it. The ValueError is caught by the wrapper below.
    tokens = list(lexer)
    check(tokens)


try:
    main()
except SystemExit:
    raise
except Exception:
    # Malformed JSON, unbalanced quotes, missing keys, anything unexpected:
    # allow the call. A guardrail that hard-fails every Bash call is worse than
    # the gap it closes.
    pass

sys.exit(0)
