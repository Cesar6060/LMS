"""
Phase 53 — Consolidate lesson-level content into sections.

Sections become the single source of truth for lesson body content. This is a
DATA-ONLY migration (no schema change): the lesson-level
``content``/``video_type``/``video_id`` columns are kept but emptied so old code
still tolerates the data while the editor/player stop reading them.

Forward, for every lesson:
  * If the lesson has NO sections AND has real lesson-level content (non-empty
    ``content`` OR a ``youtube`` video with a ``video_id``): create ONE section
    at order 0 carrying that content/video, so students keep seeing it.
  * Then blank the lesson-level fields on EVERY lesson. Lessons that already had
    sections thereby discard their leftover lesson-level content, which was
    already hidden from students by the player (sections shadowed it). Lessons
    just converted have already copied their content into the new section.

Reverse is a noop: the original lesson-level content is intentionally not
reconstructable (this is a one-way consolidation).
"""

from django.db import migrations


def consolidate_content_into_sections(apps, schema_editor):
    Lesson = apps.get_model('courses', 'Lesson')
    LessonSection = apps.get_model('courses', 'LessonSection')

    converted = 0   # no-section lessons whose content became a section
    blanked = 0     # lessons whose lesson-level fields were emptied
    skipped = 0     # nothing to do (no content, no sections)

    for lesson in Lesson.objects.all().iterator():
        has_sections = lesson.sections.exists()
        has_content = bool(lesson.content) or (
            lesson.video_type == 'youtube' and bool(lesson.video_id)
        )

        if not has_sections and has_content:
            # Preserve what students currently see: copy into a first section.
            # Blank title so we don't duplicate the lesson heading shown elsewhere.
            LessonSection.objects.create(
                lesson=lesson,
                order=0,
                title='',
                content=lesson.content,
                video_type=lesson.video_type,
                video_id=lesson.video_id,
            )
            converted += 1

        # Empty the now-dormant lesson-level fields on every lesson.
        if lesson.content or lesson.video_type != 'none' or lesson.video_id:
            lesson.content = ''
            lesson.video_type = 'none'
            lesson.video_id = ''
            lesson.save(update_fields=['content', 'video_type', 'video_id'])
            blanked += 1
        elif not has_content and not has_sections:
            skipped += 1

    print(
        f"\n[0019] lesson content consolidation: "
        f"{converted} converted to a first section, "
        f"{blanked} lesson-level fields blanked, "
        f"{skipped} lessons untouched."
    )


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0018_repair_video_ids'),
    ]

    operations = [
        migrations.RunPython(
            consolidate_content_into_sections,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
