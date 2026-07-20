from django.db import migrations

from gamification.catalog import seed_badges


def forwards(apps, schema_editor):
    Badge = apps.get_model('gamification', 'Badge')
    seed_badges(Badge)


def backwards(apps, schema_editor):
    Badge = apps.get_model('gamification', 'Badge')
    from gamification.catalog import BADGE_CATALOG
    Badge.objects.filter(key__in=[b['key'] for b in BADGE_CATALOG]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('gamification', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
