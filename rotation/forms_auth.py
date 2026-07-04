from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from rotation.models import Club


class RegisterForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        labels = {
            'username': '用户名',
            'password1': '密码',
            'password2': '确认密码',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = '用户名'
        self.fields['password'].label = '密码'
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class ClubJoinForm(forms.Form):
    club = forms.ModelChoiceField(
        label='选择俱乐部',
        queryset=Club.objects.none(),
        empty_label='请选择俱乐部',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['club'].queryset = Club.objects.exclude(owner=user).order_by('name')

    def clean_club(self):
        club = self.cleaned_data['club']
        if club.owner_id == self.user.id:
            raise forms.ValidationError('你是该俱乐部创建者，无需加入')
        return club


class ClubForm(forms.ModelForm):
    class Meta:
        model = Club
        fields = ['name', 'description']
        labels = {
            'name': '俱乐部名称',
            'description': '简介（选填）',
        }
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例如：荣达羽球俱乐部',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '简单介绍一下你们的固定活动…',
            }),
        }
