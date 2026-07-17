from django.contrib import admin

from .models import Thread, Reply


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'author', 'is_pinned', 'is_locked', 'created_at')
    list_filter = ('is_pinned', 'is_locked', 'course')
    search_fields = ('title', 'content')


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ('thread', 'author', 'created_at')
    search_fields = ('content',)
