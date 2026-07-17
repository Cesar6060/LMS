"""
Rewrite legacy notification URLs of the form /assignments/<id> to the
course-nested /courses/<code>/assignments/<id> path that the frontend
actually routes. Rows pointing at a deleted assignment get related_url=''.
"""

import re

from django.db import migrations

ASSIGNMENT_URL_RE = re.compile(r'^/assignments/(\d+)$')


def rewrite_assignment_urls(apps, schema_editor):
    Notification = apps.get_model('notifications', 'Notification')
    Assignment = apps.get_model('assignments', 'Assignment')

    for notification in Notification.objects.filter(related_url__regex=r'^/assignments/\d+$'):
        match = ASSIGNMENT_URL_RE.match(notification.related_url)
        if not match:
            continue
        assignment = (
            Assignment.objects.filter(pk=int(match.group(1)))
            .select_related('unit__course')
            .first()
        )
        if assignment is None:
            notification.related_url = ''
        else:
            notification.related_url = (
                f'/courses/{assignment.unit.course.code}/assignments/{assignment.pk}'
            )
        notification.save(update_fields=['related_url'])


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_alter_notification_type'),
        ('assignments', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(rewrite_assignment_urls, migrations.RunPython.noop),
    ]
