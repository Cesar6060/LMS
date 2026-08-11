from django.core.validators import MaxLengthValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Count, Prefetch
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from .models import (
    Course, Unit, Lesson, Enrollment, LessonProgress, Announcement, CourseGradingConfig,
    LessonQuestion, LessonQuestionChoice, LessonQuestionAnswer, LessonQuizAttempt,
    LessonAttachment, LessonSection, InstructorReminder, CourseInvite
)
from accounts.serializers import UserSerializer
from core.uploads import download_url
from .permissions import (
    require_course_instructor, is_course_instructor, require_pending_invite,
    INVITE_REQUIRED_DETAIL,
)
from .video import extract_youtube_video_id


# A full YouTube share URL is accepted as input; validate() extracts the
# 11-char ID that is actually stored, so the model columns (50/100) never see
# the raw URL. Bounded so oversized junk is still rejected before extraction.
VIDEO_ID_INPUT_MAX_LENGTH = 255


class VideoFieldsValidationMixin:
    """Normalize/validate video_id against video_type on lessons and sections.

    On partial updates, fields absent from the payload fall back to the
    instance so a title-only PATCH can't bypass validation.
    """

    def get_fields(self):
        fields = super().get_fields()
        video_id = fields.get('video_id')
        if video_id is not None:
            # The model-derived field caps length at 50/100, and DRF runs that
            # MaxLengthValidator in to_internal_value() — before validate().
            # Without this, a valid long share URL (watch?v=ID&si=...) is
            # rejected for length before the extractor ever normalizes it.
            video_id.max_length = VIDEO_ID_INPUT_MAX_LENGTH
            video_id.validators = [
                v for v in video_id.validators
                if not isinstance(v, MaxLengthValidator)
            ]
            video_id.validators.append(
                MaxLengthValidator(VIDEO_ID_INPUT_MAX_LENGTH))
        return fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        video_type = attrs.get(
            'video_type', getattr(self.instance, 'video_type', 'none'))
        video_id = attrs.get(
            'video_id', getattr(self.instance, 'video_id', ''))

        if video_type == 'youtube':
            extracted = extract_youtube_video_id(video_id)
            if extracted is None:
                raise serializers.ValidationError({
                    'video_id': 'Could not extract a YouTube video ID from this value.'
                })
            attrs['video_id'] = extracted
        else:
            attrs['video_id'] = ''
        return attrs


class LessonAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for lesson attachments."""
    url = serializers.SerializerMethodField()

    class Meta:
        model = LessonAttachment
        fields = ['id', 'filename', 'file_type', 'file_size', 'url', 'uploaded_at']

    def get_url(self, obj):
        if not obj.file:
            return None
        # Phase 73: served with an attachment disposition so an uploaded file
        # is downloaded rather than rendered. On R2 this rides on the presigned
        # URL itself, so it cannot be dropped by re-requesting the object.
        url = download_url(obj.file, obj.filename)
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url


class LessonSectionSerializer(VideoFieldsValidationMixin, serializers.ModelSerializer):
    """Serializer for lesson sections."""
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = LessonSection
        fields = [
            'id', 'title', 'content', 'video_type', 'video_id', 'layout',
            'image_url', 'image_alt', 'order', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'image_url', 'created_at', 'updated_at']

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url


class LessonSectionCreateSerializer(VideoFieldsValidationMixin, serializers.ModelSerializer):
    """Serializer for creating/updating lesson sections (lesson set in view).

    ``image`` is deliberately absent: it is set only by the slide-import
    endpoint. The editor sends full-object PUTs through this serializer, so a
    writable image field would be wiped on every save. ``image_alt`` IS
    editable here.
    """

    class Meta:
        model = LessonSection
        fields = ['id', 'title', 'content', 'video_type', 'video_id', 'layout', 'image_alt', 'order']
        read_only_fields = ['id']


class LessonSectionBulkCreateSerializer(serializers.Serializer):
    """Wrapper for atomically creating many sections at once (paste-to-split).

    Incoming per-child ``order`` is ignored — the view assigns sequential order
    appended after any existing sections. Bounded to 50 sections per request.
    """
    sections = LessonSectionCreateSerializer(many=True, min_length=1, max_length=50)


def _build_lesson_stats(lesson_ids):
    """Per-lesson counts for a batch of lessons, in three queries total.

    Returns ``{lesson_id: {section_count, attachment_count, question_count,
    has_video}}`` with an entry for every id asked for — lessons with no
    sections/attachments/questions must still report 0 rather than go missing,
    which is the classic way a bulk rewrite changes behaviour.

    ``has_video`` rides along on the section pass instead of costing a query of
    its own. It is the Python equivalent of the old
    ``filter(video_type='youtube').exclude(video_id='')``: ``video_id`` is a
    non-null CharField, so empty string is the only falsy value it can hold.
    """
    stats = {
        lesson_id: {
            'section_count': 0,
            'attachment_count': 0,
            'question_count': 0,
            'has_video': False,
        }
        for lesson_id in lesson_ids
    }
    if not lesson_ids:
        return stats

    for lesson_id, video_type, video_id in LessonSection.objects.filter(
        lesson_id__in=lesson_ids
    ).values_list('lesson_id', 'video_type', 'video_id'):
        row = stats[lesson_id]
        row['section_count'] += 1
        if video_type == 'youtube' and video_id:
            row['has_video'] = True

    for model, key in (
        (LessonAttachment, 'attachment_count'),
        (LessonQuestion, 'question_count'),
    ):
        counts = (
            model.objects.filter(lesson_id__in=lesson_ids)
            .values('lesson_id')
            .annotate(n=Count('id'))
            .values_list('lesson_id', 'n')
        )
        for lesson_id, n in counts:
            stats[lesson_id][key] = n

    return stats


class LessonStatsMixin:
    """Resolves the per-lesson count fields in bulk instead of per lesson.

    Same mechanic as ``_completed_lesson_ids`` below: DRF's ``context`` is a
    property that walks ``self.parent`` up to the root serializer and returns
    one shared dict, so a nested serializer writing to it is visible to every
    sibling. Results accumulate — a second unit's lessons add to the map rather
    than replacing it — and the dict lives for exactly one response.

    Priming happens in ``LessonStatsListSerializer`` because only the
    ``many=True`` wrapper can see the whole list up front. Rendering a single
    lesson still works: the first field access primes just that lesson, which
    costs three queries instead of the four it replaces.
    """

    #: Relations the stats are derived from, by prefetch-cache key.
    _STAT_RELATIONS = ('sections', 'attachments', 'questions')

    def _lesson_stats(self, lesson_ids):
        stats = self.context.setdefault('lesson_stats', {})
        missing = [
            lesson_id for lesson_id in lesson_ids if lesson_id not in stats
        ]
        if missing:
            stats.update(_build_lesson_stats(missing))
        return stats

    def _stats_for(self, obj):
        """Stats for one lesson, cheapest source first.

        If the view already prefetched all three relations — which the views
        serializing full sections/attachments do — read them straight out of the
        prefetch cache for zero further queries. Otherwise fall back to the
        bulk map, which is what course detail uses: prefetching sections there
        would drag every section's markdown `content` into memory just to count
        rows.
        """
        prefetched = getattr(obj, '_prefetched_objects_cache', None) or {}
        if all(relation in prefetched for relation in self._STAT_RELATIONS):
            sections = list(obj.sections.all())
            return {
                'section_count': len(sections),
                'has_video': any(
                    section.video_type == 'youtube' and section.video_id
                    for section in sections
                ),
                'attachment_count': len(obj.attachments.all()),
                'question_count': len(obj.questions.all()),
            }
        return self._lesson_stats([obj.pk])[obj.pk]

    def get_attachment_count(self, obj):
        return self._stats_for(obj)['attachment_count']

    def get_section_count(self, obj):
        return self._stats_for(obj)['section_count']

    def get_has_video(self, obj):
        # Phase 53: video lives in sections, not on the lesson. True if any
        # section has a playable YouTube video.
        return self._stats_for(obj)['has_video']

    def get_question_count(self, obj):
        return self._stats_for(obj)['question_count']


class LessonStatsListSerializer(serializers.ListSerializer):
    """Primes the shared stats map once for the whole list.

    Wired via ``Meta.list_serializer_class``, so every ``many=True`` use gets
    this for free no matter which of the six views instantiated it.
    """

    def to_representation(self, data):
        iterable = data.all() if isinstance(data, models.Manager) else data
        # Materialize once: the queryset would otherwise be evaluated a second
        # time by super(), undoing the saving.
        lessons = list(iterable)
        self.child._lesson_stats([lesson.pk for lesson in lessons])
        return super().to_representation(lessons)


class LessonSerializer(LessonStatsMixin, serializers.ModelSerializer):
    """Serializer for Lesson model."""
    question_count = serializers.SerializerMethodField()
    attachments = LessonAttachmentSerializer(many=True, read_only=True)
    sections = LessonSectionSerializer(many=True, read_only=True)
    section_count = serializers.SerializerMethodField()
    has_video = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        list_serializer_class = LessonStatsListSerializer
        # Phase 54: `required_quiz` (System A) retired — not writable/readable.
        # `requires_quiz` is the single per-lesson gate over the lesson's own
        # comprehension questions.
        #
        # Phase 55 (C5): `content`/`video_type`/`video_id` are read-only. They
        # are dormant on Lesson — content and video live on LessonSection since
        # phase 53, and migration 0019 blanked every lesson-level value — but
        # they stayed writable, so a client could still put data somewhere
        # nothing renders. Kept readable while old clients still deserialize
        # them; the column drop is a later change.
        # VideoFieldsValidationMixin is deliberately gone with them: it exists
        # to normalize a writable video_id, and LessonSection still uses it.
        fields = [
            'id', 'unit', 'title', 'content', 'order',
            'video_type', 'video_id', 'requires_quiz',
            'question_count', 'attachments',
            'sections', 'section_count', 'has_video',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'content', 'video_type', 'video_id',
        ]

    def validate_unit(self, value):
        """Refuse a PATCH that would move the lesson into another course.

        `unit` is writable so an instructor can move a lesson between units,
        but `IsEnrolledOrInstructor.has_object_permission` resolves the course
        from `obj.unit.course` — the *source* course only. Without this check a
        plain `PATCH {"unit": <unit in another course>}` moves the lesson out of
        its course with nothing validating the destination.

        Mirrors the guard `LessonViewSet.reorder` already applies to its own
        optional `unit` argument: same-course only, and the instructor is
        re-checked against the target's course.

        That second check cannot fire through the API today — by the time it
        runs the target is known to be in the same course, which `get_object()`
        already checked the caller owns. It is kept as belt-and-braces so it
        becomes load-bearing if the same-course restriction is ever relaxed,
        matching what `reorder` does.

        It fails *closed* when the serializer has no request in its context.
        Every current call site is a DRF view, which always supplies one, but
        skipping the ownership check for a context-less caller (a management
        command, a shell session, a future bulk import) would make this guard
        quietly optional — the opposite of what it is for.
        """
        if self.instance is None:
            return value

        if value.course_id != self.instance.unit.course_id:
            raise serializers.ValidationError(
                'Target unit must belong to the same course.'
            )

        request = self.context.get('request')
        if request is None:
            raise serializers.ValidationError(
                'Cannot change a lesson\'s unit without a request context to '
                'check course ownership against.'
            )
        require_course_instructor(request.user, value.course)

        return value


class LessonCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating lessons (unit set in view).

    Phase 55 (C5): `content`/`video_type`/`video_id` are read-only here too — a
    new lesson starts empty and gains its content as LessonSections. They stay
    in `fields` so the create response keeps its shape for existing clients.
    """

    class Meta:
        model = Lesson
        fields = ['id', 'title', 'content', 'order', 'video_type', 'video_id', 'requires_quiz']
        read_only_fields = ['id', 'content', 'video_type', 'video_id']


