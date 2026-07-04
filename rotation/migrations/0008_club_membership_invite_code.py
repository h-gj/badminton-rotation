import secrets

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _generate_invite_code(Club):
    while True:
        code = secrets.token_hex(3).upper()
        if not Club.objects.filter(invite_code=code).exists():
            return code


def populate_invite_codes(apps, schema_editor):
    Club = apps.get_model('rotation', 'Club')
    for club in Club.objects.filter(invite_code=''):
        club.invite_code = _generate_invite_code(Club)
        club.save(update_fields=['invite_code'])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('rotation', '0007_match_scored_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='club',
            name='invite_code',
            field=models.CharField(blank=True, default='', max_length=8, verbose_name='邀请码'),
        ),
        migrations.RunPython(populate_invite_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='club',
            name='invite_code',
            field=models.CharField(blank=True, max_length=8, unique=True, verbose_name='邀请码'),
        ),
        migrations.CreateModel(
            name='ClubMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('joined_at', models.DateTimeField(auto_now_add=True, verbose_name='加入时间')),
                ('club', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='rotation.club', verbose_name='俱乐部')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='club_memberships', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '俱乐部成员',
                'verbose_name_plural': '俱乐部成员',
            },
        ),
        migrations.AddConstraint(
            model_name='clubmembership',
            constraint=models.UniqueConstraint(fields=('user',), name='unique_user_club_membership'),
        ),
    ]
