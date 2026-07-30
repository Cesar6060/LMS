# Phase 61 — Slide deck import (PDF → slide pages)

## Goal

Let an instructor author a deck in PowerPoint / Google Slides / Canva, export
it to PDF, and upload that PDF in the lesson editor. The client rasterizes
each PDF page with pdf.js and creates one `LessonSection` per slide with
`layout='slide'` and a new per-section **image** — the slide renders as that
image on the phase-60 slide stage. The PDF's text layer is extracted per page
and stored as alt text (image slides aren't otherwise selectable or
searchable). Around the import, the editor gains the page-level operations
the workflow needs: an **insert-page-below** affordance on every row (so a
markdown page can be placed between two slides without 15 chevron clicks) and
a pre-import preview grid where individual slides can be deselected. All
rasterization happens client-side — the backend (Render free tier, no task
queue, no LibreOffice/poppler) only ever receives finished images, one small
multipart request per slide.

### End state

- Lesson editor: an "Import slides (PDF)" button opens a modal — drop/pick a
  PDF → preview grid of rendered pages with per-page deselect → Import →
  progress bar ("Uploading slide 7 of 24") → new slide pages appended after
  the lesson's existing pages. Partial failure keeps what succeeded and
  offers "Retry remaining".
- Each page row shows a thumbnail for image slides; the edit modal lets the
  instructor edit the alt text.
