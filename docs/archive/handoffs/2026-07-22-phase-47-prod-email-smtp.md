# Handoff: Phase 47 — Production email (Gmail SMTP)

## Current state
Phase 47 code-complete on `feat/phase-47-prod-email-smtp`, PR
https://github.com/Cesar6060/LMS/pull/39 (open, not merged). Implemented:
custom `PasswordResetSerializer` + `FrontendPasswordResetForm`
(`backend/accounts/serializers.py`) emailing branded templates
(`backend/templates/registration/password_reset_{email.html,email.txt,subject.txt}`)
whose link is `{FRONTEND_URL}/reset-password?uid=…&token=…`; demo guard
(`triggered_by` param) in `backend/core/email.py` threaded through invite +
announcement call sites in `backend/courses/views.py`; demo account also
skipped inside the reset form itself; `ThrottledPasswordResetView`
(`accounts/views.py` + `accounts/urls.py`, scope `password_reset`, env var
`THROTTLE_PASSWORD_RESET`); `EMAIL_TIMEOUT` in settings; render.yaml → SMTP
backend + Gmail literals + 3 `sync:false` secrets; runbook
`docs/runbooks/phase-47-email-rollout.txt`; docs/.env.example updated.
Verified: pytest 424 passed (9 new mail.outbox tests), tsc 0 errors, lint
0 errors/22 warnings (phase-46 baseline). Local console-backend reset shows
branded body + frontend link. No migrations.

## In progress / not done
- USER rollout (runbook steps 1-2 BEFORE merge): create Google app password
  for cesarvillarreal11@gmail.com; set `EMAIL_HOST_USER`,
  `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` in Render dashboard.
- USER: merge PR #39, then live verification (runbook step 4 / spec
  "Verification" prod items — reset round trip on live site, 429 throttle,
  clean Render logs). Spec prod checkboxes still open.

## Next steps
1. USER: runbook steps 1-2 (app password + Render secrets), then merge #39.
2. Live-verify per docs/runbooks/phase-47-email-rollout.txt step 4; check
   off the three prod items in docs/specs/phase-47-prod-email-smtp.md.
3. Nothing else pending from earlier phases (46 fully closed).

## Decisions made
- Kept `AllAuthPasswordResetForm` as base and overrode only `save()`:
  confirm endpoint decodes allauth's base36 uid + allauth token generator,
  so spec's literal "Django PasswordResetForm + extra_email_context" route
  would have broken the round trip. extra_email_context still honored.
- Demo account skipped inside the reset form too (not just triggered_by):
  jdoe@demo.com's mailbox isn't ours and reset-confirm bypasses
  ProtectedPasswordChangeSerializer — a delivered reset link could hijack
  the demo password. Response stays 200 (no enumeration).
- `THROTTLE_PASSWORD_RESET=5/hour` as render.yaml literal (spec's render.yaml
  task) rather than dashboard secret; dashboard can still override.
- Announcement email test monkeypatches `core.email.send_emails_async` to run
  inline — the daemon thread races `mail.outbox` assertions.

## Gotchas discovered
- dj-rest-auth silently ignores `email_template_name`/`extra_email_context`
  opts when allauth is installed (AllAuthPasswordResetForm only reads
  token_generator/url_generator kwargs) — spec-as-written was a no-op path.
- Plain-text email template needs `{% autoescape off %}` or the link's `&`
  renders as `&amp;` in the body.
- `head` in this zsh is a perl URL tool — use `/usr/bin/head`.

## Files to read first
- docs/specs/phase-47-prod-email-smtp.md — checklist w/ evidence
- docs/runbooks/phase-47-email-rollout.txt — operator steps
- backend/accounts/serializers.py — FrontendPasswordResetForm rationale
- backend/core/email.py — demo guard
