# Generated migration for assignment availability and late penalty fields

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assignments', '0004_add_files_info_to_history'),
    ]

    operations = [
        # Add availability fields to Assignment
        migrations.AddField(
            model_name='assignment',
            name='available_from',
            field=models.DateTimeField(
                blank=True,
                help_text='Assignment becomes visible from this date',
                null=True
            ),
        ),
        migrations.AddField(
            model_name='assignment',
            name='available_until',
            field=models.DateTimeField(
                blank=True,
                help_text='Submissions close after this date',
                null=True
            ),
        ),
        # Add late penalty fields to Assignment
        migrations.AddField(
            model_name='assignment',
            name='late_penalty_percent',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Percentage deducted per day/hour late',
                max_digits=5,
                null=True
            ),
        ),
        migrations.AddField(
            model_name='assignment',
            name='late_penalty_interval',
            field=models.CharField(
                choices=[('day', 'Per Day'), ('hour', 'Per Hour')],
                default='day',
                max_length=10
            ),
        ),
        migrations.AddField(
            model_name='assignment',
            name='max_late_penalty',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Maximum percentage penalty cap',
                max_digits=5,
                null=True
            ),
        ),
        # Add late penalty tracking to Submission
        migrations.AddField(
            model_name='submission',
            name='late_penalty_applied',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0'),
                help_text='Points deducted for late submission',
                max_digits=5
            ),
        ),
    ]
