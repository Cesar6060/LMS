from contextlib import contextmanager

from django.db.models.signals import post_save
from django.dispatch import receiver

from notifications.models import Notification
from .models import UserBadge

# When True, badge earns do NOT create bell notifications. Used by the backfill
# command so historical badges don't drop a burst of (wrongly-framed "just
# earned") notifications on existing students at launch.
_suppress_badge_notifications = False


@contextmanager
def suppress_badge_notifications():
    """Suppress badge-earned bell notifications within the block."""
    global _suppress_badge_notifications
    previous = _suppress_badge_notifications
    _suppress_badge_notifications = True
    try:
        yield
    finally:
        _suppress_badge_notifications = previous


@receiver(post_save, sender=UserBadge)
def notify_on_badge_earned(sender, instance, created, **kwargs):
    """Create a persistent bell notification when a badge is earned."""
    if not created or _suppress_badge_notifications:
        return
    badge = instance.badge
    Notification.objects.create(
        recipient=instance.user,
        type='badge_earned',
        title=f'Badge earned: {badge.name}',
        message=f'{badge.icon} You earned the "{badge.name}" badge — {badge.description}.',
        related_url='/settings?tab=achievements',
    )