class LessonListSerializer(LessonStatsMixin, serializers.ModelSerializer):
    """Serializer for lesson lists (includes content and video_id for editing)."""
    question_count = serializers.SerializerMethodField()
    attachment_count = serializers.SerializerMethodField()
    section_count = serializers.SerializerMethodField()
    has_video = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        list_serializer_class = LessonStatsListSerializer
        fields = [
            'id', 'title', 'order', 'video_type', 'video_id', 'content',
            'requires_quiz', 'question_count',
            'attachment_count', 'section_count', 'has_video', 'is_completed'
        ]

    def _completed_lesson_ids(self):
        """The requesting user's completed lesson ids — resolved once per response.

        Cached in the serializer context, which nested serializers share with
        the root, so a course-detail payload with 40 lessons costs one query
        rather than 40. Phase 55 (C7).
        """
        if 'completed_lesson_ids' not in self.context:
            request = self.context.get('request')
            if request is not None and request.user.is_authenticated:
                completed = frozenset(
                    LessonProgress.objects.filter(
                        user=request.user, completed=True
                    ).values_list('lesson_id', flat=True)
                )
            else:
                completed = frozenset()
            self.context['completed_lesson_ids'] = completed
        return self.context['completed_lesson_ids']

    def get_is_completed(self, obj):
        """Whether the requesting user has completed this lesson.

        Added in phase 55 (C7): the course-detail page had no per-lesson
        completion, so it *estimated* which lesson was next by spreading the
        overall progress percentage across the lesson list. That pointed at the
        wrong lesson for anyone who completed lessons out of order.
        """
        return obj.id in self._completed_lesson_ids()


