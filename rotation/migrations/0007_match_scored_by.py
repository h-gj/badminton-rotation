import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('rotation', '0006_club'),
    ]

    operations = [
        migrations.AddField(
            model_name='match',
            name='scored_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='录入时间'),
        ),
        migrations.AddField(
            model_name='match',
            name='scored_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='scored_matches',
                to=settings.AUTH_USER_MODEL,
                verbose_name='录入者',
            ),
        ),
    ]
