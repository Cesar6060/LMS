from django.db import models
from django.db.models import Count
from rest_framework import serializers
from .models import Quiz, Question, Choice, QuizAttempt, AttemptAnswer


class ChoiceSerializer(serializers.ModelSerializer):
    """Serializer for quiz choices."""
    class Meta:
        model = Choice
        fields = ['id', 'text', 'is_correct', 'order']


class ChoiceStudentSerializer(serializers.ModelSerializer):
    """Serializer for choices shown to students (hides is_correct)."""
    class Meta:
        model = Choice
        fields = ['id', 'text', 'order']


class QuestionSerializer(serializers.ModelSerializer):
    """Serializer for quiz questions with choices."""
    choices = ChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'order', 'choices']


class QuestionStudentSerializer(serializers.ModelSerializer):
    """Serializer for questions shown to students (hides correct answers)."""
    choices = ChoiceStudentSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'order', 'choices']


# Context keys used by ``QuizListListSerializer`` to hand bulk-loaded attempt
# aggregates to ``QuizListSerializer``. ``PRIMED`` holds the quiz ids the bulk
# query has already covered, so "no entry" can be told apart from "zero
# attempts" — without it a quiz with no attempts would fall back to a
# per-object query and the N+1 would survive.
_PRIMED_KEY = 'quiz_attempt_primed_ids'
_COUNTS_KEY = 'quiz_attempt_counts'
_BESTS_KEY = 'quiz_best_attempts'


def _prime_quiz_attempt_context(context, quizzes):
    """Bulk-load per-quiz attempt aggregates for ``quizzes`` into ``context``.

    One grouped query for the whole result set instead of three per quiz
    (phase 63, C1). The context dict is shared with the root serializer and
    accumulates across sibling/nested list serializers, so entries are merged
    in and never replaced (decision 7).
    """
    request = context.get('request')
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        # No request/user in context: leave the maps alone so every field
        # falls back to its per-object path and behaves exactly as before.
        return

    primed = context.setdefault(_PRIMED_KEY, set())
    counts = context.setdefault(_COUNTS_KEY, {})
    bests = context.setdefault(_BESTS_KEY, {})

    pending = {quiz.pk for quiz in quizzes if quiz.pk is not None} - primed
    if not pending:
        return

    if user.is_instructor:
        # Instructors see every student's completed attempts, and get no
        # best_score / attempts_remaining at all — one grouped count is enough.
        rows = (
            QuizAttempt.objects
            .filter(quiz_id__in=pending, status=QuizAttempt.STATUS_COMPLETED)
            .values('quiz_id')
            .annotate(total=Count('id'))
        )
        for row in rows:
            counts[row['quiz_id']] = row['total']
    else:
        # A single pass over the student's own completed attempts serves both
        # the count and the best score. Ordered by '-score' — the same ORDER BY
        # the per-quiz ``.order_by('-score').first()`` used — so the first row
        # seen for a quiz is that quiz's best attempt.
        rows = (
            QuizAttempt.objects
            .filter(
                quiz_id__in=pending,
                student=user,
                status=QuizAttempt.STATUS_COMPLETED,
            )
            .order_by('-score')
            .values_list('quiz_id', 'score', 'passed', 'completed_at')
        )
        for quiz_id, score, passed, completed_at in rows:
            counts[quiz_id] = counts.get(quiz_id, 0) + 1
            if quiz_id not in bests:
                bests[quiz_id] = {
                    'score': float(score),
                    'passed': passed,
                    'completed_at': completed_at,
                }

    primed.update(pending)


class QuizQuestionCountField(serializers.IntegerField):
    """The quiz's question count, read from a queryset annotation.

    ``Quiz.question_count`` is a read-only @property that runs .count(), so it
    costs a query per quiz. ``quizzes.views._quiz_list_queryset`` annotates the
    count as ``annotated_question_count`` instead — the property is a data
    descriptor and Django assigns annotations with setattr, so annotating under
    the name ``question_count`` would raise.

    The fallback matters: for a read-only field DRF turns a missing source
    attribute into ``SkipField``, which would silently *drop* ``question_count``
    from the response for any caller that bypassed the annotated queryset. The
    property keeps the payload identical (at the old one-query cost).
    """

    def get_attribute(self, instance):
        try:
            return super().get_attribute(instance)
        except serializers.SkipField:
            return instance.question_count


