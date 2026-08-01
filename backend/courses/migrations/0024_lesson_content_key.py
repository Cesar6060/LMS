"""
Phase 65: give every Lesson a stable ``content_key`` — the XP identity that
survives a delete-and-recreate.

Three operations, in this order and for this reason:

1. ``AddField`` nullable, NOT unique, with NO default. A single ``AddField``
   carrying ``default=generate_content_key`` would evaluate the callable ONCE
   and write the same value to every row, violating uniqueness the moment the
   index is added.
2. ``RunPython`` stamping a distinct ``auto:<uuid4hex>`` on each existing row.
3. ``AlterField`` to add ``unique=True`` and the callable default, which from
   here on applies per-INSERT.

The column lands nullable and stays nullable (decision 8): migrations are
hand-applied to Neon BEFORE the new code deploys, and Postgres allows many
NULLs under a unique index, so old code that inserts without the column keeps
working through the whole deploy window.
"""
import uuid

import courses.models
from django.db import migrations, models


def stamp_auto_keys(apps, schema_editor):
    Lesson = apps.get_model('courses', 'Lesson')
    to_update = []
    for lesson in Lesson.objects.filter(content_key__isnull=True).only('id'):
        lesson.content_key = f'auto:{uuid.uuid4().hex}'
        to_update.append(lesson)
    if to_update:
        Lesson.objects.bulk_update(to_update, ['content_key'], batch_size=500)


def noop_reverse(apps, schema_editor):
    """Reverse leaves the keys in place; the AddField reversal drops the column."""


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0023_lessonsection_image_lessonsection_image_alt'),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='content_key',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.RunPython(stamp_auto_keys, noop_reverse),
        migrations.AlterField(
            model_name='lesson',
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
