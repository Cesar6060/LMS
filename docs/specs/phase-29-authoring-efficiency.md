# Phase 29 — Authoring efficiency: paste-to-split lesson sections

## Goal
Adding lesson content today is slow: an instructor creates lesson "sections"
(slides) **one at a time** through a modal in `SectionEditor.tsx`, each a
separate API call with a full list reload after. This phase adds a **paste-to-split**
authoring path: the instructor pastes one markdown document, it is split on
`---` (thematic-break) lines into N sections, shown as **editable preview cards**
to confirm/adjust, then created in **one atomic backend request** that appends
them after any existing sections. Two quality-of-life improvements ride along:
a **live markdown preview** in the single-section editor (which currently has
none), and **auto-titling** each split chunk from its first heading line. The
existing one-at-a-time modal stays for fine edits — this is additive, not a
rewrite of the editor.

## Decisions locked this session (2026-07-19)
- **Core = paste-to-split, create NEW sections only.** Not round-trip editing of
  existing sections; not an inline modal-replacement editor. Both were considered
  and deferred — keep this phase focused and shippable.
- **Delimiter = `---` on its own line** (markdown thematic break). Each `---`
  ends one section and starts the next. Not `##` headings, not user-choosable —
  a single, explicit, unambiguous rule.
- **Split happens client-side.** The browser parses the pasted blob into chunks
  so it can render **editable preview cards** the instructor confirms/edits
  before anything is saved. The server receives the final array, not the raw blob.
- **Backend create = one new atomic bulk endpoint** in a DB transaction
  (all-or-nothing, server-assigned ordering). Not a client-side loop of the
  existing per-section POST (which risks half-created sections on partial failure).
- **Three add-ons, all in scope:** (1) editable preview cards before saving;
  (2) live markdown preview in the single-section editor modal; (3) auto-title
  each chunk from its first heading line.
- **Bulk paste is text-only.** Split sections get `video_type='none'`. Videos are
  still added/edited per-section via the existing modal afterward. The `---`
  splitter is **code-fence aware** — a `---` line inside a ```` ``` ```` fenced
  block does NOT split (critical: the Java course is code-heavy).

## Out of scope (do NOT touch)
- **Round-trip / bulk EDIT of existing sections** (editing all sections as one
  combined doc and diffing create/update/delete/reorder). Deferred.
- **Replacing the modal** with an inline stacked multi-section editor. The modal
  stays; we add a second entry point beside it.
- **New section `type` field / code / image section types.** The model stays
  markdown `content` + optional video; no migration to the model's shape.
- **Video handling in bulk paste** (parsing YouTube URLs out of pasted text,
  per-chunk video type). Split chunks are always `video_type='none'`.
- **Question / quiz bulk authoring.** This phase is lesson *sections* only.
  (`LessonQuestion` has no reorder or bulk endpoint either — leave as-is.)
- **Changing student-facing rendering** (`CoursePlayerPage`, `SectionContent`).
  New sections flow through the existing read path unchanged.
- **`Lesson.content` legacy blob behavior** — untouched; sections still win in
  the player when present.

## Relevant existing code (from Phase 29 exploration)
- Model `LessonSection` — `backend/courses/models.py:479`: fields `lesson`,
  `title` (optional), `content` (markdown), `video_type` (none/youtube/vimeo),
  `video_id`, `order`. `unique_together = ['lesson','order']` (`:522`). **No
  `type` field.**
- Write serializer `LessonSectionCreateSerializer` — `serializers.py:34`,
  fields `['id','title','content','video_type','video_id','order']`, single-object.
- Section endpoints — `urls.py:59-61`, views `lesson_sections` (POST auto-assigns
  `order = max+1`, `views.py:1953`), `lesson_section_detail` (`:1977`),
  `lesson_sections_reorder` (`:2022`, two-pass +10000 offset trick to dodge
  `unique_together` — reuse this pattern if needed).
- Permissions — `courses/permissions.py`: `require_course_instructor`,
  `is_course_instructor` (POST is instructor-only today; match it).
- Frontend editor — `frontend/src/components/lesson/SectionEditor.tsx` (modal,
  `openAddSection` `:82`, `handleSaveSection` `:108`); services
  `frontend/src/services/courses.ts:515-552` (`createLessonSection` etc.);
  type `LessonSection` `frontend/src/types/index.ts:71`.
- Live-preview pattern to copy — `LessonEditorPage.tsx:343-371` (side-by-side
  `<textarea>` + `<ReactMarkdown remarkPlugins={[remarkGfm]}>`).

## Split semantics (the client-side parser — correctness core)
Given the pasted string, produce an ordered list of `{title, content}` chunks:
1. Scan line by line. Track fenced-code state: a line matching `^\s*```` (three
   backticks, optionally with a language, or `~~~`) toggles "inside code fence".
