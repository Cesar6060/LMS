---
paths:
  - "frontend/src/services/**"
---

# Frontend API Services

## Always call through the `api.ts` default export

- Import `api from './api'` (`api.ts:161`). Never call `axios` directly from a service. The one
  exception in the codebase is the refresh call itself (`api.ts:40`) — going through `api` would
  loop the response interceptor.
- A bare `axios` call silently loses all four of these:
  - **Auth header + base URL** — the request interceptor reads `localStorage.token` and sets
    `Authorization: Bearer …` (`api.ts:16-27`); `baseURL` is `VITE_API_URL` (`api.ts:6-13`).
  - **401 single-flight refresh** (`api.ts:33-51`, `124-151`) — the first 401 stores the in-flight
    `refreshAccessToken()` promise in module-level `refreshPromise`; concurrent 401s reuse it
    (`refreshPromise = refreshPromise ?? …`, `api.ts:139`) so only one refresh is sent, then each
    caller replays its own request with the new token. `_retry` on the config caps it at one attempt
    per request; login/logout 401s and a missing `refresh` go straight to `clearTokensAndRedirect()`
    (`api.ts:53-62`), which redirects to `/login?next=…`.
  - **Sentry filtering** (`api.ts:100-113`) — `captureException` fires *only* when it is an axios
    error with `code !== 'ERR_CANCELED'` and status `undefined` (network failure) or `>= 500`.
    4xx never reaches Sentry.
  - **`demo_blocked` handling** (`api.ts:118-122`) — rewrites `error.message` to
    `DEMO_BLOCKED_MESSAGE` and fires the registered toast listener.

## Do not reimplement the interceptor

- No per-service 401 handling, token refresh, retry loop, or redirect-to-login.
- No per-service `Sentry.captureException` — the interceptor already decided what is reportable.
- No per-service `demo_blocked` detection or toasting; `ToastContext.tsx:27` is the only registrant
  of `setDemoBlockedListener` (`api.ts:88`) and it announces every blocked write globally.

## Tokens

- Keys are exactly `token` (access) and `refresh` in `localStorage` — no prefix, no wrapper.
- Writers today: `auth.ts:7,8,16,17,23,24` (login / demoLogin / register), `invites.ts:97-98`
  (accept-invite creates the account and logs the student in), and the interceptor's own
  refresh/clear (`api.ts:44,48,54,55`). Add no new writer — a service handed an `AuthResponse`
  should reuse `authService`. Read the access token via `authService.getToken()` (`auth.ts:79`).

## Classify errors with the exported helpers

- `isForbidden(error)` (`api.ts:157`) and `isDemoBlocked(error)` (`api.ts:73`) — never hand-inspect
  `error.response.status` or `error.response.data.code` in a service or page.
- `DEMO_BLOCKED_MESSAGE` (`api.ts:70`) is the only demo copy; don't write your own string.
- `setDemoBlockedListener` (`api.ts:88`) is for `ToastContext` only — services must not call it.

## Service shape

- Export a named `const <name>Service = { … }` object of `async` methods (`courseService`
  `courses.ts:143`, `quizzesService` `quizzes.ts:4`, `inviteService` `invites.ts:11`). Some files add
  `export default` too (`courses.ts:662`, `quizzes.ts:119`, `invites.ts:107`); the named export is
  the one callers rely on.
- Always pass the generic — `api.get<T>(…)` / `api.post<T>(…)` — then `return response.data`.
- Shared domain types come from `../types`; response shapes specific to one service are declared and
  `export`ed at the top of that service file (`courses.ts:7-141`).
- Every URL ends in a trailing slash, or Django's `APPEND_SLASH` redirect drops POST bodies.
- The `courses` app mounts at `/api/courses/` and its router adds `courses/`, so course-router URLs
  are genuinely doubled: `/courses/courses/<code>/…` (`courses.ts:146`, `invites.ts:16`). Non-router
  course URLs are single (`/courses/lessons/…`, `/courses/units/…`). Quizzes and discussions mount at
  `/api/` root — no app prefix at all (`quizzes.ts:19`).
- Per-call axios options are fine, the interceptor still runs: `responseType: 'blob'`
  (`courses.ts:385`), `multipart/form-data` header override (`courses.ts:513`).
- Paginate inside the service when callers expect a flat list — `getStudentRoster` walks DRF `next`
  and strips the absolute prefix (`.replace(/^.*\/api/, '')`) so `baseURL` still applies
  (`courses.ts:396-410`).
