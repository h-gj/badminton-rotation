# Generated manually for initial setup

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Player',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, verbose_name='姓名')),
                ('nickname', models.CharField(blank=True, max_length=50, verbose_name='昵称')),
                ('phone', models.CharField(blank=True, max_length=20, verbose_name='手机号')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
            ],
            options={
                'verbose_name': '球员',
                'verbose_name_plural': '球员',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Session',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100, verbose_name='活动名称')),
                ('event_date', models.DateField(verbose_name='活动日期')),
                ('location', models.CharField(blank=True, max_length=100, verbose_name='场地')),
                ('courts', models.PositiveSmallIntegerField(default=2, verbose_name='场地数')),
                ('rounds', models.PositiveSmallIntegerField(default=5, verbose_name='轮次数')),
                ('max_players', models.PositiveSmallIntegerField(default=16, verbose_name='人数上限')),
                ('status', models.CharField(
                    choices=[
                        ('open', '报名中'),
                        ('scheduled', '已排阵'),
                        ('in_progress', '进行中'),
                        ('completed', '已结束'),
                    ],
                    default='open',
                    max_length=20,
                    verbose_name='状态',
                )),
                ('notes', models.TextField(blank=True, verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
            ],
            options={
                'verbose_name': '活动场次',
                'verbose_name_plural': '活动场次',
                'ordering': ['-event_date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Registration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('registered_at', models.DateTimeField(auto_now_add=True, verbose_name='报名时间')),
                ('player', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='registrations',
                    to='rotation.player',
                    verbose_name='球员',
                )),
                ('session', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='registrations',
                    to='rotation.session',
                    verbose_name='场次',
                )),
            ],
            options={
                'verbose_name': '报名',
                'verbose_name_plural': '报名',
                'ordering': ['registered_at'],
                'unique_together': {('session', 'player')},
            },
        ),
        migrations.CreateModel(
            name='Match',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('round_number', models.PositiveSmallIntegerField(verbose_name='轮次')),
                ('court_number', models.PositiveSmallIntegerField(verbose_name='场地')),
                ('score_team1', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='A队得分')),
                ('score_team2', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='B队得分')),
                ('is_completed', models.BooleanField(default=False, verbose_name='已录入比分')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('session', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='matches',
                    to='rotation.session',
                    verbose_name='场次',
                )),
                ('team1_player1', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='team1_p1_matches',
                    to='rotation.player',
                    verbose_name='A队球员1',
                )),
                ('team1_player2', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='team1_p2_matches',
                    to='rotation.player',
                    verbose_name='A队球员2',
                )),
                ('team2_player1', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='team2_p1_matches',
                    to='rotation.player',
                    verbose_name='B队球员1',
                )),
                ('team2_player2', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='team2_p2_matches',
                    to='rotation.player',
                    verbose_name='B队球员2',
                )),
            ],
            options={
                'verbose_name': '对阵',
                'verbose_name_plural': '对阵',
                'ordering': ['round_number', 'court_number'],
                'unique_together': {('session', 'round_number', 'court_number')},
            },
        ),
    ]
