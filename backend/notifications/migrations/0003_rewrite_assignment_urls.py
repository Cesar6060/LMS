"""
Historical migration, now a no-op.

This used to rewrite legacy /assignments/<id> notification URLs, which
required the assignments app. The assignments app was removed in Phase 18;
the file is kept (empty) so applied migration history stays valid.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_alter_notification_type'),
    ]

    operations = []
