from django.contrib import admin
from .models import Quiz, Question, Choice, QuizAttempt, AttemptAnswer


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'unit', 'passing_score', 'points', 'question_count', 'created_at']
    list_filter = ['unit__course', 'created_at']
    search_fields = ['title', 'description']
    inlines = [QuestionInline]

    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Questions'


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['text_preview', 'quiz', 'order', 'choice_count']
    list_filter = ['quiz__unit__course']
    search_fields = ['text']
    inlines = [ChoiceInline]

    def text_preview(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Question'

    def choice_count(self, obj):
        return obj.choices.count()
    choice_count.short_description = 'Choices'


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['student', 'quiz', 'score', 'passed', 'completed_at']
    list_filter = ['passed', 'quiz__unit__course', 'completed_at']
    search_fields = ['student__email', 'quiz__title']
    readonly_fields = ['completed_at']
