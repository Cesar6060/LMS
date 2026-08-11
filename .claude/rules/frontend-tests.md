---
paths:
  - "frontend/src/**/*.test.{ts,tsx}"
  - "frontend/src/test/**"
---

# Frontend Tests (vitest + React Testing Library)

## Run & place

- `cd frontend && npm test` — `vitest run`, one pass (`package.json:10`).
  `npm run test:watch` is bare `vitest`. Suite today: 26 files, 269 tests, ~3s.
- Co-locate `Foo.test.tsx` next to `Foo.tsx`; no `__tests__/` dir exists anywhere
  under `frontend/src` — do not create one. Glob: `src/**/*.{test,spec}.{ts,tsx}`.
- A test ships in the SAME commit as the feature. New frontend behavior with no
  test is an incomplete change, not a follow-up.

## Mock at the service-module boundary — never axios

Zero tests touch `axios`. Mock the `@/services/*` module (or a context hook) with
`vi.hoisted` handles so `beforeEach` can reset them (`ClassCodeCard.test.tsx:5`):

```ts
const mockGetJoinCode = vi.hoisted(() => vi.fn());
vi.mock('@/services/courses', () => ({
  courseService: { getJoinCode: mockGetJoinCode },
}));
// beforeEach: mockGetJoinCode.mockReset();
```

- Auth the same way: `vi.mock('@/contexts/useAuth', () => ({ useAuth: () => ({ user }) }))`
  (`ManageCoursePage.test.tsx:19`).
- Stub heavy children that own a suite, so a page test does not re-test them
  (`ManageCoursePage.test.tsx:25`).

## Query by role and accessible name

- Use `getByRole`/`findByRole` with `{ name: /…/i }`, `getByLabelText`,
  `findByText` (`JoinWithCodePage.test.tsx:24-26`) — ~95 role queries vs 6 testid.
- `data-testid` exists in exactly three production spots (`OutlineUnitCard.tsx:291,334`,
  `CoursePlayerPage.tsx:1169`), all badges/indicators with no accessible name. Do
  not add a fourth to ease a test; give the element a real role or label. On a
  test-local stub component it is fine (`CoursePlayerPage.test.tsx:37`).

## Routing

- react-router v7: import from `'react-router'`; `'react-router-dom'` appears
  nowhere in `src` — do not introduce it.
- Page tests render inside `MemoryRouter` + `Routes` with `initialEntries` set to a
  real URL so `useParams`/`useSearchParams` resolve (`JoinWithCodePage.test.tsx:12`,
  `CoursePlayerPage.test.tsx:132`). Assert navigation with a probe route that
  renders `useLocation()` (`CoursePlayerPage.test.tsx:461`).

## Environment (`src/test/setup.ts`, `vite.config.ts` `test`)

- jsdom, `globals: true`, one setup file — yet all 26 files still import
  `describe/it/expect/vi` from `'vitest'` explicitly; match that.
- Setup only adds `@testing-library/jest-dom/vitest` matchers and `cleanup()` in
  `afterEach` (`setup.ts:4-9`). No global `matchMedia`/`ResizeObserver`/`fetch`
  shim — stub locally. Fake timers opt-in (`useDebounce.test.ts`); prefer `findBy*`.
