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


class QuizListSerializer(serializers.ModelSerializer):
    """Serializer for listing quizzes."""
    question_count = serializers.IntegerField(read_only=True)
    best_score = serializers.SerializerMethodField()
    attempt_count = serializers.SerializerMethodField()
    attempts_remaining = serializers.SerializerMethodField()
    unit_title = serializers.CharField(source='unit.title', read_only=True)
    course_code = serializers.CharField(source='unit.course.code', read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'passing_score', 'points',
            'max_attempts', 'order', 'question_count', 'best_score',
            'attempt_count', 'attempts_remaining', 'unit', 'unit_title', 'course_code', 'created_at'
        ]

    def get_best_score(self, obj):
        user = self.context.get('request').user
        if user.is_instructor:
            return None
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
        user_attempts = obj.attempts.filter(
            student=user, status=QuizAttempt.STATUS_COMPLETED
        ).count()
        return max(0, obj.max_attempts - user_attempts)


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
        correct = obj.question.choices.filter(is_correct=True).first()
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
