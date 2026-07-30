# Phase 62 — Player UX polish: Present everywhere + deferred nits

## Goal

Make the Present control a first-class, always-available affordance in the
course player instead of a slide-only button buried in the stage corner, and
clear the three UI nits deferred from phases 60–61. Today the Present button
lives inside `SlideStage` (`SlideStage.tsx:50-62`, `absolute top-4 right-4`),
so it exists only on `layout === 'slide'` pages; an instructor on a doc page
has no way to go fullscreen. This phase moves the button into the player
content area's top-right corner — inside the fullscreen element, so the same
control both enters and exits — and makes it available on doc and slide pages
alike. Alongside that: the lesson header stops hiding Mark Complete while
presenting, the attachments card stops stealing slide-stage height, the slide
stage gets a real aspect-ratio constraint instead of a viewport-derived width
cap, and the instructor editor's live preview stops re-running highlight.js on
every keystroke. Zero backend change — no models, no migrations, no endpoints.

## Out of scope

- Any backend work. No model, migration, serializer, endpoint, or permission
  change. `LessonSection` is untouched.
- A Present button in the instructor editor's slide preview
  (`SectionEditor.tsx:917-938` is a hand-rolled mini stage, not `SlideStage`).
- Presenting from anywhere outside the course player — no Present on the
  course map, dashboard, or instructor pages. "Every page" means every page
  *of a lesson*.
- Role-gating Present. Students keep it (decided below).
- Speaker notes, presenter view, a second-screen mode, laser pointer, or any
  new presentation feature beyond the fullscreen toggle that exists today.
- Re-chunking course content, seed-command edits, or prod reseeding.
- Fixing the deferred phase-61 items (Pillow `verify()` trailing bytes,
  no-slash POST 500, orphaned media on course cascade-delete).
- The unpaginated lesson-list N+1 (pre-existing, phase 53).

## Key decisions (from scoping interview + code exploration)

1. **Button lives inside the fullscreen element, not the player header.**
   The player header (`CoursePlayerPage.tsx:659-706`) sits *outside*
   `playerContentRef` (`:727`), which is the fullscreen target. A button there
   would vanish the moment presenting starts, leaving `Esc`/`F` as the only
   exit. So the button becomes an absolutely-positioned child of the
   `playerContentRef` div itself — one control that reads "Present" or "Exit"
   and is always visible.
2. **Direct child of `playerContentRef`, not of the scroll container.** Doc
   pages scroll (`:736`, `flex-1 overflow-y-auto`). If the button lived inside
   that scroller it would scroll out of view. Mounting it as a sibling of the
   scroller — with `relative` added to the `playerContentRef` div — pins it.
3. **Doc + slide pages only; the quiz page shows Exit but never Present.**
   Projecting a quiz to the room can spoil it for students answering on their
   own devices. But paging *into* the quiz while already presenting must not
   yank the class out of fullscreen, so presenting continues and the button
   stays as Exit. Concretely: render when `!isOnQuizSection || isPresenting`.
4. **No role gate — students keep Present.** It's a harmless fullscreen
   toggle and doubles as distraction-free reading. Gating on `isCourseOwner`
   would also be a regression on slide pages, where every user has it today.
5. **Hide the lesson title while presenting, keep Mark Complete.** Today the
   entire header block is hidden (`:740`, `isPresenting && isSlidePage`),
   which is the deferred nit — a student can't finish the lesson without
   leaving fullscreen. Split the block: title/subtitle/quiz-badge hide,
   Mark Complete stays. The rule also stops being slide-only, since presenting
   now happens on doc pages too.
6. **Attachments get `shrink-0` + a capped height with their own scroll.**
   They're a sibling of the stage inside a `h-full flex flex-col`
   (`:820-825`), so a tall card subtracts from the stage's `flex-1 min-h-0`.
   Capping and scrolling inside keeps files reachable without page scroll,
   which phase 60 deliberately removed from slide pages.
