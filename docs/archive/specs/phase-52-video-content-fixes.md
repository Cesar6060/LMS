# Phase 52 — Lesson Video & Content Bug Fixes

## Goal

Instructors paste YouTube links into lessons and the video doesn't show up.
Root cause: the frontend URL parser (`frontend/src/lib/video.ts`) only
recognizes `watch?v=`, `youtu.be/`, and `embed/` links — `shorts/`, `live/`,
and URLs where `v=` isn't the first query param fall through, and the parser
then **silently stores the full URL as the video_id**. The backend accepts
anything (no validation, no normalization), so the lesson saves fine and the
player renders an empty embed with no error. This phase makes video-ID
extraction robust for all common YouTube URL forms, makes the backend the
validating source of truth, repairs existing bad rows via data migration,
removes the half-broken Vimeo option (never rendered by the player; blocked
by production CSP), gives instructors an inline preview + visible error in
the editors, and deletes the duplicated/dead code found along the way.

## Out of scope

- Vimeo playback support (option is being removed, not implemented)
- Any change to video progress tracking (`LessonProgress.video_position`,
  10s polling) or the YouTube IFrame API player itself
- The Sentry N+1 on `/api/courses/{code}/quizzes/` (STEMQUEST-DJANGO-5) —
  separate backlog item
- Phase-51 housekeeping items (ADMIN_URL flip, legal banners, etc.)
- CSP changes — production `_headers` already correctly allows YouTube

## Supported YouTube URL forms (the contract)

Extraction must return the 11-char video ID from ALL of:

- `https://www.youtube.com/watch?v=VIDEOID` (also `m.` and no-`www` hosts)
- `https://www.youtube.com/watch?feature=share&v=VIDEOID` (v= anywhere in query)
- `https://youtu.be/VIDEOID` and `https://youtu.be/VIDEOID?si=TRACKING&t=42`
- `https://www.youtube.com/shorts/VIDEOID` (with or without query params)
- `https://www.youtube.com/live/VIDEOID` (with or without query params)
- `https://www.youtube.com/embed/VIDEOID`
- A bare 11-char ID (`[A-Za-z0-9_-]{11}`) passes through unchanged

Anything else (non-YouTube URL, malformed link, empty when type=youtube) is
**rejected with a clear error**, never stored.

## Backend tasks

- [x] Add `backend/courses/video.py` with `extract_youtube_video_id(value) -> str | None`
      implementing the contract above (single source of truth server-side).
