from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User, UserPreferences


@receiver(post_save, sender=User)
def create_user_preferences(sender, instance, created, **kwargs):
    """Auto-create UserPreferences when a new user is created."""
    if created:
        UserPreferences.objects.get_or_create(user=instance)
