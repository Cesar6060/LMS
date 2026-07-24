"""Phase 55 (C4): drop the two dormant Lesson quiz columns.

`required_quiz` was the retired cross-course gate (System A). Migration 0020
cleared every value; production carried it on 0 of 40 lessons at audit time, and
phase 54 already made it non-writable and non-readable through the API.

`max_quiz_attempts` was last enforced by `submit_lesson_quiz`, the pre-phase-32
batch quiz endpoint deleted earlier in this phase (C2). The mastery session that
replaced it re-queues missed questions until they are mastered, so a pass is
guaranteed and an attempt cap has no meaning. Production had it non-zero on all
40 lessons, but nothing has read it since phase 32.

**These are irreversible in practice.** RemoveField drops the column and its
data; the auto-generated reverse re-adds an empty column. Applied locally and
verified here — the Neon apply is a deliberate operator step at merge time, with
the daily R2 backup as the recovery net.

The three AlterFields are help_text-only (C5's DORMANT annotations) and touch no
data.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0020_lesson_requires_quiz'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='lesson',
            name='max_quiz_attempts',
        ),
        migrations.RemoveField(
            model_name='lesson',
            name='required_quiz',
        ),
        migrations.AlterField(
            model_name='lesson',
            name='content',
            field=models.TextField(blank=True, help_text='DORMANT (Phase 53): superseded by LessonSection.content.'),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='video_id',
            field=models.CharField(blank=True, help_text='DORMANT (Phase 53): superseded by LessonSection.video_id.', max_length=50),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='video_type',
            field=models.CharField(choices=[('none', 'No Video'), ('youtube', 'YouTube')], default='none', help_text='DORMANT (Phase 53): superseded by LessonSection.video_type.', max_length=10),
        ),
    ]
