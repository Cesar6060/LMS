from django.db import migrations, models

REMOVED_TYPES = ['submission', 'grade', 'new_assignment', 'resubmission']


def delete_assignment_notifications(apps, schema_editor):
    Notification = apps.get_model('notifications', 'Notification')
    Notification.objects.filter(type__in=REMOVED_TYPES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_rewrite_assignment_urls'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='type',
            field=models.CharField(choices=[('enrollment', 'New Enrollment'), ('new_lesson', 'New Lesson'), ('announcement', 'New Announcement'), ('reply', 'New Reply')], max_length=20),
        ),
        migrations.RunPython(delete_assignment_notifications, migrations.RunPython.noop),
    ]
