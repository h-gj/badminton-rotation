from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rotation', '0002_session_event_datetime'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='gender',
            field=models.CharField(
                blank=True,
                choices=[('', '未设置'), ('M', '男'), ('F', '女')],
                default='',
                max_length=1,
                verbose_name='性别',
            ),
        ),
        migrations.AddField(
            model_name='session',
            name='avoid_mixed_gender_doubles',
            field=models.BooleanField(default=False, verbose_name='避免女双对男双'),
        ),
    ]
