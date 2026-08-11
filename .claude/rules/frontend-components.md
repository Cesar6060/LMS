---
paths:
  - "frontend/src/components/**"
  - "frontend/src/pages/**"
---

# Components and Pages

## The UI library

- `src/components/ui/` is the design system: AnimatedBackground, Button, Card,
  ConfirmDialog, Dialog, DropdownMenu, Input, ProgressBar, Sheet, Skeleton,
  Tabs, Toast. Compose from these; look for an existing one before building new.
- Radix is imported in exactly 5 files, all wrappers: `ui/Button.tsx:2`
  (`react-slot`), `ui/Dialog.tsx:2` + `ui/Sheet.tsx:2` (`react-dialog`),
  `ui/DropdownMenu.tsx:2`, `ui/Tabs.tsx:2`. A new Radix primitive enters **only**
  wrapped in `components/ui/` — never `@radix-ui/*` in a page or feature file.

## Styling

- `cn()` from `@/lib/utils` = `twMerge(clsx(...))` (`lib/utils.ts:4`) — lets a
  caller's `className` beat the component's own. Every styled component takes
  `className` and runs it through `cn`.
- Variants use `cva`: base string, then `variants` + `defaultVariants`, props
  extending `VariantProps<typeof xVariants>` (`ui/Button.tsx:6-36`). Add to the
  `cva` map — do not fork the component or pile on conditional classNames.
  `asChild` renders through Radix `Slot` (`ui/Button.tsx:41`): use it to put
  button styling on a `<Link>` instead of restyling an anchor.
- Use semantic tokens, not raw colors: `background`/`foreground`, `card`,
  `primary`, `secondary`, `muted`, `accent`, `destructive` (each with a
  `-foreground` pair), plus `border`, `input`, `ring`. They resolve to HSL CSS
  variables set per theme in `src/index.css:9-53` (`tailwind.config.mjs:13-42`),
  so they theme automatically; `neon-*` and `shadow-neon-*` are literal and do
  not.
- The type scale is deliberately one notch above stock Tailwind:
  `tailwind.config.mjs:65-70` (the config is `.mjs`, not `.js`) overrides
  `xs`→0.8125rem, `sm`→0.9375rem, `base`→1.0625rem, `lg`→1.1875rem (stock
  0.75/0.875/1/1.125); `xl`+ stay stock. `text-sm` reads like stock `text-base` —
  don't "fix" small text by bumping a step.

## Page shape and the isLoading / error / forbidden trio

- Page bodies wrap in `PageContainer` (`components/layout/PageContainer.tsx:17`):
  `container mx-auto px-6 py-8` + `max-w-7xl`. Narrow via the `maxWidth` prop
  (`maxWidth="max-w-6xl"`), never by hand-rolling the div. Early-return branches
  wrap in it too, so the page does not jump width when it resolves.
- Data pages hold three states: `isLoading` (init `true`), `error` (init `''`),
  `forbidden` (init `false`) — `GradebookPage.tsx:22-24`, `AnnouncementsPage.tsx:31-33`.
- The fetch `catch` branches on `isForbidden(err)` from `@/services/api` (403
  check, `services/api.ts:157`): forbidden → `setForbidden(true)`, else
  `setError('Failed to load …')` + `console.error`; `setIsLoading(false)` in
  `finally` (`GradebookPage.tsx:31-40`).
- Render order is fixed: `isLoading` → skeleton, `forbidden` → `<AccessDenied />`
  (`components/AccessDenied.tsx`, optional `message`), then `error || !data` →
  inline error card. See `GradebookPage.tsx:113-131`.
- `Skeleton` (`ui/Skeleton.tsx`) is in-page loading: mirror the real layout with
  sized blocks so nothing shifts (`GradebookPage.tsx:113-121`).
- `PageLoader` (`components/PageLoader.tsx`) is a full-screen spinner reserved
  for route-level work in `App.tsx` — auth-guard `isLoading` (`App.tsx:53`) and
  the `<Suspense>` fallback (`App.tsx:127`). Never for a fetch inside a page.

## Confirmation and routing

- Use `ConfirmDialog` (`ui/ConfirmDialog.tsx`), never native `confirm()`: `open`,
  `onOpenChange`, `title`, `confirmLabel`, `onConfirm`, optional `loadingLabel`/
  `isLoading`/`destructive`, body as `children` (`StudentRosterPage.tsx:849-863`).
  Convert the ~6 legacy native `confirm()` call sites when you touch them.
- Pages are **named** exports registered as `lazy()` routes in `src/App.tsx`, one
  chunk each. `lazy()` wants a default, hence
  `lazy(() => import('@/pages/X').then((m) => ({ default: m.X })))`
  (`App.tsx:10-13`). Do not add a default export.

## Auth (details in `frontend.md`)

- `useAuth` from `@/contexts/useAuth`, never `AuthContext` — the split keeps
  `AuthContext.tsx` component-only for `react-refresh/only-export-components`
  (`contexts/useAuth.ts:15-17`).
- No role string exists: instructor gating is `!!user?.is_instructor`
  (`types/index.ts:14`); hide write UI when `!!user?.is_demo`
  (`types/index.ts:16`), as in `DiscussionsPage.tsx:40,159,227`.
