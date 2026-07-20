from rest_framework import serializers

from .models import Badge


class BadgeSerializer(serializers.ModelSerializer):
    """A catalog badge annotated with this user's earned state."""
    earned = serializers.SerializerMethodField()
    earned_at = serializers.SerializerMethodField()

    class Meta:
        model = Badge
        fields = [
            'key', 'name', 'description', 'icon',
            'criteria_type', 'threshold', 'order',
            'earned', 'earned_at',
        ]

    def get_earned(self, obj):
        return obj.id in self.context.get('earned_map', {})

    def get_earned_at(self, obj):
        earned_map = self.context.get('earned_map', {})
        return earned_map.get(obj.id)
