"""
Phase 65: give every Quiz a stable ``content_key``.

Same three-step shape as ``courses.0024`` and for the same reasons — see that
module's docstring for why the callable default cannot ride along on the
``AddField``, and why the column stays nullable.
"""
import uuid

import courses.models
from django.db import migrations, models


def stamp_auto_keys(apps, schema_editor):
    Quiz = apps.get_model('quizzes', 'Quiz')
    to_update = []
    for quiz in Quiz.objects.filter(content_key__isnull=True).only('id'):
        quiz.content_key = f'auto:{uuid.uuid4().hex}'
        to_update.append(quiz)
    if to_update:
        Quiz.objects.bulk_update(to_update, ['content_key'], batch_size=500)


def noop_reverse(apps, schema_editor):
    """Reverse leaves the keys in place; the AddField reversal drops the column."""


class Migration(migrations.Migration):

    dependencies = [
        ('quizzes', '0003_attemptanswer_mastered_at_quizattempt_status_and_more'),
        ('courses', '0024_lesson_content_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='quiz',
            name='content_key',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.RunPython(stamp_auto_keys, noop_reverse),
        migrations.AlterField(
            model_name='quiz',
            name='content_key',
            field=models.CharField(
                blank=True,
                default=courses.models.generate_content_key,
                help_text='Stable identity across content rebuilds. Seeded content uses an '
                          'author-chosen slug; anything else gets auto:<uuid>.',
                max_length=100,
                null=True,
                unique=True,
            ),
        ),
    ]
