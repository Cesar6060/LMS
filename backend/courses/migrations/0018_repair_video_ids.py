# Phase 52: repair rows corrupted by the old frontend parser, which stored
# full URLs as video_id, and retire the never-implemented vimeo option.

from django.db import migrations

# Deliberate import of live app code: the extractor is the single source of
# truth for the URL contract and has no model/app-registry dependencies. If
# courses/video.py changes later, a replay of this migration applies the
# newer logic — acceptable for a one-way repair of corrupted/dead data.
from courses.video import VIDEO_ID_RE, extract_youtube_video_id


def repair_video_ids(apps, schema_editor):
    for model_name in ('Lesson', 'LessonSection'):
        model = apps.get_model('courses', model_name)
        vimeo_cleared = model.objects.filter(video_type='vimeo').update(
            video_type='none', video_id='')

        normalized = 0
        nulled = 0
        for row in model.objects.filter(video_type='youtube'):
            if VIDEO_ID_RE.match(row.video_id or ''):
                continue
            extracted = extract_youtube_video_id(row.video_id)
            if extracted:
                row.video_id = extracted
                normalized += 1
            else:
                # Audit trail so support can recover a false-positive null.
                print(f'{model_name} pk={row.pk}: nulling video_id={row.video_id!r}')
                row.video_type = 'none'
                row.video_id = ''
                nulled += 1
            row.save(update_fields=['video_type', 'video_id'])

        print(
            f'{model_name}: {vimeo_cleared} vimeo rows cleared, '
            f'{normalized} video_ids normalized, {nulled} unparseable rows nulled'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0017_alter_lesson_video_id_alter_lesson_video_type_and_more'),
    ]

    operations = [
        migrations.RunPython(repair_video_ids, migrations.RunPython.noop),
    ]
