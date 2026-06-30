from django import forms
from django.utils import timezone

from rotation.models import Match, Player, Session


def parse_player_names(text):
    if not text or not text.strip():
        return []
    seen = set()
    names = []
    for part in text.replace(',', '\n').split('\n'):
        name = part.strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


class SessionCreateForm(forms.Form):
    title = forms.CharField(
        label='活动名称',
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '例如：周六夜场'}),
    )
    location = forms.CharField(
        label='场地号',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '可选'}),
    )
    event_datetime = forms.DateTimeField(
        label='活动时间',
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S'],
        widget=forms.DateTimeInput(
            attrs={'class': 'form-control', 'type': 'datetime-local'},
            format='%Y-%m-%dT%H:%M',
        ),
    )
    players = forms.CharField(
        label='报名人员',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': '多个人员换行输入或者用英文逗号分割',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            now = timezone.localtime()
            self.initial.setdefault('event_datetime', now.strftime('%Y-%m-%dT%H:%M'))


class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ['name', 'nickname', 'phone']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '真实姓名'}),
            'nickname': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '可选'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '可选'}),
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