2. A line matching `^\s*---\s*$` **while NOT inside a code fence** is a delimiter:
   it ends the current chunk and starts a new one. The delimiter line itself is
   discarded (not part of either chunk).
3. After splitting, for each chunk: trim leading/trailing blank lines.
   **Drop chunks that are empty/whitespace-only** (handles leading/trailing/
   consecutive `---`).
4. **Auto-title:** if a chunk's first non-blank line is a heading
   (`^\s*#{1,6}\s+(.+)$`), use the captured text as the chunk `title` **and
   remove that heading line from the chunk body** (avoids the title rendering
   twice). Otherwise `title = ''` (blank; the field is optional).
5. If the whole paste has no delimiter, the result is a single chunk (still valid
   — one section created). If the paste is empty/all-whitespace, result is an
   empty list → the "Add sections" action is disabled.

Edge cases to cover in the preview/parser: `---` inside a ```` ``` ```` block does
NOT split; a chunk whose only content was a heading (now stripped) with no body
becomes an empty-body section — allow it (content may be blank) but keep the title.

## Backend tasks
- [x] **1. Bulk-create serializer** in `backend/courses/serializers.py`. Add a
  wrapper that validates a list of sections, e.g. `LessonSectionBulkCreateSerializer`
  with `sections = LessonSectionCreateSerializer(many=True)` (or a `ListField`),
  `min_length=1`, a sane `max_length` (e.g. 50) to bound abuse. Incoming `order`
  is ignored (server assigns it) — either drop it from the child or overwrite on
  save. Each child validates `title`/`content`/`video_type`/`video_id` as today.
- [x] **2. Bulk-create view** `lesson_sections_bulk_create` in
  `backend/courses/views.py`. `@api_view(['POST'])`, `IsAuthenticated`, and
  **instructor-only** via `require_course_instructor` (match `lesson_sections`
  POST). Behavior:
  - Wrap in `transaction.atomic()` — **all-or-nothing**.
  - Compute the starting order = `(max existing order for this lesson) + 1`
    (mirror the single-POST auto-assign at `views.py:1962`), then assign
    sequential `order` to each new section in list order. This appends the batch
    after existing sections and cannot collide with `unique_together=['lesson','order']`.
  - Bulk `create` the sections; return the created list (serialized with
    `LessonSectionSerializer`, `many=True`) with `201`.
  - Invalid body (empty list, bad child) → `400`, nothing created.
- [x] **3. URL** in `backend/courses/urls.py`: add
  `path('lessons/<int:lesson_id>/sections/bulk/', views.lesson_sections_bulk_create)`
  alongside the existing `sections/` and `sections/reorder/` routes (`urls.py:59-61`).
  Confirm it does not shadow `sections/<section_id>/` (int converter on the detail
  route means `bulk` won't be captured as an id — verify ordering/converter).
- [x] **4. No model/migration changes** — `LessonSection` shape is unchanged.
- [x] **5. Backend tests** in `backend/courses/tests.py`:
  - Instructor bulk-creates 3 sections on a lesson with 0 existing → 201, 3
    returned, `order` = 0,1,2 (or the lesson's existing convention).
  - Bulk-create on a lesson that already has 2 sections → new ones get
    `order` 2,3,… (appended, no `unique_together` collision).
  - **Atomicity:** a batch containing one invalid section → 400 and **zero**
    sections created (query count unchanged) — proves the transaction rolls back.
  - Empty `sections: []` → 400.
  - Non-instructor (enrolled student) → 403; unauthenticated → 401.
  - Wrong-course instructor (owner check) → 403.

## Frontend tasks
- [x] **1. Service method** in `frontend/src/services/courses.ts` (beside
  `createLessonSection`, `:521`): `bulkCreateLessonSections(lessonId, sections)`
  → `POST /courses/lessons/{lessonId}/sections/bulk/` with body
  `{ sections: [{ title, content, video_type: 'none', video_id: '' }, ...] }`.
- [x] **2. Client-side splitter** — a small pure function (e.g.
  `frontend/src/lib/splitSections.ts` or colocated util) implementing the "Split
  semantics" section above: input `string` → `Array<{ title: string; content: string }>`.
  Code-fence aware, drops empty chunks, auto-titles from first heading. Keep it
  pure/testable.
- [x] **3. Paste-to-split dialog** — a new modal (or a mode of the existing one)
  opened from a **"Paste to add sections"** button placed next to "Add Section"
  in `SectionEditor.tsx` (`:177` / empty-state `:198`). Flow:
  - Large `<textarea>` for the pasted markdown + a short hint ("Separate sections
    with a line containing only `---`").
  - **"Preview split"** runs the splitter and renders N **editable preview cards**,
    each showing an editable `title` input + editable `content` textarea (with the
    live markdown preview from add-on #4). Instructor can tweak titles/bodies and
    remove a card before saving.
  - Footer button **"Add N sections"** (disabled when 0 cards) → calls
    `bulkCreateLessonSections`, then reloads the section list (reuse the existing
    reload path) and closes.
  - On API error, surface it and keep the dialog open (nothing was created).
- [x] **4. Live markdown preview in the single-section editor** — add the
  side-by-side `react-markdown` + `remark-gfm` preview to the existing section
  modal's Content textarea in `SectionEditor.tsx` (`:362`), matching the pattern
  at `LessonEditorPage.tsx:343-371`. (Also reused inside the preview cards.)
- [x] **5. No type changes** — reuse `LessonSection`; the bulk payload is a subset
  (`title`, `content`, `video_type`, `video_id`). Add a local param type if needed.
- [ ] **6. (If trivial) a couple of unit assertions** for `splitSections` (fence
  awareness, empty-chunk drop, auto-title) if a frontend test runner exists;
  otherwise cover via the manual flow.

## Verification
Run `/verify-stack` first (must stay green), then the phase-specific checks.

- [x] **pytest** — `docker compose exec -T backend pytest`: baseline **196** plus
  the new bulk-endpoint tests all pass. The atomicity test must prove rollback
  (zero created on a bad batch).
- [x] **tsc** — `cd frontend && npx tsc --noEmit`: **0 errors**.
- [x] **lint** — `cd frontend && npm run lint`: **0 errors** (warning baseline ~23).
- [x] **Backend manual** — `curl`/DRF browsable API: POST the bulk endpoint as an
  instructor with 3 sections → 201, appended after existing; POST as a student →
  403; POST `{"sections": []}` → 400; POST a batch with one invalid section →
  400 and the section count is unchanged.
- [ ] **Manual click-through (hand to user — no browser automation in agent env):**
  1. As instructor, open a lesson editor → Sections tab → **"Paste to add sections"**.
  2. Paste a doc with 3 chunks separated by `---`, where each chunk starts with a
     `## Heading` and one chunk contains a ```` ```java ```` block that itself
     includes a `---` line.
  3. **Preview split** → exactly **3** cards; titles auto-filled from the headings;
     the `---` inside the code block did **not** create an extra section; live
     preview renders each card.
  4. Edit one card's title, delete another card → **"Add N sections"** →
     the sections appear appended after any pre-existing sections, in order.
  5. Open one new section in the single-section modal → the **live markdown
     preview** shows beside the textarea.
  6. Reload the page → the new sections persist with correct order and titles;
     the student player paginates through them correctly.

## Notes
- **Base branch:** cut `feat/phase-29-authoring-efficiency` from `lms/main` after
  PR #16 (Phase 28) merges. If #16 is still open, branch from merged main once it
  lands — do not stack on the phase-28 branch.
- Reuse the reorder view's transaction/ordering discipline (`views.py:2022`) as
  the reference for safe multi-write against `unique_together`.
- Commits: `feat:` for the endpoint + editor; split a `docs:` commit for this spec
  + the handoff. Conventional format, no Co-Authored-By (per CLAUDE.md).
- `PLAN.md` + `CLAUDE.md` are gitignored — not in the diff.