class UnitSerializer(serializers.ModelSerializer):
    """Serializer for Unit model with nested lessons.

    Phase 66: a locked unit stays *visible* to students — title, order and
    ``lesson_count`` are still sent so the UI can render "N lessons · Locked" —
    but ``lessons`` is emptied. Withholding the lesson list here is what makes
    the lock hold for any caller of this serializer; the per-endpoint
    ``require_unit_unlocked`` gates cover direct access to a known lesson id.
    """
    lessons = LessonListSerializer(many=True, read_only=True)
    lesson_count = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = [
            'id', 'course', 'title', 'order', 'is_locked',
            'lessons', 'lesson_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'is_locked', 'created_at', 'updated_at']

    def get_lesson_count(self, obj):
        # Counts every lesson, locked or not — this is the number the student
        # is shown alongside the lock, so it must not depend on visibility.
        lessons = getattr(obj, 'lessons', None)
        if lessons is None:
            return 0
        return len(lessons.all()) if hasattr(lessons, 'all') else len(lessons)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not instance.is_locked:
            return data

        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and is_course_instructor(user, instance.course):
            return data

        data['lessons'] = []
        return data


class UnitCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating units.

    ``is_locked`` is writable here (phase 66) — ``UnitViewSet`` uses this
    serializer for update/partial_update, and that ViewSet already restricts
    writes to the course instructor.
    """

    class Meta:
        model = Unit
        fields = ['id', 'title', 'order', 'is_locked']
        read_only_fields = ['id']


#: Prefetch alias holding only active enrollments. Views that serialize
#: student_count/is_enrolled attach this; the serializers below read it instead
#: of issuing a filter() per course. Named via to_attr so it cannot collide with
#: a plain prefetch_related('enrollments') elsewhere.
ACTIVE_ENROLLMENTS_ATTR = 'active_enrollments'


def prefetch_active_enrollments():
    return Prefetch(
        'enrollments',
        queryset=Enrollment.objects.filter(is_active=True),
        to_attr=ACTIVE_ENROLLMENTS_ATTR,
    )


class ActiveEnrollmentCountMixin:
    """Serves student_count/is_enrolled from a filtered prefetch when present.

    The per-object versions these replace both called ``.filter()`` on the
    related manager, which builds a fresh queryset and hits the database every
    time — a plain ``prefetch_related('enrollments')`` never helped them.
    """

    def _active_enrollments(self, obj):
        return getattr(obj, ACTIVE_ENROLLMENTS_ATTR, None)

    def get_student_count(self, obj):
        active = self._active_enrollments(obj)
        if active is None:
            return obj.enrollments.filter(is_active=True).count()
        return len(active)

    def get_is_enrolled(self, obj):
        request = self.context.get('request')
        if not (request and request.user.is_authenticated):
            return False
        active = self._active_enrollments(obj)
        if active is None:
            return obj.enrollments.filter(
                user=request.user, is_active=True).exists()
        return any(
            enrollment.user_id == request.user.id for enrollment in active
        )


class CourseSerializer(ActiveEnrollmentCountMixin, serializers.ModelSerializer):
    """Full course serializer with nested units."""
    instructor = UserSerializer(read_only=True)
    units = UnitSerializer(many=True, read_only=True)
    student_count = serializers.SerializerMethodField()
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'code', 'title', 'description', 'instructor',
            'enrollment_code', 'is_active', 'units', 'student_count',
            'is_enrolled', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'enrollment_code', 'created_at', 'updated_at']

    def to_representation(self, instance):
        """Hide enrollment_code, and lesson content, from outsiders."""
        data = super().to_representation(instance)
        request = self.context.get('request')

        # Only show enrollment_code to the course instructor
        if request and request.user != instance.instructor:
            data.pop('enrollment_code', None)

        # Phase 73: CourseViewSet.get_queryset hands every is_instructor user
        # the unfiltered Course queryset so they can browse the catalogue, and
        # this serializer nests units -> lessons -> content. That combination
        # let any instructor account read the full body of every course on the
        # platform by walking enumerable codes like ROB101. The catalogue entry
        # stays visible; the material does not. Fetching the same lesson at
        # /api/lessons/<id>/ has always 403'd for these callers — this closes
        # the second route to it.
        #
        # Reuses the already-computed is_enrolled rather than calling
        # can_access_course: that helper runs its own Enrollment query and would
        # bypass the prefetch this serializer is built around, which the phase
        # 63 query-count guard catches.
        if request and not (
            request.user == instance.instructor or data.get('is_enrolled')
        ):
            data['units'] = []

        return data


class CourseListSerializer(ActiveEnrollmentCountMixin, serializers.ModelSerializer):
    """Lightweight serializer for course lists."""
    instructor_name = serializers.SerializerMethodField()
    student_count = serializers.SerializerMethodField()
    unit_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'code', 'title', 'description', 'instructor_name',
            'is_active', 'student_count', 'unit_count', 'created_at'
        ]

    def get_instructor_name(self, obj):
        return obj.instructor.get_full_name() or obj.instructor.email

    def get_unit_count(self, obj):
        # Free when the view prefetched units: .count() on a prefetched manager
        # would still hit the database, len() of .all() reads the cache.
        return len(obj.units.all())


class CourseCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating courses."""

    class Meta:
        model = Course
        fields = ['id', 'code', 'title', 'description', 'is_active']
        read_only_fields = ['id']

    def create(self, validated_data):
        validated_data['instructor'] = self.context['request'].user
        return super().create(validated_data)


class InstructorCourseSerializer(
        ActiveEnrollmentCountMixin, serializers.ModelSerializer):
    """Course serializer for instructors (includes enrollment_code)."""
    units = UnitSerializer(many=True, read_only=True)
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'code', 'title', 'description', 'enrollment_code',
            'is_active', 'units', 'student_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'enrollment_code', 'created_at', 'updated_at']


class EnrollmentCourseSerializer(serializers.ModelSerializer):
    """Course serializer for enrollment (includes instructor details)."""
    instructor = UserSerializer(read_only=True)

    class Meta:
        model = Course
        fields = ['id', 'code', 'title', 'description', 'instructor', 'is_active']


class EnrollmentSerializer(serializers.ModelSerializer):
    """Serializer for enrollment records."""
    course = EnrollmentCourseSerializer(read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = Enrollment
        fields = ['id', 'user', 'course', 'enrolled_at']
        read_only_fields = ['id', 'enrolled_at']


class EnrollmentCreateSerializer(serializers.Serializer):
    """Serializer for enrolling in a course with a code AND a pending invite.

    This path resolves the course by enrollment code ALONE — there is no
    course in the URL — so the invite check is the only thing scoping it to a
    course the caller was actually asked to join. Its authorization must stay
    identical to `CourseViewSet.enroll`'s; anything true of one and not the
    other is the bug phase 68 exists to fix.
    """
    enrollment_code = serializers.CharField(max_length=8)

    def validate_enrollment_code(self, value):
        try:
            course = Course.objects.get(enrollment_code=value.upper(), is_active=True)
        except Course.DoesNotExist:
            raise serializers.ValidationError("Invalid enrollment code.")

        user = self.context['request'].user

        # Check if already actively enrolled
        existing = Enrollment.objects.filter(user=user, course=course).first()
        if existing and existing.is_active:
            raise serializers.ValidationError("You are already enrolled in this course.")

        # Check if user is the instructor
        if course.instructor == user:
            raise serializers.ValidationError("Instructors cannot enroll in their own courses.")

        # PermissionDenied, not ValidationError: a missing invitation is an
        # authorization failure and must be a 403 {'detail': ...} per
        # .claude/rules/backend.md, not a 400 field error.
        require_pending_invite(user, course)

        # A soft-deleted enrollment is not revived by presenting a code. Only
        # accept_invite's _activate_enrollment brings one back, so an
        # instructor's removal sticks until they re-invite. Same body as the
        # no-invite refusal — a student is never told they were removed.
        if existing:
            raise PermissionDenied(INVITE_REQUIRED_DETAIL)

        self.course = course
        return value.upper()

    def create(self, validated_data):
        from .views import consume_invite_for

        user = self.context['request'].user
        try:
            with transaction.atomic():
                enrollment = Enrollment.objects.create(
                    user=user, course=self.course)
                # Same contract as CourseViewSet.enroll: the invite check in
                # validate() is a read, this write is what claims the invite,
                # and an instructor's revoke landing in the gap must win.
                if not consume_invite_for(user, self.course):
                    raise PermissionDenied(INVITE_REQUIRED_DETAIL)
        except IntegrityError:
            # A concurrent request took the unique ('user','course') row
            # between validate() and here. Already-enrolled, not a 500 —
            # but confirmed by re-reading rather than inferred from the
            # exception class, so a future constraint reachable from this
            # block cannot be silently relabelled as a business-rule 400.
            if not Enrollment.objects.filter(
                    user=user, course=self.course).exists():
                raise
            raise serializers.ValidationError(
                {'enrollment_code': ["You are already enrolled in this course."]})
        return enrollment


class LessonProgressSerializer(serializers.ModelSerializer):
    """Serializer for lesson progress."""
    lesson_questions_status = serializers.SerializerMethodField()

    class Meta:
        model = LessonProgress
        fields = [
            'id', 'lesson', 'completed', 'completed_at', 'video_position',
            'current_section', 'lesson_questions_status', 'updated_at'
        ]
        read_only_fields = ['id', 'completed_at', 'updated_at']

    def get_lesson_questions_status(self, obj):
        """Status of the lesson's own comprehension questions (System B).

        Phase 54: the gate is `requires_quiz`. `can_complete_lesson` must agree
        with the real completion gate in `LessonProgressUpdateSerializer.
        validate_completed` — i.e. a passing `LessonQuizAttempt` when gated —
        so the UI never shows "ready" while the save would 400.
        """
        lesson = obj.lesson
        total_questions = lesson.questions.count()

        if total_questions == 0:
            return None  # No questions for this lesson

        answers = LessonQuestionAnswer.objects.filter(
            user=obj.user,
            question__lesson=lesson
        )
        answered_count = answers.count()
        correct_count = answers.filter(is_correct=True).count()
        all_correct = correct_count == total_questions

        has_passed = LessonQuizAttempt.objects.filter(
            user=obj.user, lesson=lesson,
            status=LessonQuizAttempt.STATUS_COMPLETED, passed=True
        ).exists()

        gated = lesson.requires_quiz
        can_complete = has_passed if gated else True

        return {
            'total_questions': total_questions,
            'answered_questions': answered_count,
            'correct_answers': correct_count,
            'all_correct': all_correct,
            'requires_quiz': gated,
            'has_passed': has_passed,
            'can_complete_lesson': can_complete,
        }


class LessonProgressUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating lesson progress."""

    class Meta:
        model = LessonProgress
        fields = ['completed', 'video_position', 'current_section']

    def validate_completed(self, value):
        """Phase 54: a lesson gates completion only when `requires_quiz` is set
        AND it has comprehension questions; the gate is a passing
        `LessonQuizAttempt`. The retired cross-course `required_quiz` FK is no
        longer enforced."""
        if value:  # Only check when marking as complete
            lesson = self.instance.lesson
            user = self.instance.user

            if lesson.requires_quiz and lesson.questions.exists():
                has_passed = LessonQuizAttempt.objects.filter(
                    user=user,
                    lesson=lesson,
                    status=LessonQuizAttempt.STATUS_COMPLETED,
                    passed=True
                ).exists()

                if not has_passed:
                    raise serializers.ValidationError(
                        "You must pass this lesson's quiz before completing it."
                    )
        return value

    def update(self, instance, validated_data):
        from django.utils import timezone

        # Flag the not-completed -> completed transition so the view can award
        # gamification XP. This is the single place a lesson "becomes done".
        just_completed = bool(validated_data.get('completed')) and not instance.completed

        # Set completed_at when marking as complete
        if just_completed:
            validated_data['completed_at'] = timezone.now()

        updated = super().update(instance, validated_data)
        updated._just_completed = just_completed
        return updated


class AnnouncementSerializer(serializers.ModelSerializer):
    """Serializer for Announcement model."""
    author = UserSerializer(read_only=True)
    course_code = serializers.CharField(source='course.code', read_only=True)

    class Meta:
        model = Announcement
        fields = [
            'id', 'course', 'course_code', 'author', 'title', 'content',
            'is_pinned', 'send_email', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author', 'created_at', 'updated_at']


class AnnouncementListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for announcement lists."""
    author_name = serializers.SerializerMethodField()
    course_code = serializers.CharField(source='course.code', read_only=True)

    class Meta:
        model = Announcement
        fields = [
            'id', 'course_code', 'author_name', 'title', 'is_pinned', 'created_at'
        ]

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.email


class AnnouncementCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating announcements."""

    class Meta:
        model = Announcement
        fields = ['id', 'title', 'content', 'is_pinned', 'send_email']
        read_only_fields = ['id']


class StudentRosterSerializer(serializers.ModelSerializer):
    """Serializer for student roster (instructor view)."""
    student_id = serializers.IntegerField(source='user.id')
    email = serializers.EmailField(source='user.email')
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    progress_percentage = serializers.SerializerMethodField()
    is_inactive = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = [
            'id', 'student_id', 'email', 'first_name', 'last_name',
            'enrolled_at', 'last_activity_at', 'is_active',
            'progress_percentage', 'is_inactive'
        ]

    def _course_lesson_total(self, course_id):
        """Lessons in the course — one query per response, not per student.

        Every row on a roster page belongs to the same course, so the old
        per-student ``Lesson.objects.filter(unit__course=obj.course).count()``
        recomputed an identical number up to 100 times (the roster page size).
        Keyed by course id anyway, so a mixed-course list stays correct.
        """
        totals = self.context.setdefault('roster_lesson_totals', {})
        if course_id not in totals:
            # Locked units are excluded so a roster percentage matches the
            # progress the student is actually able to make (phase 66).
            totals[course_id] = Lesson.objects.filter(
                unit__course_id=course_id, unit__is_locked=False).count()
        return totals[course_id]

    def _completed_counts(self, course_id):
        """{user_id: completed lesson count} for the whole course, in one query.

        Scoped by course rather than by the ids on the current page so the
        first access serves every row without a list wrapper to prime it. The
        rows are two integers each, so fetching the whole course is cheaper
        than the per-student query it replaces even when the page is small.
        """
        by_course = self.context.setdefault('roster_completed', {})
        if course_id not in by_course:
            rows = (
                LessonProgress.objects.filter(
                    lesson__unit__course_id=course_id,
                    lesson__unit__is_locked=False, completed=True)
                .values('user_id')
                .annotate(n=Count('id'))
                .values_list('user_id', 'n')
            )
            by_course[course_id] = dict(rows)
        return by_course[course_id]

    def get_progress_percentage(self, obj):
        """Calculate course progress for this student."""
        total_lessons = self._course_lesson_total(obj.course_id)
        if total_lessons == 0:
            return 0

        completed = self._completed_counts(obj.course_id).get(obj.user_id, 0)

        return round((completed / total_lessons) * 100, 1)

    def get_is_inactive(self, obj):
        """Check if student hasn't been active in 7+ days."""
        from django.utils import timezone
        from datetime import timedelta

        if not obj.last_activity_at:
            # If never active, check enrolled date
            return (timezone.now() - obj.enrolled_at) > timedelta(days=7)

        return (timezone.now() - obj.last_activity_at) > timedelta(days=7)


class GradingConfigSerializer(serializers.ModelSerializer):
    """Serializer for CourseGradingConfig model."""

    class Meta:
        model = CourseGradingConfig
        fields = ['quizzes_weight', 'participation_weight']

    def validate(self, data):
        # Get existing values for fields not being updated
        instance = self.instance
        quizzes = data.get('quizzes_weight', instance.quizzes_weight if instance else 50)
        participation = data.get('participation_weight', instance.participation_weight if instance else 50)

        total = float(quizzes) + float(participation)
        if total != 100:
            raise serializers.ValidationError(f'Weights must sum to 100%. Current total: {total}%')
        return data


# ============================================
# Lesson Questions (Mini Comprehension Quizzes)
# ============================================

class LessonQuestionChoiceSerializer(serializers.ModelSerializer):
    """Serializer for lesson question choices."""

    class Meta:
        model = LessonQuestionChoice
        fields = ['id', 'text', 'is_correct', 'order']


class LessonQuestionChoiceStudentSerializer(serializers.ModelSerializer):
    """Serializer for students - hides is_correct field."""

    class Meta:
        model = LessonQuestionChoice
        fields = ['id', 'text', 'order']


class LessonQuestionSerializer(serializers.ModelSerializer):
    """Serializer for lesson questions (instructor view with answers)."""
    choices = LessonQuestionChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = LessonQuestion
        fields = ['id', 'lesson', 'text', 'order', 'choices', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class LessonQuestionStudentSerializer(serializers.ModelSerializer):
    """Serializer for students - hides correct answer info."""
    choices = LessonQuestionChoiceStudentSerializer(many=True, read_only=True)

    class Meta:
        model = LessonQuestion
        fields = ['id', 'text', 'order', 'choices']


class LessonQuestionCreateSerializer(serializers.Serializer):
    """Serializer for creating/updating a lesson question with choices."""
    text = serializers.CharField()
    order = serializers.IntegerField(default=0)
    choices = serializers.ListField(
        child=serializers.DictField(),
        min_length=2,
        max_length=6,
        help_text='List of choices with text, is_correct, and order'
    )

    def validate_choices(self, value):
        # Ensure exactly one choice is marked correct
        correct_count = sum(1 for choice in value if choice.get('is_correct', False))
        if correct_count == 0:
            raise serializers.ValidationError("Exactly one choice must be marked as correct.")
        if correct_count > 1:
            raise serializers.ValidationError("Only one choice can be marked as correct.")

        # Ensure each choice has text
        for i, choice in enumerate(value):
            if not choice.get('text', '').strip():
                raise serializers.ValidationError(f"Choice {i+1} must have text.")

        return value


class LessonQuestionAnswerSerializer(serializers.ModelSerializer):
    """Serializer for student answers to lesson questions."""
    question_text = serializers.CharField(source='question.text', read_only=True)
    selected_choice_text = serializers.CharField(source='selected_choice.text', read_only=True)

    class Meta:
        model = LessonQuestionAnswer
        fields = ['id', 'question', 'question_text', 'selected_choice', 'selected_choice_text', 'is_correct', 'answered_at']
        read_only_fields = ['id', 'is_correct', 'answered_at']


class LessonQuestionsStatusSerializer(serializers.Serializer):
    """Serializer for lesson questions completion status."""
    total_questions = serializers.IntegerField()
    answered_questions = serializers.IntegerField()
    correct_answers = serializers.IntegerField()
    all_correct = serializers.BooleanField()
    can_complete_lesson = serializers.BooleanField()



class InstructorReminderSerializer(serializers.ModelSerializer):
    """Serializer for instructor calendar reminders."""
    course_code = serializers.SerializerMethodField()
    course_title = serializers.SerializerMethodField()

    class Meta:
        model = InstructorReminder
        fields = [
            "id", "course", "course_code", "course_title", "title",
            "description", "date", "time", "end_time", "color", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_course_code(self, obj):
        return obj.course.code if obj.course else None

    def get_course_title(self, obj):
        return obj.course.title if obj.course else None


class InstructorReminderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating reminders (instructor set in view)."""

    class Meta:
        model = InstructorReminder
        fields = ["id", "course", "title", "description", "date", "time", "end_time", "color"]
        read_only_fields = ["id"]

    def validate_course(self, value):
        """Ensure instructor owns the course if specified."""
        if value:
            request = self.context.get("request")
            if request and value.instructor != request.user:
                raise serializers.ValidationError("You can only add reminders to your own courses.")
        return value

    def validate(self, data):
        """Validate that end_time is after time if both are provided."""
        time = data.get('time') or (self.instance.time if self.instance else None)
        end_time = data.get('end_time')

        if time and end_time and end_time <= time:
            raise serializers.ValidationError({
                'end_time': 'End time must be after start time.'
            })

        # If no start time, clear end time
        if not time and end_time:
            data['end_time'] = None

        return data



# ==================== Course Map (Phase 35) ====================
# Read-only serializers for the Duolingo-style course map. Node states are
# computed in the view (course_map); these only shape the payload.

class CourseMapLessonNodeSerializer(serializers.Serializer):
    """A lesson node on the course map."""
    node_type = serializers.CharField()
    id = serializers.IntegerField()
    title = serializers.CharField()
    order = serializers.IntegerField()
    state = serializers.ChoiceField(
        choices=['completed', 'current', 'unlocked', 'locked']
    )
    # Why a locked node is locked, so the UI can pick the right tooltip:
    # 'sequence' = finish the previous node, 'instructor' = the unit is locked
    # (phase 66). Null whenever state is not 'locked'.
    lock_reason = serializers.ChoiceField(
        choices=['sequence', 'instructor'], allow_null=True
    )


class CourseMapQuizNodeSerializer(CourseMapLessonNodeSerializer):
    """A quiz ("boss") node — additionally carries scores.

    Both are null inside an instructor-locked unit (phase 66): the passing bar
    and the student's best score describe content they cannot see.
    """
    passing_score = serializers.IntegerField(allow_null=True)
    best_score = serializers.FloatField(allow_null=True)


class CourseMapUnitSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    order = serializers.IntegerField()
    is_locked = serializers.BooleanField()
    nodes = serializers.SerializerMethodField()

    def get_nodes(self, obj):
        return [
            (CourseMapQuizNodeSerializer if node['node_type'] == 'quiz'
             else CourseMapLessonNodeSerializer)(node).data
            for node in obj['nodes']
        ]


class CourseMapSerializer(serializers.Serializer):
    course_code = serializers.CharField()
    course_title = serializers.CharField()
    total_nodes = serializers.IntegerField()
    completed_nodes = serializers.IntegerField()
    # Composite "<node_type>-<id>" key (lesson and quiz ids can collide).
    current_node_id = serializers.CharField(allow_null=True)
    units = CourseMapUnitSerializer(many=True)


class CourseInviteSerializer(serializers.ModelSerializer):
    status = serializers.ReadOnlyField()
    # Phase 67: delivery is the email's fate, status is the invite's. Note the
    # deliberate absence of `token` / `invite_url` — live tokens stay out of
    # this list payload (and therefore out of browser cache and logs); the
    # roster fetches one on demand from the link endpoint instead.
    delivery = serializers.ReadOnlyField()

    class Meta:
        model = CourseInvite
        fields = [
            'id', 'email', 'status', 'created_at', 'expires_at',
            'email_sent_at', 'email_error', 'delivery',
        ]
        read_only_fields = ['email_sent_at', 'email_error']
