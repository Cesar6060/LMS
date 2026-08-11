---
paths:
  - "backend/**/serializers.py"
---

# DRF Serializer Rules

## `to_representation` is an authorization surface

The view queryset is NOT the last gate: `CourseViewSet.get_queryset` hands every
`is_instructor` user the unfiltered `Course` queryset (`courses/views.py:82`).

- `CourseSerializer.to_representation` (`courses/serializers.py:522`) sets
  `data['units'] = []` unless the caller is `instance.instructor` or
  `data.get('is_enrolled')` — phase 73; this closed a hole where any instructor
  account read every course's lessons by walking codes like `ROB101`. It also
  `pop`s `enrollment_code` for non-instructors (`:528`).
- `UnitSerializer.to_representation` (`:433`) sets `data['lessons'] = []` when
  `instance.is_locked` and the caller is not the course instructor.
  `lesson_count` still counts every lesson (`:425`) — students see "N lessons ·
  Locked".
- Pattern to copy: `super().to_representation()` first, early-return the full `data`
  for privileged callers, then blank the nested key. Never rely on a nested child to
  police its own visibility; when you add a nested relation, strip it in the parent.

## Reuse already-computed fields; don't re-query

- In `to_representation`, read the rendered `data` (e.g. `data['is_enrolled']`),
  not a permission helper. `can_access_course()` calls `is_enrolled()`, a fresh
  `Enrollment.objects.filter(...).exists()` per object (`courses/permissions.py:15-23`)
  that bypasses the prefetch — the phase-63 query-count guards
  (`TestPhase63CourseDetailQueryCounts`, `courses/tests.py:3093`) catch it.
- `ActiveEnrollmentCountMixin` (`:476`) reads the `active_enrollments` prefetch
  alias; `.filter()` on a related manager hits the DB even when prefetched, and
  `len(obj.units.all())` beats `.count()` likewise (`:571`).
- Cross-object lookups cache in `self.context` — one dict shared root-to-child,
  alive for exactly one response (`:374`, `:200`).

## Per-list N+1: `list_serializer_class` + a view-attached `to_attr` prefetch

- Only the `many=True` wrapper sees the whole set: prime bulk maps there and wire
  it via `Meta.list_serializer_class`, so every view gets it free. Examples:
  `LessonStatsListSerializer` (`courses/serializers.py:248`, wired at `:274`,
  `:367`), `QuizListListSerializer` (`quizzes/serializers.py:132`, wired `:160`).
- The wrapper must `list(iterable)` and pass the list to `super()`, or the queryset
  is evaluated twice and the saving is undone (`:259`). A `many=False` render must
  still work — fall back to a per-object query.
- Filtered prefetches live beside the serializer that consumes them, attached by
  the view: `prefetch_active_enrollments()` uses `to_attr` so it cannot collide
  with `prefetch_related('enrollments')` (`courses/serializers.py:468`; attached
  `courses/views.py:79`, `:213`).

## Conventions

- Authorization failures in `validate_*` raise `PermissionDenied` (403
  `{'detail': ...}`), not `ValidationError` (`courses/serializers.py:650`).
- Retire a field via `read_only_fields`, not deletion: dormant
  `content`/`video_type`/`video_id` stay readable for old clients (`:294`). Omit it
  entirely when full-object PUTs would wipe it — `image` on
  `LessonSectionCreateSerializer` (`:112`).
