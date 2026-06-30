from django.db import models


class Player(models.Model):
    name = models.CharField('姓名', max_length=50)
    nickname = models.CharField('昵称', max_length=50, blank=True)
    phone = models.CharField('手机号', max_length=20, blank=True)
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


class Session(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', '报名中'
        SCHEDULED = 'scheduled', '已排阵'
        IN_PROGRESS = 'in_progress', '进行中'
        COMPLETED = 'completed', '已结束'

    title = models.CharField('活动名称', max_length=100)
    event_date = models.DateTimeField('活动时间')
    location = models.CharField('场地号', max_length=100, blank=True)
    courts = models.PositiveSmallIntegerField('场地数', default=2)
    rounds = models.PositiveSmallIntegerField('轮次数', default=5)
    max_players = models.PositiveSmallIntegerField('人数上限', default=16)
    status = models.CharField(
        '状态', max_length=20, choices=Status.choices, default=Status.OPEN
    )
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '活动场次'
        verbose_name_plural = '活动场次'
        ordering = ['-event_date', '-created_at']

    def __str__(self):
        return self.title

    @property
    def player_count(self):
        return self.registrations.count()

    @property
    def can_generate(self):
        if self.status != self.Status.OPEN or self.player_count < 4:
            return False
        slots = min(self.player_count, self.courts * 4)
        return (slots // 4) * 4 >= 4


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

    def team1_players(self):
        return [self.team1_player1, self.team1_player2]

    def team2_players(self):
        return [self.team2_player1, self.team2_player2]
