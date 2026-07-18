# Phase 19: Learning Mode UI Balance

## Goal

Make the learning-mode chrome (top bar, course-content sidebar, navigation
footer) more prominent and visually balanced against the content area. Today
everything around the lesson content renders at `text-xs`/`text-sm` with 16px
icons, a 56px top bar, and a cramped progress meter — on a large display the
chrome reads as an afterthought. This phase scales up typography, spacing, and
key affordances without changing any behavior, routes, or data flow.

Screenshot reference: student view of `/courses/VGD101/learn/1` (2026-07-18).

## Decisions made during scoping

- Pure presentation pass: no API, routing, or state changes. Sidebar
  collapse/persistence, keyboard nav, auto-advance, and section logic are
  untouched.
- Sidebar widens from 380px to 420px and gets a typography/spacing bump; the
  collapsed rail widens slightly to match.
- Top bar grows from 56px to 64px with a larger course title, full-size Exit
  button, and a wider/taller progress meter.
- Navigation footer grows to match the top bar (64px) with full-size
  Previous/Next buttons and larger section indicators.
- Lesson content column keeps `max-w-4xl`; only its padding breathes a bit
  more. The point is balance, not a content redesign.

## Out of scope

- Mobile/responsive rework beyond keeping existing `sm:` breakpoints sane.
- Dark/light theme changes, color palette changes.
- Any sidebar feature work (search, filtering, drag to resize).
- Quiz section, video player, and markdown content styling.

## Tasks

### `frontend/src/pages/courses/CoursePlayerPage.tsx`

- [x] Top bar: `h-14` → `h-16`, horizontal padding `px-4` → `px-6`.
- [x] Exit button: `size="sm"` → default size.
- [x] Course title: `text-sm sm:text-base` → `text-base sm:text-lg`.
- [x] Progress meter: bar `w-20 sm:w-28 h-2` → `w-28 sm:w-40 h-2.5`;
      percentage label `text-xs` → `text-sm`.
- [x] Lesson header: title `text-2xl` → `text-3xl`; content wrapper padding
      `p-6` → `p-6 lg:p-8`.
- [x] Navigation footer: `h-14` → `h-16`, `px-4 sm:px-6` → `px-6`;
      Previous/Next buttons `size="sm"` → default; section dots
      `w-2 h-2` → `w-2.5 h-2.5` (active `w-3` → `w-4`); helper/counter text
      `text-xs` → `text-sm`.

### `frontend/src/components/course/CourseSidebar.tsx`

- [x] Expanded width `w-[380px]` → `w-[420px]`.
- [x] Header: padding `p-4` → `p-5`; "Course Content" `text-sm` →
      `text-base`; collapse chevron `h-4 w-4` → `h-5 w-5`.
- [x] Progress: bar `h-2` → `h-2.5`; caption `text-xs` → `text-sm`.
- [x] Unit rows: padding `px-4 py-3` → `px-5 py-4`; unit title `text-sm` →
      `text-base`; lesson count `text-xs` → `text-sm`; chevrons and unit
      check icon `h-4 w-4` → `h-5 w-5`.
- [x] Lesson rows: padding `px-4 py-2` → `px-5 py-3`; title `text-sm` →
      `text-[15px]`; completion/type/quiz icons `h-4 w-4` → `h-5 w-5`;
      active border `border-l-2` → `border-l-[3px]`.
- [x] Collapsed rail: `w-12` → `w-14`; expand chevron `h-4 w-4` → `h-5 w-5`.

## Verification

- [x] `cd frontend && npx tsc --noEmit` — 0 errors.
- [x] `cd frontend && npm run lint` — 0 new errors.
- [x] `/verify-stack` output shown. (2026-07-18: pytest 192 passed,
      tsc 0 errors, lint 0 errors / 24 pre-existing warnings)
- [ ] Visual check at `/courses/VGD101/learn/1`: chrome reads balanced at
      desktop width; sidebar collapse/expand still works and persists; footer
      section dots still navigate.
