from decimal import Decimal

from django.db import migrations, models


def redistribute_weights(apps, schema_editor):
    """Fold the old assignments weight into quizzes/participation proportionally.

    The two surviving weights are rescaled to sum to 100. A config where both
    are 0 (e.g. 100% assignments) becomes 50/50.
    """
    CourseGradingConfig = apps.get_model('courses', 'CourseGradingConfig')
    for config in CourseGradingConfig.objects.all():
        quizzes = config.quizzes_weight or Decimal('0')
        participation = config.participation_weight or Decimal('0')
        remaining = quizzes + participation
        if remaining == 0:
            config.quizzes_weight = Decimal('50')
            config.participation_weight = Decimal('50')
        else:
            new_quizzes = (quizzes / remaining * 100).quantize(Decimal('0.01'))
            config.quizzes_weight = new_quizzes
            config.participation_weight = Decimal('100') - new_quizzes
        config.save(update_fields=['quizzes_weight', 'participation_weight'])


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0013_add_end_time_to_reminder'),
    ]

    operations = [
        migrations.RunPython(redistribute_weights, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='coursegradingconfig',
            name='assignments_weight',
        ),
        migrations.AlterField(
            model_name='coursegradingconfig',
            name='quizzes_weight',
            field=models.DecimalField(decimal_places=2, default=50, help_text='Weight percentage for quizzes (0-100)', max_digits=5),
        ),
        migrations.AlterField(
            model_name='coursegradingconfig',
            name='participation_weight',
            field=models.DecimalField(decimal_places=2, default=50, help_text='Weight percentage for participation/lesson completion (0-100)', max_digits=5),
        ),
    ]
