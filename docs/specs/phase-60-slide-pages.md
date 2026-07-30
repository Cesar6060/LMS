# Phase 60 — Slide-style lesson pages

## Goal

Let each lesson page be delivered either as today's scrolling markdown
document or as a **PowerPoint-style slide**, chosen **per page**. The
infrastructure already exists — since Phase 53 a lesson is an ordered list of
`LessonSection` "pages" rendered one at a time with prev/next, dots, arrow
keys, and a saved resume position — so this phase is a presentation-layer
change plus one tiny backend field: `LessonSection.layout` (`doc` | `slide`,
default `doc`). Content stays markdown in both layouts. Slide pages render on
a large centered "stage" with big typography, animated page transitions, an
optional fullscreen present mode, and syntax-highlighted code blocks; long
content scrolls *inside* the slide rather than being cut off. Existing pages
all default to `doc`, so nothing changes anywhere until the instructor flips
a page — this is the gradual migration path the user asked for. The
instructor editor gets a per-page Doc/Slide toggle and a preview-as-slide
mode.

### End state

- Student player: doc pages look exactly as today; slide pages render as a
  slide stage filling the content area (sidebar untouched — stays visible and
  student-controlled as today). A lesson can freely mix doc and slide pages.
- Page transitions actually animate (today's `animate-in` classes are dead —
  `tailwindcss-animate` was never installed).
- Fullscreen present mode: button + `F` key on slide pages, `Esc` exits;
  header/sidebar hidden while presenting; arrow keys keep working.
- Code blocks are syntax-highlighted in the player (both layouts) and in the
  editor preview.
- Instructor editor: each page row has a Doc/Slide toggle (real buttons, not
  a bare dropdown); preview shows the page as students will see it,
  including a slide-styled preview for slide pages.
- Quiz page, completion gating, progress/resume, XP — all unchanged.

## Out of scope

- Re-chunking existing course content into slide-sized pages (ROB101 /
  JAVA101 populate commands keep their current sections; everything stays
  `layout='doc'` until flipped by hand in the editor). No seed-command
  content edits, no prod reseeding.
- Any new content block types (images-per-slide, multi-video, columns,
  speaker notes, slide themes/backgrounds). Markdown + optional YouTube
  video per page, same as today.
- Auto-fit/shrink-to-fit typography (decided: long content scrolls inside
  the slide).
- Renaming `LessonSection` or any API routes; `layout` is an additive field.
- Auto-collapsing or hiding the sidebar on slide pages (decided: sidebar
  behavior unchanged; only fullscreen present mode hides chrome).
- Touching the dormant `Lesson.content` / `video_*` columns.
- The unpaginated lesson-list N+1 noted in Phase 53 (pre-existing).

## Key decisions (from scoping interview)

1. **Mix level = per page.** `layout` lives on `LessonSection`, not Lesson or
   Course. A single lesson can open with a slide, follow with a long doc
   page, and close with slide recaps.
2. **Sidebar stays, student controls it.** The slide stage fills whatever
   space remains next to the (collapsible) sidebar. Only fullscreen present
   mode goes chrome-less.
3. **Overflow scrolls inside the slide.** No content rewrite required for
   day one; re-chunking happens gradually in later content passes.
4. **Extras all in scope:** transitions (fixes the dead `animate-in`
   classes), instructor slide preview, syntax highlighting, fullscreen
   present mode.
5. **Default `doc` everywhere** — zero behavior change on deploy until pages
   are flipped.

## Backend tasks

- [x] `LessonSection.layout`: `CharField(max_length=10,
      choices=[('doc','Document'),('slide','Slide')], default='doc')` in
      `backend/courses/models.py`; schema migration (`AddField` with default
      — safe, no data migration needed).
- [x] Serializers (`backend/courses/serializers.py`): add `layout` to
      `LessonSectionSerializer`, `LessonSectionCreateSerializer`, and the
      bulk-create item serializer. Invalid value must 400 via choices
      validation. `LessonSerializer`'s nested read-only `sections` picks it
      up automatically — verify field list includes it.
- [x] `clone_course_for_demo.py`: copy `layout` in the section deep-copy.
      (No code change needed — `_clone()` copies ALL concrete fields via
      `pk=None` + save, so `layout` is preserved automatically; proven by
      `test_clone_preserves_section_layout`.)
- [x] [P] Tests (`backend/courses/tests/`): create/update section with
      `layout='slide'`; omitted layout defaults to `'doc'`; invalid layout →
      400; bulk create with mixed layouts; layout editable by instructor
      only (reuse existing permission test pattern — students already can't
      write sections); clone command preserves layout; lesson detail
      response includes `layout` in nested sections.
