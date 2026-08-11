---
paths:
  - "frontend/src/**/*.{ts,tsx}"
---

# React Frontend — always-on core

The short list that applies to every file under `src/`. The heavy conventions
are split by path: `frontend-services.md` (the `api.ts` contract),
`frontend-components.md` (UI library, pages, state trio),
`frontend-tests.md` (vitest).

## Types and imports

- TypeScript strict. No `any` — there are currently zero in `src/`, keep it
  that way. Explicit props and state types; functional components with hooks.
- Import with the `@/` alias, not relative parents (102 files use `@/`, 8 use
  `../`). Same-directory `./` is fine.
- Cross-cutting domain types live in the `src/types/index.ts` barrel (73
  exported types). A response shape used by exactly one service may live in
  and be imported from that service — `services/courses.ts` and
  `services/analytics.ts` export 20 interfaces between them and pages import
  them from there. Do not duplicate a type into both places.

## Router

- react-router **v7**. Import from `'react-router'` — `react-router-dom` is
  not a dependency and appears nowhere in `src/`. Adding an import from it
  will typecheck locally only until the install is clean, then break.

## Auth and roles

- `useAuth` comes from `@/contexts/useAuth`, never from `AuthContext`. The
  split is deliberate: it keeps `AuthContext.tsx` component-only for the
  `react-refresh/only-export-components` lint rule.
- There is no role string. Instructor gating is `!!user?.is_instructor`
  (`types/index.ts:14`).
- The demo account is `user.is_demo` (`types/index.ts:16`). Hide write UI for
  it rather than letting the user click a button the backend will 403. The
  backend answer is a 403 with `code: 'demo_blocked'`, which the axios
  interceptor already turns into a toast — see `frontend-services.md`.

## Environment

- Every new `VITE_*` variable must be declared in `src/vite-env.d.ts`
  (`ImportMetaEnv`), or `import.meta.env.X` is untyped. Currently
  `VITE_API_URL` (required) and `VITE_SENTRY_DSN` (optional).
- `VITE_API_URL` is baked in at build time. CI's production build sets it
  explicitly so Cloudflare Pages can never ship a bundle without it.

## Before done

`cd frontend && npx tsc --noEmit` (zero errors), `npm run lint` (zero errors)
and `npm test` all pass. CI runs all three plus a production build.
