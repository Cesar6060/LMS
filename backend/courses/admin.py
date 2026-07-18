from django.contrib import admin
from .models import Course, Unit, Lesson, Enrollment, LessonProgress, CourseGradingConfig


class UnitInline(admin.TabularInline):
    model = Unit
    extra = 0
    ordering = ['order']


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    ordering = ['order']
    fields = ['title', 'order', 'video_type', 'video_id']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['code', 'title', 'instructor', 'is_active', 'enrollment_code', 'student_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['code', 'title', 'instructor__email']
    readonly_fields = ['enrollment_code', 'created_at', 'updated_at']
    inlines = [UnitInline]

    def student_count(self, obj):
        return obj.enrollments.count()
    student_count.short_description = 'Students'


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'order', 'lesson_count']
    list_filter = ['course']
    search_fields = ['title', 'course__code', 'course__title']
    ordering = ['course', 'order']
    inlines = [LessonInline]

    def lesson_count(self, obj):
        return obj.lessons.count()
    lesson_count.short_description = 'Lessons'


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'unit', 'order', 'video_type', 'created_at']
    list_filter = ['video_type', 'unit__course']
    search_fields = ['title', 'unit__title', 'unit__course__code']
    ordering = ['unit__course', 'unit__order', 'order']


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'enrolled_at']
    list_filter = ['course', 'enrolled_at']
    search_fields = ['user__email', 'course__code', 'course__title']
    readonly_fields = ['enrolled_at']


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'lesson', 'completed', 'video_position', 'updated_at']
    list_filter = ['completed', 'lesson__unit__course']
    search_fields = ['user__email', 'lesson__title']
    readonly_fields = ['updated_at']


@admin.register(CourseGradingConfig)
class CourseGradingConfigAdmin(admin.ModelAdmin):
    list_display = ['course', 'quizzes_weight', 'participation_weight', 'updated_at']
    list_filter = ['updated_at']
    search_fields = ['course__code', 'course__title']
    readonly_fields = ['created_at', 'updated_at']