- Every row gets an "insert page below" button; the inserted page defaults
  to the layout of the row it was inserted under (so a page added between
  slides is a slide-stage text page; below a doc page it's a doc).
- Student player: image slides fill the slide stage (`object-contain`,
  title suppressed — it's baked into the image); markdown slide pages,
  doc pages, present mode, nav, resume, quiz gating all unchanged.

## Key decisions (from scoping interview + code exploration)

1. **Interview answers (2026-07-29):** inserted-between pages default to
   **slide** layout (via layout inheritance from the anchor row); insert UX
   is a per-row **insert-below button** (not drag-and-drop, not
   append+chevrons); import failure is **keep + retry remaining** (not
   all-or-nothing); imported slides **append at end** (no position picker,
   no replace mode).
2. **Prior decisions carried from the phase-60 handoff:** per-page mixing
   stays (no lesson-level layout field); import path is PDF-export +
   client-side pdf.js rasterization; PPTX parsing, published-embed iframes,
   and slides→markdown conversion are rejected; PDF text layer becomes alt
   text.
3. **Image lives on `LessonSection`** (`image` + `image_alt`), not on a new
   model and not on `LessonAttachment` (attachments are lesson-scoped,
   capped at 10/lesson, and have no section linkage).
4. **`image` is NOT writable through the normal section create/update/bulk
   serializers** — it is set only by the new import endpoint. This protects
   it from the editor's full-object PUTs (SectionEditor sends every field on
   update; a writable image field would be wiped by every save).
   `image_alt` IS writable through the normal update serializer.
5. **One multipart request per slide** (new endpoint, client loops pages
   with a small progress pipeline). No bulk-multipart request: Django's
   1000-field default and the unknown hosting body-size ceiling make one
   giant request fragile, and per-page requests are what makes keep+retry
   possible.
6. **Rasterization target:** render each page at 1920 px width (scale from
   the PDF viewport), encode `canvas.toBlob('image/webp', 0.9)` with PNG
   fallback when WebP encoding is unavailable. Client caps: PDF ≤ 50 MB,
   ≤ 100 pages; server caps: image ≤ 5 MB (`SLIDE_IMAGE_MAX_UPLOAD_BYTES`),
   lesson section count ≤ 200 after import.
7. **Signed-URL reality (accepted):** R2 media URLs are presigned with a
   ~1 h TTL (`querystring_auth: True`, settings.py:186-191), so slide image
   URLs expire and differ per fetch. The player fetches lesson detail on
   load, which is fine for normal sessions; a player tab left open > 1 h can
   show broken images until the lesson is re-entered. No mitigation this
   phase; do not cache image URLs client-side.
8. **Demo accounts are blocked from the import endpoint**
   (`require_not_demo` → 403 `demo_blocked`): uploads write to shared R2
   storage, which falls under the demo policy's shared-surface rule even
   though ordinary section edits are learning writes.
9. **Blob lifecycle:** the section DELETE view deletes the image blob before
   the row (mirrors the attachment DELETE pattern, views.py:2590-2609).
   `clone_course_for_demo` must **duplicate** the blob under a new name —
   `_clone()` copies the FileField *name*, so without duplication the
   original and clone would share one blob and deleting either section
   would break the other. The demo seed command must delete demo slide
   blobs before wiping demo courses, or every reseed orphans a deck's
   worth of R2 objects.
10. **Section titles** default to "Slide 1" … "Slide N" (editable). A
    section with an image renders the image in both layouts (doc: image at
    the top of the doc card; slide: image fills the stage) so flipping the
    toggle never shows an empty page.

## Out of scope

- Parsing PPTX/Google-Slides/Canva formats directly, embedding published
  decks, or converting slides to markdown (all rejected in scoping).
- Server-side PDF processing of any kind (no poppler/PyMuPDF/pdf2image, no
  task queue).
- Re-import / update-in-place of a changed deck (delete the slide pages and
  import again; the "replace all pages" mode was explicitly not chosen).
- Speaker notes, per-slide video, slide themes/backgrounds, animations
  within a slide.
- Drag-and-drop page reordering (insert-below + chevrons only; dnd-kit
  stays confined to ManageCoursePage).
- Public/cacheable media URLs, CDN custom domain, or TTL changes for R2
  signed URLs.
- Retroactive demo-block or magic-byte hardening of the existing attachment
  upload endpoint (pre-existing; note for a future audit phase).
- OCR for image-only PDFs (if a page has no text layer, alt text is empty
  and editable by hand).
- Storage-quota accounting per instructor/course.

## Backend tasks

- [x] `LessonSection.image = models.ImageField(upload_to='slide_images/%Y/%m/', blank=True)`
      and `image_alt = models.TextField(blank=True)` in
      `backend/courses/models.py` (~:626). Migration `0023` (additive,
      safe). Pillow already in requirements.
- [x] Serializers (`backend/courses/serializers.py`): read serializer
      (`LessonSectionSerializer`, :77-83) gains `image_url`
      (SerializerMethodField → `obj.image.url` if set, wrapped with the
      `request.build_absolute_uri()` pattern from :70-74, else `None`) and
      `image_alt`. `LessonSectionCreateSerializer` and the bulk item
      serializer gain **only** `image_alt` (never `image` — decision 4).
      Nested `LessonSerializer.sections` picks the new fields up.
- [x] New endpoint `POST /api/courses/lessons/<lesson_id>/sections/import-slide/`
      (`courses/urls.py` + `courses/views.py`, next to the bulk view at
      :2748): multipart fields `image` (required file), `title`,
      `image_alt` (optional text). Creates ONE section with
      `layout='slide'`, order = `Max(order)+1` (same pattern as :2644),
      inside `transaction.atomic()`. Guards, in order:
      `IsAuthenticated`, `require_course_instructor`,
      `require_not_demo` (from `core.demo`), throttle
      `core.throttling.ClientIPScopedWriteRateThrottle`, extension
      allowlist (png/jpg/jpeg/webp), size ≤
      `settings.SLIDE_IMAGE_MAX_UPLOAD_BYTES` (new constant = 5 MB in the
      settings block at ~:349-353), Pillow magic-byte check (copy the
      avatar sequence exactly: `Image.open` → read `.format` → `verify()`
      → `seek(0)`, accounts/views.py:220-234), and reject if the lesson
      already has ≥ 200 sections. Returns the created section via the read
      serializer (201).
- [x] Section DELETE (`lesson_section_detail`, views.py:2655-2697): delete
      `section.image` blob (`.delete(save=False)`) before deleting the row,
      keeping the existing gap-close logic intact.
- [x] `clone_course_for_demo.py`: duplicate the image blob for cloned
      sections (read original file, `image.save(new_name, ...)` on the
      clone) — decision 9.
- [x] `seed_demo_account` (or wherever demo courses are wiped): delete
      slide image blobs of demo-owned sections before the wipe — decision 9.
- [x] [P] Tests (`backend/courses/tests.py`, follow `TestLessonAttachments`
      :2597 for the tmp-MEDIA_ROOT fixture and multipart posts, and the
      bulk-create permission matrix :1581-1678):
      - import-slide happy path: 201, section has `layout='slide'`, correct
        appended order, response includes `image_url` + `image_alt`;
        title defaults applied.
      - permission matrix: student 403, unauthenticated 401, wrong-course
        instructor 403, demo user 403 with `demo_blocked` code.
      - validation: bad extension 400, oversize 400 (settings override),
        text file with .png name 400 (magic-byte), missing file 400,
        201st section rejected.
      - `image` ignored if posted to the normal create/update/bulk
        endpoints; `image_alt` editable via PUT and preserved by a full
        editor-style PUT.
      - DELETE removes the blob from storage; lesson detail nests
        `image_url` in sections.
      - clone duplicates the blob (names differ, both files exist; deleting
        the original section leaves the clone's file intact).

## Frontend tasks

- [x] Types (`frontend/src/types/index.ts` :70-81): `image_url: string |
      null` and `image_alt: string` on `LessonSection`; mirror in
      CoursePlayerPage's local interfaces.
- [x] Services (`frontend/src/services/courses.ts`):
      `importSlideSection(lessonId, {image: Blob, title, imageAlt},
      signal?)` posting FormData to `.../sections/import-slide/` (follow
      `uploadLessonAttachments` :487-503; thread an `AbortSignal` through
      for cancel); add `image_alt` to the update payload type (:541-548).
- [x] [P] `src/lib/pdfSlides.ts` (+ install `pdfjs-dist`; worker via
      `import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'` →
      `GlobalWorkerOptions.workerSrc`; add an `optimizeDeps` entry in
      vite.config.ts if dev pre-bundling chokes; run
      `docker compose exec frontend npm install` too — see gotcha in the
      phase-60 handoff). Pure functions: `loadDeck(file)` → page count +
      handles; `renderPage(page)` → Blob (1920 px wide, WebP 0.9, PNG
      fallback when `toBlob` yields null/non-webp) + extracted text-layer
      string (joined items, trimmed, capped ~1000 chars) for alt text.
      Keep DOM/canvas touching thin so the orchestration logic is testable
      with pdf.js mocked (jsdom has no canvas 2d context).
- [x] Import modal in `SectionEditor.tsx` (third Radix Dialog in the
      existing fragment, same `max-w-4xl` scroll-body + footer pattern as
      paste-to-split :629-754): dropzone (lift visuals/validation/error
      copy from `AttachmentUploader.tsx` :120-149; accept `.pdf`, reject
      > 50 MB or > 100 pages client-side) → thumbnail preview grid with
      per-page deselect (mirrors paste-to-split's per-card remove) →
      Import: sequential per-page upload driven by `ProgressBar`
      ("Uploading slide 7 of 24"), Cancel via AbortController (stops after
      the in-flight page, keeps what's imported). On failure: keep
      succeeded pages, mark failed ones in the grid, "Retry remaining"
      button. On finish: toast ("Imported 24 slides"), `loadSections()`.
- [x] Editor rows (`SectionEditor.tsx` :327-427): thumbnail (small
      `image_url` img) in the section-info block for image slides; edit
      modal shows the image preview + an alt-text textarea
      (`image_alt` through the existing PUT); thread `image_alt` through
      `EditingSection`, `openAddSection`/`openEditSection`, the save
      payload, and `handleLayoutChange` so full-object PUTs don't drop it.
- [x] Insert-below button on every row: opens the add-page modal, new page
      inherits the anchor row's `layout`, then create (appends) +
      `reorderLessonSections` with the full permutation to slot it after
      the anchor. Chevrons/delete unchanged.
- [x] `SlideStage.tsx`: optional `image?: {url, alt}` prop — when set,
      suppress the title `<h3>` (:60) and render an `object-contain` img
      filling the stage body instead of `LessonMarkdown`; adjust the
      empty-state condition (:70-78). `CoursePlayerPage.tsx` passes the
      image through at the layout branch (:584-596); doc branch renders the
      image (if set) at the top of the doc card.
- [x] [P] Frontend tests (vitest, patterns from `SlideStage.test.tsx` and
      `splitSections.test.ts`): pdfSlides orchestration with pdf.js mocked
      (page loop, alt-text extraction/truncation, WebP→PNG fallback);
      SlideStage image mode (img rendered with alt, title suppressed,
      markdown path untouched); import pipeline unit (sequential order,
      keep-on-failure, retry set, abort behavior) with the service mocked.

## Verification

- [x] `docker compose restart backend`; full `pytest` in the container
      green including every new test above; `makemigrations --check` clean
      (exactly one new migration, 0023).
- [x] `cd frontend && npx tsc --noEmit` — 0 errors; `npm run lint` — 0
      errors; vitest suite green.
- [x] `/verify-stack` PASS, output shown.
- [x] Manual (instructor): export a real Google Slides deck (≥ 10 pages,
      with text) to PDF → Import slides into a local lesson → deselect one
      page in the preview grid → import → progress bar advances → rows
      show thumbnails titled "Slide N"; open one, edit its alt text, save;
      insert a markdown page between two slides via insert-below (defaults
      to slide layout) and confirm it lands in position; delete a slide
      page and confirm the lesson renumbers.
- [x] Manual (student): open that lesson — slides render crisply on the
      stage (light + dark), the inserted markdown page renders on the
      stage between them, present mode + arrows/dots/resume work across
      image and markdown pages, quiz gating unchanged; img alt text
      present in the DOM.
- [x] Manual (failure path): kill the backend mid-import — succeeded pages
      survive, grid marks the failures, Retry remaining completes the deck.
- [x] Demo: import-slide as the demo user → 403 `demo_blocked`; run
      `clone_course_for_demo` on a course with an image slide → cloned
      section shows the image and its file name differs from the original.
- [ ] After merge/deploy: apply migration 0023 to Neon (additive columns,
      no backfill) — same MCP procedure as phases 59/60; note in handoff.
