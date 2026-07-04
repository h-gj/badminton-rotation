from datetime import time

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rotation', '0003_player_gender_session_avoid_mixed_gender'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='event_end_time',
            field=models.TimeField(blank=True, null=True, verbose_name='结束时间'),
        ),
    ]
