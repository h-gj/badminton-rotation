from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from rotation.models import Club, Player


class ManageClubForm(forms.ModelForm):
    class Meta:
        model = Club
        fields = ['name', 'description']
        labels = {
            'name': '俱乐部名称',
            'description': '简介',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ManageClubCreateForm(ManageClubForm):
    owner = forms.ModelChoiceField(
        label='创建者账号',
        queryset=get_user_model().objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='须为尚未拥有或加入俱乐部的用户',
    )

    class Meta(ManageClubForm.Meta):
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        self.fields['owner'].queryset = (
            User.objects.filter(owned_club__isnull=True, club_memberships__isnull=True)
            .order_by('username')
        )


class ManagePlayerCreateForm(forms.Form):
    name = forms.CharField(
        label='姓名',
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '真实姓名'}),
    )
    nickname = forms.CharField(
        label='昵称',
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '可选'}),
    )
    gender = forms.ChoiceField(
        label='性别',
        choices=Player.Gender.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    phone = forms.CharField(
        label='手机号',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '可选'}),
    )
    club = forms.ModelChoiceField(
        label='所属俱乐部',
        queryset=Club.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    create_account = forms.BooleanField(
        label='同时创建登录账号',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='用户名格式：邀请码_姓名拼音，默认密码 666666',
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        from rotation.services.club import is_site_admin, manage_club_queryset

        clubs = manage_club_queryset(user)
        self.fields['club'].queryset = clubs
        if clubs.count() == 1:
            self.fields['club'].initial = clubs.first().pk
        if not is_site_admin(user):
            self.fields['club'].widget = forms.HiddenInput()


class ManagePlayerEditForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ['name', 'nickname', 'gender', 'phone']
        labels = {
            'name': '姓名',
            'nickname': '昵称',
            'gender': '性别',
            'phone': '手机号',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'nickname': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ManagePlayerPasswordForm(forms.Form):
    password1 = forms.CharField(
        label='新密码',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='确认新密码',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('两次输入的密码不一致')
        if p1:
            validate_password(p1)
        return cleaned
