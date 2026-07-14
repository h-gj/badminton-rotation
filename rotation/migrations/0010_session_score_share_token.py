import secrets

from django.db import migrations, models


def _generate_token():
    return secrets.token_urlsafe(16)


def backfill_score_share_tokens(apps, schema_editor):
    Session = apps.get_model('rotation', 'Session')
    used = set(
        Session.objects.exclude(score_share_token='')
        .values_list('score_share_token', flat=True)
    )
    for session in Session.objects.filter(score_share_token=''):
        while True:
            token = _generate_token()
            if token not in used:
                used.add(token)
                session.score_share_token = token
                session.save(update_fields=['score_share_token'])
                break


class Migration(migrations.Migration):

    dependencies = [
        ('rotation', '0009_player_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='score_share_token',
            field=models.CharField(blank=True, default='', max_length=32, verbose_name='计分分享令牌'),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_score_share_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='session',
            name='score_share_token',
            field=models.CharField(blank=True, max_length=32, unique=True, verbose_name='计分分享令牌'),
        ),
    ]
