from django.conf import settings
from django.db import models
from django.utils import timezone
import secrets


def _local_now():
    return timezone.localtime()


def _generate_club_invite_code():
    while True:
        code = secrets.token_hex(3).upper()
        if not Club.objects.filter(invite_code=code).exists():
            return code


class Club(models.Model):
    name = models.CharField('俱乐部名称', max_length=100)
    description = models.TextField('简介', blank=True)
    invite_code = models.CharField('邀请码', max_length=8, unique=True, blank=True)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_club',
        verbose_name='创建者',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '俱乐部'
        verbose_name_plural = '俱乐部'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.invite_code:
            self.invite_code = _generate_club_invite_code()
        super().save(*args, **kwargs)


class ClubMembership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='club_memberships',
        verbose_name='用户',
    )
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='memberships',
        verbose_name='俱乐部',
    )
    joined_at = models.DateTimeField('加入时间', auto_now_add=True)

    class Meta:
        verbose_name = '俱乐部成员'
        verbose_name_plural = '俱乐部成员'
        constraints = [
            models.UniqueConstraint(fields=['user'], name='unique_user_club_membership'),
        ]

    def __str__(self):
        return f'{self.user} @ {self.club}'


class Player(models.Model):
    class Gender(models.TextChoices):
        UNKNOWN = '', '未设置'
        MALE = 'M', '男'
        FEMALE = 'F', '女'

    name = models.CharField('姓名', max_length=50)
    nickname = models.CharField('昵称', max_length=50, blank=True)
    phone = models.CharField('手机号', max_length=20, blank=True)
    gender = models.CharField(
        '性别', max_length=1, choices=Gender.choices, blank=True, default='',
    )
    avatar = models.ImageField('头像', upload_to='avatars/', blank=True, null=True)
    club = models.ForeignKey(
        Club, on_delete=models.CASCADE, related_name='players',
        verbose_name='俱乐部', null=True, blank=True,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='player_profile',
        verbose_name='登录账号',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '球员'
        verbose_name_plural = '球员'
        ordering = ['name']

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.nickname or self.name

    @property
    def login_username(self):
        return self.user.username if self.user_id else ''


def _generate_score_share_token():
    while True:
        token = secrets.token_urlsafe(16)
        if not Session.objects.filter(score_share_token=token).exists():
            return token


class Session(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', '报名中'
        SCHEDULED = 'scheduled', '已排阵'
        IN_PROGRESS = 'in_progress', '进行中'
        COMPLETED = 'completed', '已结束'

    title = models.CharField('活动名称', max_length=100)
    event_date = models.DateTimeField('活动时间')
    event_end_time = models.TimeField('结束时间', null=True, blank=True)
    location = models.CharField('场地号', max_length=100, blank=True)
    courts = models.PositiveSmallIntegerField('场地数', default=2)
    rounds = models.PositiveSmallIntegerField('轮次数', default=15)
    max_players = models.PositiveSmallIntegerField('人数上限', default=16)
    avoid_mixed_gender_doubles = models.BooleanField('避免女双对男双', default=False)
    status = models.CharField(
        '状态', max_length=20, choices=Status.choices, default=Status.OPEN
    )
    notes = models.TextField('备注', blank=True)
    club = models.ForeignKey(
        Club, on_delete=models.CASCADE, related_name='sessions',
        verbose_name='俱乐部', null=True, blank=True,
    )
    score_share_token = models.CharField(
        '计分分享令牌', max_length=32, unique=True, blank=True,
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '活动场次'
        verbose_name_plural = '活动场次'
        ordering = ['-event_date', '-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.score_share_token:
            self.score_share_token = _generate_score_share_token()
        super().save(*args, **kwargs)

    @property
    def player_count(self):
        return self.registrations.count()

    @property
    def event_time_label(self):
        local = timezone.localtime(self.event_date)
        start = local.strftime('%H:%M')
        if self.event_end_time:
            return f'{local.strftime("%Y-%m-%d")} {start}-{self.event_end_time.strftime("%H:%M")}'
        return local.strftime('%Y-%m-%d %H:%M')

    @property
    def can_generate(self):
        if self.status != self.Status.OPEN or self.player_count < 4:
            return False
        slots = min(self.player_count, self.courts * 4)
        return (slots // 4) * 4 >= 4

    @property
    def event_end_at(self):
        """活动计划结束时刻；未设置结束时间时返回 None。"""
        if not self.event_end_time:
            return None
        event_start = timezone.localtime(self.event_date)
        return event_start.replace(
            hour=self.event_end_time.hour,
            minute=self.event_end_time.minute,
            second=0,
            microsecond=0,
        )

    @property
    def scores_editable(self):
        """是否仍可录入或修改比分。

        已设置比赛结束时间：当前时间早于该结束时刻则可编辑。
        未设置结束时间：创建当天可编辑，过了创建日则锁定。
        """
        now = _local_now()
        end_at = self.event_end_at
        created = timezone.localtime(self.created_at)
        if end_at is not None:
            if end_at < created:
                return now.date() <= created.date()
            return now < end_at
        return now.date() <= created.date()


class Registration(models.Model):
    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name='registrations', verbose_name='场次'
    )
    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name='registrations', verbose_name='球员'
    )
    registered_at = models.DateTimeField('报名时间', auto_now_add=True)

    class Meta:
        verbose_name = '报名'
        verbose_name_plural = '报名'
        unique_together = [('session', 'player')]
        ordering = ['registered_at']

    def __str__(self):
        return f'{self.session.title} - {self.player.display_name}'


class Match(models.Model):
    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name='matches', verbose_name='场次'
    )
    round_number = models.PositiveSmallIntegerField('轮次')
    court_number = models.PositiveSmallIntegerField('场地')
    team1_player1 = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name='team1_p1_matches', verbose_name='A队球员1'
    )
    team1_player2 = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name='team1_p2_matches', verbose_name='A队球员2'
    )
    team2_player1 = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name='team2_p1_matches', verbose_name='B队球员1'
    )
    team2_player2 = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name='team2_p2_matches', verbose_name='B队球员2'
    )
    score_team1 = models.PositiveSmallIntegerField('A队得分', null=True, blank=True)
    score_team2 = models.PositiveSmallIntegerField('B队得分', null=True, blank=True)
    is_completed = models.BooleanField('已录入比分', default=False)
    scored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scored_matches',
        verbose_name='录入者',
    )
    scored_at = models.DateTimeField('录入时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '对阵'
        verbose_name_plural = '对阵'
        ordering = ['round_number', 'court_number']
        unique_together = [('session', 'round_number', 'court_number')]

    def __str__(self):
        return (
            f'第{self.round_number}轮 场地{self.court_number}: '
            f'{self.team1_label} vs {self.team2_label}'
        )

    @property
    def team1_label(self):
        return f'{self.team1_player1.display_name}/{self.team1_player2.display_name}'

    @property
    def team2_label(self):
        return f'{self.team2_player1.display_name}/{self.team2_player2.display_name}'

    @property
    def winner_team(self):
        if not self.is_completed or self.score_team1 is None or self.score_team2 is None:
            return None
        if self.score_team1 > self.score_team2:
            return 1
        if self.score_team2 > self.score_team1:
            return 2
        return 0

    @property
    def score_diff(self):
        if not self.is_completed or self.score_team1 is None or self.score_team2 is None:
            return None
        return abs(self.score_team1 - self.score_team2)

    @property
    def scored_by_display(self):
        if self.scored_by:
            return self.scored_by.get_full_name() or self.scored_by.username
        if self.is_completed and self.scored_at:
            return '匿名用户'
        return ''

    def team1_players(self):
        return [self.team1_player1, self.team1_player2]

    def team2_players(self):
        return [self.team2_player1, self.team2_player2]