- [ ] After merge/deploy: apply the new migration to Neon (single additive
      column, default `'doc'`, no backfill needed) — note in handoff.

## Frontend tasks

- [x] Types (`frontend/src/types/index.ts`): `layout: 'doc' | 'slide'` on
      `LessonSection`; mirror in the local interfaces duplicated at the top
      of `CoursePlayerPage.tsx` (`LessonDetail` etc.).
- [x] Services (`frontend/src/services/courses.ts`): include `layout` in
      section create/update/bulk payload types.
- [x] [P] Shared markdown renderer: extract a `LessonMarkdown` component
      (react-markdown + remark-gfm + `rehype-highlight` with the common-
      language bundle) and use it in the player (both layouts) and both
      SectionEditor preview call sites. Include a highlight.js theme that
      works in light *and* dark (e.g. github / github-dark switched by the
      `dark` class), scoped so it doesn't fight `prose-invert`.
- [x] [P] Install + register `tailwindcss-animate` in
      `tailwind.config.mjs` — this revives the player's existing
      `animate-in fade-in slide-in-from-*` classes (currently no-ops) and
      powers slide transitions. Verify built CSS actually contains
      `animate-in` afterwards.
- [x] `SlideStage` component (`frontend/src/components/lesson/`): renders a
      slide-layout page — centered stage with generous padding, max-width
      ~16:9 proportions within the available content area, scaled-up
      typography (`prose-xl`-ish; keep the user's bigger-type preference in
      mind), optional video block, and `overflow-y: auto` on the stage body
      for long content. Directional slide transition on page change.
- [x] `CoursePlayerPage.tsx`: branch `renderSectionContent()` on
      `currentSection.layout` — `doc` renders today's card unchanged,
      `slide` renders `SlideStage`. Quiz page and all page-count/nav/resume
      math (`contentPageCountFor`) untouched.
- [x] Fullscreen present mode: button on the slide stage + `F` shortcut
      (skip when focus is in an input, same guard as arrow keys); use the
      Fullscreen API on the player content element; `Esc` exits natively;
      while fullscreen, hide header/sidebar and keep prev/next + arrow-key
      navigation and the page dots visible. Doc pages inside a fullscreen
      session render normally (scrollable) so mixed lessons don't break the
      flow.
- [x] SectionEditor (`frontend/src/components/lesson/SectionEditor.tsx`):
      per-page Doc/Slide segmented toggle (two real buttons with labels, not
      a dropdown), persisted via `updateLessonSection`; preview pane renders
      slide pages with the slide styling ("preview as slide"), doc pages as
      today.
- [x] Frontend tests where the repo has patterns for them: added
      `SlideStage.test.tsx` (vitest + testing-library, matching the existing
      component-test pattern) covering title/markdown render, Present/Exit
      button states + callback, fullscreen-unavailable gating, and the empty
      state; plus tsc/lint + manual flow below.

## Verification

- [x] `docker compose restart backend`, then backend suite in container:
      full `pytest` green including the new section-layout tests.
- [x] `makemigrations --check` clean after the new migration is committed
      (exactly one new migration).
- [x] `cd frontend && npx tsc --noEmit` — 0 errors.
- [x] `cd frontend && npm run lint` — 0 errors.
- [x] `/verify-stack` PASS, output shown.
- [x] `grep -c "animate-in" frontend/dist/assets/index-*.css` > 0 after a
      build (proves transitions are live).
- [x] Manual flow (instructor): open a ROB101 lesson in the editor → flip
      page 1 to Slide → preview shows slide styling → save.
- [x] Manual flow (student): open that lesson → page 1 renders as a slide
      with transition; page 2 (doc) renders exactly as before; arrows, dots,
      and resume (`current_section`) still work across mixed layouts; a
      long slide page scrolls inside the stage; `F` enters fullscreen, `Esc`
      exits, arrows navigate while presenting; quiz page unchanged and
      still gates completion when `requires_quiz` is on.
      (Fullscreen note: the automated browser window was hidden, and Chrome
      refuses `requestFullscreen` on hidden documents — verified the full
      chain (F key / Present button → requestFullscreen on the player
      content element → fullscreenchange → header hidden, Exit button,
      arrows + dots working, exitFullscreen) against a mocked Fullscreen
      API; the unmocked remainder is native browser behavior.)
- [x] Manual: a JAVA101 code block shows syntax highlighting in both light
      and dark mode, in player and editor preview.
- [x] Demo clone: run `clone_course_for_demo` against a course with a slide
      page; cloned section keeps `layout='slide'`.
