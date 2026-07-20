from django.contrib import admin

from .models import GameProfile, XPEvent, Badge, UserBadge


@admin.register(GameProfile)
class GameProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_xp', 'level', 'current_streak', 'longest_streak', 'last_activity_date')
    search_fields = ('user__email',)


@admin.register(XPEvent)
class XPEventAdmin(admin.ModelAdmin):
    list_display = ('user', 'source_type', 'source_id', 'amount', 'created_at')
    list_filter = ('source_type',)
    search_fields = ('user__email',)


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('order', 'key', 'name', 'icon', 'criteria_type', 'threshold')
    ordering = ('order',)


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge', 'earned_at')
    search_fields = ('user__email', 'badge__key')
