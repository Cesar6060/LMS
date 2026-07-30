# Handoff: Phase 60 — Per-page doc/slide lesson layouts

## Current state
Phase 60 complete on `feat/phase-60-slide-pages`;
**PR #78 open on Cesar6060/LMS, awaiting user merge**. Delivered:
- Backend: `LessonSection.layout` ('doc'|'slide', default 'doc') in
  courses/models.py; migration 0022 (applied locally, NOT yet on Neon);
  field in both section serializers; 8 new tests (TestSectionLayout in
  courses/tests.py + test_clone_preserves_section_layout in
  test_seed_demo_account.py). clone_course_for_demo needed NO change —
  `_clone()` copies all concrete fields.
- Frontend: SlideStage.tsx (stage, internal scroll, transitions, Present
  button), LessonMarkdown.tsx (shared renderer w/ rehype-highlight;
  scoped light/dark theme in lessonMarkdown.css, regenerate via
  `npm run gen:hljs-theme`), CoursePlayerPage.tsx (layout branch,
  fullscreen present mode, F key, navDirection), SectionEditor.tsx
  (per-row Doc/Slide toggle + modal control + slide preview),
  tailwindcss-animate registered (animate-in classes now real),
  SlideStage.test.tsx (5 vitest cases).
Verified twice: /verify-stack PASS — 639 backend tests (in container),
tsc 0, eslint 0, vitest 62, prod build OK, animate-in in built CSS.
Manual browser flows all passed (instructor flip+preview, student mixed
lesson, in-stage scroll, arrows/dots/resume, highlighting light+dark).
Reviews: code-reviewer APPROVE WITH NITS (all fixed, 2nd commit);
adversarial-tester 36 HELD / 0 BROKEN; db-migration-checker SAFE.

## In progress / not done
- SHIPPED 2026-07-30 (user instructed): migration 0022 applied to Neon
  (via Neon MCP run_sql_transaction — exact sqlmigrate SQL + migration
  row; column verified, 264 prod sections all 'doc'), THEN PR #78
  merged (02:38Z). Post-deploy verified: deep health 200 x3; prod
  lesson API returns `layout`; new Pages bundle live (LessonMarkdown
  chunk); prod player renders docs + highlighted java, 0 console errors.
- A stray `feat/phase-60-slide-pages` branch was pushed to the archived
  origin repo (dev-learning-platform) by mistake; deletion was
  permission-blocked. Harmless — delete manually if it bothers you.

## Next steps
1. **PHASE 61 — slide deck import (plan next session).** User's real
   intent behind "slides": author in PowerPoint/Google Slides/Canva and
   upload the deck; each slide becomes a lesson page; must be able to
   remove a slide and insert markdown pages between slides. Scoping
   interview settled direction (2026-07-30, this session):
   - KEEP per-page mixing (phase 60 model) — "remove a slide" /
     "md page in between" are page-level ops; a per-lesson md-vs-slide
     switch would forbid them. No lesson-level layout field.
   - Import path: "export deck to PDF, upload PDF" — one pipeline covers
     all three tools; rasterize per page (pdf.js client-side; Render
     free tier can't run LibreOffice for PPTX) → one LessonSection per
     slide with layout='slide' + an IMAGE (new field — images-per-slide
     was explicitly out of scope in phase 60). Bulk-create pattern
     exists (paste-to-split). Storage solved: prod media is on R2
     (USE_R2, settings.py ~153); attachments already upload there.
   - Rejected: PPTX parsing (LibreOffice/paid API), published-embed
     iframes (public publishing, no per-slide pages, nav conflict),
     slides→markdown conversion (loses visual design).
   - Mitigation to spec: extract PDF text layer per page as alt text
     (image slides aren't selectable/searchable).
   - Open scoping Q: do inserted md-between pages default to doc
     (scrolling) or slide (text on stage)? Both supported; pick default.
   Write docs/specs/phase-61-slide-import.md first.
2. User: flip a real page to Slide in the prod editor when ready (one
   real `F`-key fullscreen press is the only thing never tested on a
   visible window).
3. Deferred review nits (any future phase): debounce editor live preview
   (re-highlights per keystroke); attachments on a last slide page steal
   stage height when long; Mark Complete hidden while presenting a slide.
4. Pre-existing items re-flagged: empty-body section create is valid;
   no-slash POST /sections returns DEBUG HTML 500 locally (prod: 404).
5. Carried: XP double-award schema fix, JAVA101 answer-rotation reseed,
   phase-56 regression click-through, school-device login test, Sentry
   LoginPage TypeError, promote warning-filter 3-way check to a test.

## Decisions made
- Present mode fullscreens the player content element (header/sidebar
  live outside it) and `isPresenting` compares fullscreenElement to that
  exact element — so fullscreening the YouTube embed can't flip the UI.
- hljs theme CSS is GENERATED (frontend/scripts/gen-hljs-theme.mjs) from
  highlight.js github/github-dark, scoped under `.lesson-markdown`, and
  committed — no runtime highlight.js dep (it's devDependencies-only).
- Local ROB101 lesson 254 page 1 left as layout='slide' (manual-test
  artifact; local data only, harmless).

## Gotchas discovered
- Frontend deps must be installed INSIDE the frontend container too
  (`docker compose exec frontend npm install`) or Vite 500s on import.
- Host `npm install` keeps dropping `@rollup/rollup-darwin-arm64` (npm
  optional-deps bug); fix: `npm install --no-save @rollup/rollup-darwin-arm64`.
- Prod build requires VITE_API_URL set (repo guard in vite.config.ts).
- Chrome refuses requestFullscreen when the window is hidden/occluded
  ("Permissions check failed") — automated fullscreen tests need a
  visible window or a mocked Fullscreen API.

## Files to read first
1. docs/specs/phase-60-slide-pages.md — checklist (1 open post-merge item).
2. frontend/src/pages/courses/CoursePlayerPage.tsx — layout branch +
   present mode wiring.
3. frontend/src/components/lesson/SlideStage.tsx + LessonMarkdown.tsx.
4. backend/courses/tests.py TestSectionLayout (~line 1679).
