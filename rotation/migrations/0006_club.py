import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('rotation', '0005_player_avatar'),
    ]

    operations = [
        migrations.CreateModel(
            name='Club',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='俱乐部名称')),
                ('description', models.TextField(blank=True, verbose_name='简介')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('owner', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='owned_club', to=settings.AUTH_USER_MODEL, verbose_name='创建者')),
            ],
            options={
                'verbose_name': '俱乐部',
                'verbose_name_plural': '俱乐部',
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='player',
            name='club',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='players', to='rotation.club', verbose_name='俱乐部'),
        ),
        migrations.AddField(
            model_name='session',
            name='club',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to='rotation.club', verbose_name='俱乐部'),
        ),
    ]
