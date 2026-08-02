"""
Phase 65: move the XP award-once guarantee from ``source_id`` to ``source_key``.

``source_key`` lands nullable and is backfilled from the target's
``content_key``; rows whose target no longer exists (the damage earlier
destructive reseeds already did) are labelled ``orphan:<source_type>:<pk>`` so
they stay distinct, keep their XP, and are countable by ``audit_xp``.

Depends on ``courses.0024`` and ``quizzes.0004`` so the keys exist by the time
this runs. The new ``unique_together`` is added AFTER the backfill; adding it
first would be harmless (Postgres allows many NULLs under a unique index) but
this ordering keeps the intent obvious.

Orphan labelling never collides with a live key: live keys are unique per
model, and every orphan label carries its own primary key.
"""
from django.db import migrations, models


def backfill_source_keys(apps, schema_editor):
    XPEvent = apps.get_model('gamification', 'XPEvent')
    Lesson = apps.get_model('courses', 'Lesson')
    Quiz = apps.get_model('quizzes', 'Quiz')

    lesson_keys = dict(Lesson.objects.values_list('id', 'content_key'))
    quiz_keys = dict(Quiz.objects.values_list('id', 'content_key'))

    to_update = []
    for event in XPEvent.objects.filter(source_key__isnull=True).only(
        'id', 'source_type', 'source_id'
    ):
        lookup = quiz_keys if event.source_type == 'quiz' else lesson_keys
        key = lookup.get(event.source_id)
        event.source_key = key or f'orphan:{event.source_type}:{event.source_id}'
        to_update.append(event)
    if to_update:
        XPEvent.objects.bulk_update(to_update, ['source_key'], batch_size=500)


def noop_reverse(apps, schema_editor):
    """Reverse leaves the keys in place; the AddField reversal drops the column."""


class Migration(migrations.Migration):

    dependencies = [
        ('gamification', '0005_gameprofile_avatar_aura_gameprofile_avatar_companion_and_more'),
        ('courses', '0024_lesson_content_key'),
        ('quizzes', '0004_quiz_content_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='xpevent',
            name='source_key',
            field=models.CharField(
                blank=True,
                help_text="The target's content_key. This is what dedupes; source_id is history.",
                max_length=100,
                null=True,
            ),
        ),
        # source_id becomes nullable: the legacy uniqueness on it is still
        # live, so an award that carries no id must land NULL rather than a
        # shared sentinel that would collide with every other keyless row.
        # Widening NOT NULL -> NULL is safe for the still-running old code,
        # which always writes the column.
        migrations.AlterField(
            model_name='xpevent',
            name='source_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_source_keys, noop_reverse),
        migrations.AlterUniqueTogether(
            name='xpevent',
            unique_together={
                ('user', 'source_type', 'source_id'),
                ('user', 'source_type', 'source_key'),
            },
        ),
    ]
