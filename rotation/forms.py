from datetime import time

from django import forms
from django.db.models import Count
from django.utils import timezone

from rotation.models import Match, Player, Session


def default_session_title(player_count):
    return f'{player_count}人多人轮转赛|{timezone.localtime().date().strftime("%m-%d")}'


def default_event_schedule():
    now = timezone.localtime()
    start = now.replace(hour=20, minute=0, second=0, microsecond=0)
    return start, time(20, 0), None


def parse_player_names(text):
    if not text or not text.strip():
        return []
    seen = set()
    names = []
    normalized = text.replace(',', ' ').replace('，', ' ')
    for part in normalized.split():
        if part and part not in seen:
            seen.add(part)
            names.append(part)
    return names


def get_club_players_for_picker(club, exclude_ids=()):
    """本俱乐部球员列表，供报名搜索/多选。"""
    if not club:
        return Player.objects.none()
    qs = (
        Player.objects.filter(club=club)
        .annotate(session_count=Count('registrations'))
        .order_by('-session_count', 'name')
    )
    if exclude_ids:
        qs = qs.exclude(pk__in=exclude_ids)
    return qs


def get_previous_players(club=None):
    """兼容旧调用：返回本俱乐部有报名记录的球员。"""
    qs = Player.objects.annotate(session_count=Count('registrations')).filter(session_count__gt=0)
    if club:
        qs = qs.filter(club=club)
    return qs.order_by('-session_count', 'name')


from rotation.services.round_options import MAX_ROUNDS, MIN_ROUNDS


class SessionMetaForm(forms.Form):
    event_date = forms.DateField(
        label='比赛日期',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    event_start_time = forms.TimeField(
        label='开始时间',
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
    )
    event_end_time = forms.TimeField(
        label='结束时间',
        required=False,
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
    )
    location = forms.CharField(
        label='比赛地点',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '例如：XX羽毛球馆'}),
    )

    def clean(self):
        cleaned = super().clean()
        event_date = cleaned.get('event_date')
        start_time = cleaned.get('event_start_time')
        end_time = cleaned.get('event_end_time')
        if event_date and start_time and end_time and end_time <= start_time:
            raise forms.ValidationError('结束时间须晚于开始时间')
        return cleaned


class SessionAddPlayersForm(forms.Form):
    players = forms.ModelMultipleChoiceField(
        label='选择人员',
        queryset=Player.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    players_manual = forms.CharField(
        label='手动添加',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': '输入新人员姓名，多人请用空格、换行或逗号分隔',
        }),
    )

    def __init__(self, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session
        registered_ids = session.registrations.values_list('player_id', flat=True)
        self.fields['players'].queryset = get_club_players_for_picker(
            session.club, registered_ids,
        )

    def clean_players(self):
        players = self.cleaned_data.get('players')
        club = self.session.club
        if club and players:
            invalid = [p for p in players if p.club_id != club.id]
            if invalid:
                raise forms.ValidationError('只能选择本俱乐部的球员')
        return players

    @property
    def selected_player_pks(self):
        if not self.is_bound:
            return set()
        return {int(pk) for pk in self.data.getlist('players') if pk.isdigit()}


class SessionGenerateSettingsForm(forms.Form):
    rounds = forms.IntegerField(
        label='比赛局数',
        min_value=MIN_ROUNDS,
        max_value=MAX_ROUNDS,
        widget=forms.HiddenInput,
    )
    avoid_mixed_gender_doubles = forms.BooleanField(
        label='避免女双碰到男双',
        required=False,
        initial=False,
        widget=forms.HiddenInput,
    )

    def clean_avoid_mixed_gender_doubles(self):
        return self.data.get('avoid_mixed_gender_doubles') in ('1', 'true', 'on')


class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ['name', 'nickname', 'gender', 'phone', 'avatar']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '真实姓名'}),
            'nickname': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '可选'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '可选'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }


class PlayerAvatarForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ['avatar']
        widgets = {
            'avatar': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar and avatar.size > 10 * 1024 * 1024:
            raise forms.ValidationError('图片大小不能超过 10MB')
        return avatar


class PlayerGenderForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ['gender']
        labels = {'gender': '性别'}
        widgets = {
            'gender': forms.Select(attrs={'class': 'form-select'}),
        }


class RegistrationForm(forms.Form):
    name = forms.CharField(
        label='姓名',
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '输入姓名报名'}),
    )
    nickname = forms.CharField(
        label='昵称',
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )


class MatchScoreForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['score_team1', 'score_team2']
        widgets = {
            'score_team1': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 30}),
            'score_team2': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 30}),
        }

    def clean(self):
        cleaned = super().clean()
        s1 = cleaned.get('score_team1')
        s2 = cleaned.get('score_team2')
        if s1 is None or s2 is None:
            return cleaned

        if s1 < 0 or s2 < 0:
            raise forms.ValidationError('比分不能为负数')

        high = max(s1, s2)
        low = min(s1, s2)

        if high > 30:
            raise forms.ValidationError('获胜方得分不能超过 30')
        if low > 29:
            raise forms.ValidationError('比分最高为 30:29')
        if s1 == s2:
            raise forms.ValidationError('比分不能相同，需分出胜负')

        return cleaned

    def save(self, commit=True):
        match = super().save(commit=False)
        match.is_completed = True
        if commit:
            match.save()
        return match