7. **Real aspect-ratio on the stage.** `max-w-[calc((100vh-10rem)*1.7778)]`
   (`SlideStage.tsx:44`) derives width from *viewport* height, not the parent
   box — so anything that shrinks the parent shortens the card while it keeps
   the viewport-derived width, breaking 16:9. Switch to a container-relative
   aspect-ratio constraint. This is the root cause the attachments bug
   exposed; fixing both means the stage is correct at any window size.
8. **A shared `useDebounce` hook, not a one-off.** The inline
   `useRef` + `setTimeout` pattern already exists at
   `LessonEditorPage.tsx:124-132`; generalizing it gives the preview a
   predictable delay and leaves a reusable hook. Pair it with memoizing
   `LessonMarkdown` and hoisting its plugin arrays — `remarkPlugins={[...]}`
   / `rehypePlugins={[...]}` at `LessonMarkdown.tsx:26` are fresh array
   literals every render, so `memo` alone would not help.

## Backend tasks

None. This phase is frontend-only.

- [x] Confirm no backend files changed before opening the PR
      (`git diff --stat main -- backend/` is empty) and that
      `makemigrations --check` stays clean.

## Frontend tasks

### A. Present button relocation (sequential — all touch the same two files)

- [x] Add `relative` to the `playerContentRef` div
      (`CoursePlayerPage.tsx:727`) so it becomes the positioning context.