class QuizListListSerializer(serializers.ListSerializer):
    """``many=True`` wrapper for :class:`QuizListSerializer`.

    Only the list wrapper sees the whole result set, so this is where the bulk
    attempt lookup can happen. A ``many=False`` render simply skips it and each
    field falls back to its original per-object query.
    """

    def to_representation(self, data):
        iterable = data.all() if isinstance(data, models.Manager) else data
        items = list(iterable)
        _prime_quiz_attempt_context(self.context, items)
        return super().to_representation(items)


class QuizListSerializer(serializers.ModelSerializer):
    """Serializer for listing quizzes."""
    question_count = QuizQuestionCountField(
        read_only=True, source='annotated_question_count'
    )
    best_score = serializers.SerializerMethodField()
    attempt_count = serializers.SerializerMethodField()
    attempts_remaining = serializers.SerializerMethodField()
    unit_title = serializers.CharField(source='unit.title', read_only=True)
    course_code = serializers.CharField(source='unit.course.code', read_only=True)

    class Meta:
        model = Quiz
        list_serializer_class = QuizListListSerializer
        fields = [
            'id', 'title', 'description', 'passing_score', 'points',
            'max_attempts', 'order', 'question_count', 'best_score',
            'attempt_count', 'attempts_remaining', 'unit', 'unit_title', 'course_code', 'created_at'
        ]

    def _is_primed(self, obj):
        """Whether the bulk lookup already covered this quiz."""
        primed = self.context.get(_PRIMED_KEY)
        return primed is not None and obj.pk in primed

    def get_best_score(self, obj):
        user = self.context.get('request').user
        if user.is_instructor:
            return None
        if self._is_primed(obj):
            return self.context[_BESTS_KEY].get(obj.pk)
        best_attempt = obj.attempts.filter(
            student=user, status=QuizAttempt.STATUS_COMPLETED
        ).order_by('-score').first()
        if best_attempt:
            return {
                'score': float(best_attempt.score),
                'passed': best_attempt.passed,
                'completed_at': best_attempt.completed_at
            }
        return None

    def get_attempt_count(self, obj):
        if self._is_primed(obj):
            return self.context[_COUNTS_KEY].get(obj.pk, 0)
        user = self.context.get('request').user
        if user.is_instructor:
            return obj.attempts.filter(status=QuizAttempt.STATUS_COMPLETED).count()
        return obj.attempts.filter(
            student=user, status=QuizAttempt.STATUS_COMPLETED
        ).count()

    def get_attempts_remaining(self, obj):
        user = self.context.get('request').user
        if user.is_instructor:
            return None
        if obj.max_attempts == 0:
            return None  # Unlimited
        # Same count ``attempt_count`` needs — reuse it instead of re-running
        # the identical query (phase 63, decision 9).
        return max(0, obj.max_attempts - self.get_attempt_count(obj))