- [x] Validation in serializers: `LessonSerializer`, `LessonCreateSerializer`,
      `LessonSectionSerializer`, `LessonSectionCreateSerializer` (bulk create
      goes through the child serializer — verify it does). When
      `video_type == 'youtube'`: normalize `video_id` through the extractor;
      reject with a field error ("Could not extract a YouTube video ID from
      this value") if extraction fails. When `video_type == 'none'`: force
      `video_id` to empty.
- [x] Remove `vimeo` from `VIDEO_TYPE_CHOICES` on both `Lesson`
      (`models.py:84-88`) and `LessonSection` (`models.py:654-659`) —
      schema migration.
- [x] Data migration (same migration file or follow-up, with reverse noop):
      1. Any row with `video_type='vimeo'` → `video_type='none'`, `video_id=''`.
      2. Any row with `video_type='youtube'` whose `video_id` is not a bare
         11-char ID → re-parse through the extractor; on success store the ID,
         on failure set `video_type='none'`, `video_id=''`.
      Print/log a summary of rows changed and rows nulled.
- [x] Run the `db-migration-checker` agent on the new migrations before merge.
- [x] Tests (`backend/courses/tests.py`):
      - [x] Parametrized extractor test covering every URL form in the
            contract + rejection cases (google.com URL, `watch?v=short`,
            empty string, 12-char garbage).
      - [x] Lesson update via API with a `shorts/` URL stores the bare ID.
      - [x] Section create (single + bulk) with a `youtu.be/...?si=` URL
            stores the bare ID.
      - [x] Unparseable value with `video_type='youtube'` returns 400 with
            the field error.
      - [x] `video_type='vimeo'` now rejected (choices).
      - [x] Data migration test: URL-shaped `video_id` gets normalized;
            garbage gets nulled to `none`.

## Frontend tasks

- [x] `frontend/src/lib/video.ts`: rewrite `extractYouTubeVideoId` to match
      the contract, **returning `null` on failure instead of echoing the
      input back** (current line 27 behavior is the silent-corruption bug).
      Delete `extractVimeoVideoId`.
- [x] `frontend/src/components/lesson/SectionEditor.tsx`: delete the private
      duplicate extractor (lines ~40-54); import from `@/lib/video`. Handle
      the new `null` return: block save + show inline error.
- [x] `frontend/src/pages/instructor/LessonEditorPage.tsx`: remove the Vimeo
      option from the video-type select; handle `null` from the extractor:
      block save + show inline error.
- [x] Inline preview in BOTH editors: once a valid ID parses, show the
      thumbnail `https://i.ytimg.com/vi/<ID>/hqdefault.jpg` (already allowed
      by CSP `img-src`) with the parsed ID displayed; when input is non-empty
      and unparseable, show a visible error state instead. Follow the UI
      readability preferences: real button/error styling, not tiny text.
- [x] `frontend/src/types/index.ts`: narrow `video_type` on `Lesson` and
      `LessonSection` to `'none' | 'youtube'`.
- [x] Delete dead component `frontend/src/components/lesson/SectionContent.tsx`
      after confirming (grep) nothing imports it.
- [x] Sweep remaining `vimeo` references (`VideoPlayer.tsx` prop types, etc.)
      — `grep -ri vimeo frontend/src` must come back empty when done.

## Verification

- [x] `/verify-stack` passes: backend pytest (all existing + new video tests),
      `npx tsc --noEmit` 0 errors, `npm run lint` 0 warnings.
- [x] New extractor tests demonstrably cover: watch, watch-with-extra-params,
      youtu.be, youtu.be?si, shorts, live, embed, bare ID, and 4 rejection
      cases — on both backend and (if a frontend test harness exists) frontend.
- [x] Manual flow (local): as instructor, paste a `youtube.com/shorts/...`
      URL into the **section editor** → preview thumbnail appears → save →
      open the lesson as a student → video plays. Repeat with a
      `youtu.be/...?si=...` link in the **lesson editor**. Paste
      `https://google.com/foo` → visible inline error, save blocked.
- [x] Manual flow (negative): API request with `video_type='youtube'`,
      `video_id='https://example.com'` returns 400 (curl or pytest).
- [ ] Deploy order (gotcha from phase 51): run migrations on Neon BEFORE
      merging the backend schema change to main.
- [ ] Post-deploy: existing prod lessons with previously-broken video IDs
      render correctly (check at least one repaired row via the app).

## Notes for implementer

- Backend changes need `docker compose restart backend` to take effect.
- `Lesson.video_id` is max_length=50, `LessonSection.video_id` is 100 —
  after normalization only 11-char IDs are stored, so leave lengths alone.
- The player chain (`VideoPlayer.tsx` → `YouTubePlayer.tsx` → YT IFrame API)
  is working correctly; do not touch it beyond the prop-type narrowing.

## Finish-phase review (2026-07-23)

Adversarial review found one real bug, now fixed; three low-risk items deferred.

- **FIXED — long share URLs rejected before extraction.** DRF runs the
  model-derived `max_length` validator on `video_id` (50 on Lesson, 100 on
  Section) inside `to_internal_value()`, i.e. *before* the mixin's `validate()`
  extractor. A valid 63-char share URL (`watch?v=ID&si=...`, YouTube's own
  Share default) 400'd on length instead of normalizing — defeating the
  "backend is the validating source of truth" goal for direct API clients
  (the UI pre-extracts, so it was unreachable through the app). Fix:
  `VideoFieldsValidationMixin.get_fields()` lifts the input cap to 255 so
  extraction runs and stores the 11-char ID; oversized junk is still rejected.
  Regression tests: `test_lesson_update_with_long_share_url_stores_bare_id`,
  `test_lesson_update_oversized_video_id_rejected`.
- **DEFERRED (low risk, not API-reachable through normal flows):**
  1. An 11-digit integer/JSON number is accepted as a bare ID (coincidental
     shape match) — stores a broken embed but no security impact.
  2. Repair migration `0018` only touches exact `video_type in ('vimeo',
     'youtube')`; out-of-enum drift (e.g. `'YouTube'`) written out-of-band is
     left untouched. Not creatable via the API (strict `ChoiceField`).
  3. `javascript://youtube.com/watch?v=ID` parses to the ID; never persisted
     (only the bare 11-char ID is stored), so not exploitable. A defensive
     scheme allowlist in `video.py`/`video.ts` is a possible follow-up.
