"""
Phase 54 — Lesson quiz-gating simplification.

Adds ``Lesson.requires_quiz`` (boolean) — the single, explicit per-lesson gate:
when true, students must pass the lesson's own comprehension questions (the
Questions tab) to complete the lesson.

Data step (forward):
  * Seed ``requires_quiz=True`` for every lesson that currently has >=1
    comprehension question, preserving the pre-Phase-54 behavior where any
    question implicitly gated completion.
  * Clear the retired cross-course ``required_quiz`` FK on ALL lessons. That gate
    is removed from enforcement; the column is kept dormant (no schema drop).

Reverse: the AddField reverses normally; the data step is a noop (cleared FK
values are intentionally not reconstructable — this is a one-way retirement).
"""

from django.db import migrations, models
import django.db.models.deletion


def seed_requires_quiz_and_clear_required_quiz(apps, schema_editor):
    Lesson = apps.get_model('courses', 'Lesson')

    seeded = 0   # lessons flipped to requires_quiz=True (had questions)
    cleared = 0  # lessons whose retired required_quiz FK was nulled

    for lesson in Lesson.objects.all():
        if lesson.questions.exists():
            lesson.requires_quiz = True
            seeded += 1
        if lesson.required_quiz_id is not None:
            lesson.required_quiz = None
            cleared += 1
        lesson.save(update_fields=['requires_quiz', 'required_quiz'])

    print(
        f"\n[0020] lesson quiz-gating: "
        f"{seeded} lessons -> requires_quiz=True, "
        f"{cleared} retired required_quiz values cleared."
    )


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0019_consolidate_lesson_content_into_sections'),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='requires_quiz',
            field=models.BooleanField(
                default=False,
                help_text="When true, students must pass this lesson's own "
                          "comprehension questions (the Questions tab) to complete "
                          "the lesson.",
            ),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='required_quiz',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='required_for_lessons',
                to='quizzes.quiz',
                help_text='DORMANT (Phase 54): retired cross-course quiz gate. '
                          'Kept as a dormant column; no longer written or enforced.',
            ),
        ),
        migrations.RunPython(
            seed_requires_quiz_and_clear_required_quiz,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