class QuizDetailSerializer(serializers.ModelSerializer):
    """Serializer for quiz detail (instructor view with answers)."""
    questions = QuestionSerializer(many=True, read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    unit_title = serializers.CharField(source='unit.title', read_only=True)
    course_code = serializers.CharField(source='unit.course.code', read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'passing_score', 'points',
            'max_attempts', 'order', 'questions', 'question_count', 'unit_title',
            'course_code', 'created_at', 'updated_at'
        ]


class QuizStudentDetailSerializer(serializers.ModelSerializer):
    """Serializer for quiz detail (student view, hides correct answers)."""
    questions = QuestionStudentSerializer(many=True, read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    unit_title = serializers.CharField(source='unit.title', read_only=True)
    course_code = serializers.CharField(source='unit.course.code', read_only=True)
    best_score = serializers.SerializerMethodField()
    attempt_count = serializers.SerializerMethodField()
    attempts_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'passing_score', 'points',
            'max_attempts', 'order', 'questions', 'question_count', 'unit_title',
            'course_code', 'best_score', 'attempt_count', 'attempts_remaining', 'created_at'
        ]

    def get_best_score(self, obj):
        user = self.context.get('request').user
        best_attempt = obj.attempts.filter(
            student=user, status=QuizAttempt.STATUS_COMPLETED
        ).order_by('-score').first()
        if best_attempt:
            return {
                'score': float(best_attempt.score),
                'passed': best_attempt.passed,
                'completed_at': best_attempt.completed_at
            }
        return None

    def get_attempt_count(self, obj):
        user = self.context.get('request').user
        return obj.attempts.filter(
            student=user, status=QuizAttempt.STATUS_COMPLETED
        ).count()

    def get_attempts_remaining(self, obj):
        user = self.context.get('request').user
        if obj.max_attempts == 0:
            return None  # Unlimited
        user_attempts = obj.attempts.filter(
            student=user, status=QuizAttempt.STATUS_COMPLETED
        ).count()
        return max(0, obj.max_attempts - user_attempts)


class QuizCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating quizzes."""
    class Meta:
        model = Quiz
        fields = ['title', 'description', 'passing_score', 'points', 'max_attempts', 'order']


class QuestionCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating questions with choices."""
    choices = ChoiceSerializer(many=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'order', 'choices']

    def create(self, validated_data):
        choices_data = validated_data.pop('choices')
        question = Question.objects.create(**validated_data)
        for i, choice_data in enumerate(choices_data):
            choice_data['order'] = i
            Choice.objects.create(question=question, **choice_data)
        return question

    def update(self, instance, validated_data):
        choices_data = validated_data.pop('choices', None)
        instance.text = validated_data.get('text', instance.text)
        instance.order = validated_data.get('order', instance.order)
        instance.save()

        if choices_data is not None:
            # Delete existing choices and recreate
            instance.choices.all().delete()
            for i, choice_data in enumerate(choices_data):
                choice_data['order'] = i
                Choice.objects.create(question=instance, **choice_data)

        return instance


class AttemptAnswerSerializer(serializers.ModelSerializer):
    """Serializer for attempt answers."""
    question_text = serializers.CharField(source='question.text', read_only=True)
    selected_choice_text = serializers.CharField(source='selected_choice.text', read_only=True)
    correct_choice_text = serializers.SerializerMethodField()

    class Meta:
        model = AttemptAnswer
        fields = [
            'question', 'question_text', 'selected_choice',
            'selected_choice_text', 'is_correct', 'correct_choice_text'
        ]

    def get_correct_choice_text(self, obj):
        question = obj.question
        # Use the prefetched choices when the caller supplied them
        # (``prefetch_related('answers__question__choices')``). .filter() would
        # rebuild the queryset and defeat the cache, so iterate instead; the
        # cache is ordered by Choice.Meta.ordering ('order'), the same order
        # ``.filter(...).first()`` used.
        if 'choices' in getattr(question, '_prefetched_objects_cache', {}):
            for choice in question.choices.all():
                if choice.is_correct:
                    return choice.text
            return None
        correct = question.choices.filter(is_correct=True).first()
        return correct.text if correct else None


class QuizAttemptSerializer(serializers.ModelSerializer):
    """Serializer for quiz attempts."""
    answers = AttemptAnswerSerializer(many=True, read_only=True)
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    points_earned = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'quiz', 'quiz_title', 'score', 'passed',
            'points_earned', 'completed_at', 'answers'
        ]


class QuizSubmissionSerializer(serializers.Serializer):
    """Serializer for submitting quiz answers."""
    answers = serializers.DictField(
        child=serializers.IntegerField(),
        help_text="Dict of question_id: choice_id"
    )