- [x] Create `frontend/src/components/lesson/PresentButton.tsx` — props
      `{ isPresenting: boolean; onToggle: () => void }`. Move the markup
      verbatim from `SlideStage.tsx:50-62`, including the
      `document.fullscreenEnabled` guard (iPhone Safari has no Fullscreen
      API), the `Maximize`/`Minimize` icons, the `aria-label`/`title` pair
      ("Present fullscreen (F)" / "Exit fullscreen (Esc)"), and the
      `hidden md:inline` label span. Position it `absolute top-4 right-4 z-20`
      (z above the stage's own `z-10` content).
- [x] Render `<PresentButton>` as a direct child of the `playerContentRef` div
      in `CoursePlayerPage.tsx`, *outside* the scroll container at `:736`,
      gated on `!isOnQuizSection || isPresenting` (decision 3). It must not
      render while `isLessonLoading` or when `currentLesson` is null.
- [x] Remove the Button, the `Maximize`/`Minimize` imports, and the
      `isPresenting` / `onTogglePresent` props from `SlideStage.tsx`; drop
      them at the call site (`CoursePlayerPage.tsx:586-599`). Keep the
      `pr-24` on the stage title (`SlideStage.tsx:79`) — the floating button
      still overlaps that corner once the lesson header is hidden.
- [x] Update the `F`-key handler (`CoursePlayerPage.tsx:506-514`): the
      condition `isSlidePage || isPresenting` becomes
      `!isOnQuizSection || isPresenting` to match the button. Keep the
      modifier-key bail (`e.metaKey || e.ctrlKey || e.altKey`) so
      Cmd/Ctrl+F find-in-page is never hijacked, and keep the
      input/textarea skip at `:488-490`.

### B. Lesson header while presenting (same file as A — sequential)

- [x] Split the header block at `CoursePlayerPage.tsx:740-811`: apply the
      `hidden` class to the title `h2` (`:741`), the section subtitle
      (`:744-748`), and the quiz-requirement badge (`:752-778`) when
      `isPresenting`; leave the Mark Complete row (`:783-801`) and the
      "Lesson Completed" row (`:805-810`) visible.
- [x] Drop `&& isSlidePage` from the hide condition — presenting now happens
      on doc pages too, and a visible title there would look inconsistent.
- [x] Verify the `mb-6` spacing doesn't leave a gap when only Mark Complete
      remains (move the margin onto the surviving children if it does).

### C. Attachments + stage height (touches A's file — sequential)

- [x] Add `shrink-0` and a capped height with `overflow-y-auto` to the
      attachments card (`LessonAttachmentsList.tsx:15`, currently
      `Card className="mt-6"`) so a long file list scrolls inside the card
      rather than compressing the stage.
- [x] Leave the `!isPresenting` gate at `CoursePlayerPage.tsx:822` as-is —
      attachments stay hidden while presenting.
- [x] Replace the viewport-derived width cap at `SlideStage.tsx:44`
      (`max-w-[calc((100vh-10rem)*1.7778)]`) with a container-relative
      aspect-ratio constraint so the stage holds 16:9 against its actual box.
      Update the component doc comment at `:24-29`, which describes the old
      viewport behavior.

### D. Editor preview debounce — [P] (independent: no file overlap with A/B/C)

- [x] Create `frontend/src/hooks/useDebounce.ts` (the `hooks/` directory does
      not exist yet) — a typed `useDebounce<T>(value: T, delayMs: number): T`
      with `setTimeout` + cleanup on unmount and on value change. Default the
      call sites to 200ms.
- [x] Use it in `SectionEditor.tsx` for the live preview: keep the textarea
      fully controlled off `editingSection.content` (`:904-915`) so typing
      stays instant, and feed the *debounced* value to the previews at
      `:928-931` (slide branch) and `:942` (doc branch).
- [x] Apply the same treatment to the bulk-paste modal preview
      (`SectionEditor.tsx:1056-1065`), which has the identical
      keystroke → `LessonMarkdown` path.
- [x] Hoist the `remarkPlugins` / `rehypePlugins` array literals out of the
      component body in `LessonMarkdown.tsx:26` to module-level constants, and
      wrap the component in `React.memo` — without the hoist, `memo` is a
      no-op because the arrays are new objects each render.

### E. Tests

- [x] Move the Present/Exit assertions out of `SlideStage.test.tsx` (the
      Present vs Exit label test and the `document.fullscreenEnabled` test)
      into a new `PresentButton.test.tsx`; keep the remaining `SlideStage`
      tests (title/markdown render, empty state, image mode) passing with the
      reduced prop set. — [P] once A lands
- [x] Add `frontend/src/hooks/useDebounce.test.ts` with fake timers: value
      updates only after the delay; rapid changes collapse to the last one;
      the pending timer is cleared on unmount. — [P]
- [x] Add a `CoursePlayerPage` component test (first coverage for this file;
      follow the `SlideStage.test.tsx` pattern) asserting: Present renders on
      a doc page, renders on a slide page, does NOT render on the quiz page,
      and DOES render (as Exit) on the quiz page while `isPresenting`.
- [x] Add an assertion that Mark Complete stays in the DOM while
      `isPresenting` and the lesson title does not.

## Verification

Run `/verify-stack` and show the output. It must report:

- **Backend:** `pytest` — 665 tests pass, unchanged (no backend edits).
  `python manage.py makemigrations --check` clean.
- **Types:** `cd frontend && npx tsc --noEmit` — 0 errors. This catches the
  `SlideStage` prop removal at every call site.
- **Lint:** `cd frontend && npm run lint` — 0 errors, 0 warnings.
- **Unit:** `cd frontend && npx vitest run` — 85 existing tests still pass,
  plus the new `PresentButton`, `useDebounce`, and `CoursePlayerPage` cases.
- **Build:** `npm run build` succeeds, and the editor route's chunk does not
  regress (phase 61 got it to 13.08 kB gzip by keeping pdf.js dynamic —
  confirm `useDebounce` didn't pull anything new in).

Manual click-through in a **visible** browser window (a hidden/occluded tab
pauses rAF-driven rendering — phase-61 gotcha):

1. Open a lesson whose first page is `layout='doc'`. Present appears in the
   content area's top-right. Click it → fullscreen, app header and sidebar
   gone, lesson title gone, button now reads Exit. Click Exit → back to normal.
2. Scroll a long doc page while not presenting — the button stays pinned and
   does not scroll away.
3. Press `F` on a doc page → presents. Press `Esc` → exits and the button
   flips back to Present (the `fullscreenchange` listener at `:300-307`).
4. Press `Cmd/Ctrl+F` → browser find-in-page opens; presenting does not toggle.
5. Navigate to a slide page. The stage has no button of its own; the floating
   one is the only Present control and does not overlap the slide title.
6. On a lesson with a quiz: page to the quiz → no Present button. Go back a
   page, start presenting, then page forward into the quiz → still fullscreen,
   button reads Exit, clicking it exits cleanly.
7. On a lesson with attachments and no quiz, land on the last slide page: the
   stage keeps full height and holds 16:9; a long attachments list scrolls
   inside its own card.
8. Resize the window narrow/short while on a slide page — the stage stays 16:9
   and doesn't letterbox oddly.
9. Mark Complete: on the last page of a lesson without a gating quiz, start
   presenting → Mark Complete is still clickable, and clicking it completes
   the lesson without leaving fullscreen.
10. Instructor editor: type a long paragraph into a section with a fenced code
    block. Typing is smooth with no per-keystroke flicker; the preview settles
    ~200ms after you stop.
11. On a phone (or with `document.fullscreenEnabled` stubbed false): no
    Present button anywhere, and nothing else breaks.

## Assumptions

Implemented unattended on `feat/phase-62-player-ux-polish`. Deviations from the
letter of the spec, all deliberate:

1. **Header pieces are conditionally rendered, not `hidden`-classed** (task B).
   The spec said apply `hidden`; task E then asks for a test that the lesson
   title is gone from the DOM while presenting. A Tailwind `hidden` class is
   invisible to jsdom (no stylesheet), so that assertion is only testable with
   conditional rendering. Same visual result, no dead DOM.
2. **The header block collapses via a `headerHasContent` flag.** With only Mark
   Complete surviving, an always-present `mb-6` would leave a 24px gap above the
   stage on pages where Mark Complete does *not* show (mid-lesson, or when the
   quiz gates completion). `headerHasContent = !isPresenting || showMarkComplete
   || showCompletedBadge` swaps `mb-6` for `hidden` in exactly that case.
3. **Attachments cap lives on the file list, not the card body.** `shrink-0` on
   the `Card` as specified, but `max-h-40 overflow-y-auto` on the inner list so
   the "Lesson Materials" heading stays put while the files scroll under it.
4. **The stage aspect ratio uses `aspect-video` + `height: auto` + ONE
   container-query width cap** (`max-w-[calc(100cqh*1.7778)]`), not a cq cap on
   both axes. Measured in Chrome: capping both axes with cross-axis `cqh`/`cqw`
   left one of the two resolving against a stale container size after a
   relayout (ratios of 4.07 and 0.83 observed). With height derived from the
   ratio there is only one cross-axis constraint and the ratio held at 1.778
   across every real relayout tested. `max-h-full` remains as the no-container-
   query fallback clamp.
5. **`SectionEditor` uses a local `DebouncedMarkdownPreview` component** rather
   than a bare `useDebounce` call in the editor body. Hooks can't be called
   inside `previewCards.map()`, and one pattern for all three previews beats two.
6. **Lint reports 1 warning, not 0**: `ErrorBoundary.tsx:117`
   (`react-refresh/only-export-components`). Pre-existing on `main` and in a
   file this phase does not touch. 0 errors.

Manual click-through: steps 2, 5, 7, 8, 10 and 11 were executed in a visible
Chrome window and passed (evidence in the phase handoff). Steps 1, 3, 4, 6b and
9 — everything that needs the browser to actually *be* in fullscreen — could not
be automated: `requestFullscreen()` from the extension is rejected with
`TypeError: Permissions check failed` because it lacks a genuine user gesture.
Those paths are covered by `CoursePlayerPage.test.tsx` (which fakes the
Fullscreen API end to end, including paging into the quiz while presenting and
Mark Complete surviving) but still want one human pass.
