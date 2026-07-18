from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_preferences'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userpreferences',
            name='email_grades',
        ),
        migrations.RemoveField(
            model_name='userpreferences',
            name='email_submissions',
        ),
        migrations.RemoveField(
            model_name='userpreferences',
            name='email_due_reminders',
        ),
    ]
