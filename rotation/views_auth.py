from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from rotation.decorators import login_required_view
from rotation.forms import PlayerAvatarForm, PlayerGenderForm
from rotation.forms_auth import ClubForm, ClubJoinForm, LoginForm, RegisterForm
from rotation.models import Club, ClubMembership, Player
from rotation.services.club import get_user_club, get_club_page_context, is_site_admin, user_has_club, user_owns_club
from rotation.services.stats import compute_player_stats


def _safe_next_url(request):
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return None


def _stash_post_club_next(request):
    next_url = _safe_next_url(request)
    if next_url:
        request.session['post_club_next'] = next_url


def _redirect_after_club_action(request):
    next_url = request.session.pop('post_club_next', None)
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect('club_home')


def _redirect_after_login(request, user):
    if not user_has_club(user) and not is_site_admin(user):
        _stash_post_club_next(request)
        messages.info(request, '请先创建或加入俱乐部')
        return redirect('club_home')
    next_url = _safe_next_url(request)
    if next_url:
        return redirect(next_url)
    return redirect('home')


def register(request):
    if request.user.is_authenticated:
        return _redirect_after_login(request, request.user)

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, '注册成功，请创建或加入俱乐部')
            return redirect('club_home')
    else:
        form = RegisterForm()

    return render(request, 'rotation/auth_register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return _redirect_after_login(request, request.user)

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, '欢迎回来')
            return _redirect_after_login(request, form.get_user())
    else:
        form = LoginForm()

    return render(request, 'rotation/auth_login.html', {
        'form': form,
        'next_url': request.GET.get('next', ''),
    })


def logout_view(request):
    logout(request)
    messages.info(request, '已退出登录')
    return redirect('login')


def _get_or_create_profile_player(user):
    player = Player.objects.filter(user=user).select_related('club').first()
    if player:
        return player
    club = get_user_club(user)
    if not club:
        return None
    return Player.objects.create(club=club, name=user.username, user=user)


@login_required_view
def profile(request):
    user = request.user
    club = get_user_club(user)
    player = Player.objects.filter(user=user).select_related('club').first()
    membership = ClubMembership.objects.filter(user=user).select_related('club').first()
    owned_club = Club.objects.filter(owner=user).first()

    if is_site_admin(user):
        role_label = '站点管理员'
        role_class = 'admin'
    elif owned_club:
        role_label = '俱乐部创建者'
        role_class = 'owner'
    elif membership:
        role_label = '俱乐部成员'
        role_class = 'member'
    else:
        role_label = '未加入俱乐部'
        role_class = ''

    stats = compute_player_stats(player) if player else None
    display_name = player.display_name if player else user.username
    can_edit_profile = bool(player or club)

    return render(request, 'rotation/profile.html', {
        'club': club,
        'player': player,
        'stats': stats,
        'display_name': display_name,
        'role_label': role_label,
        'role_class': role_class,
        'membership': membership,
        'owned_club': owned_club,
        'is_admin': is_site_admin(user),
        'can_edit_avatar': can_edit_profile,
        'can_edit_profile': can_edit_profile,
        'gender_form': PlayerGenderForm(instance=player) if player else PlayerGenderForm(),
    })


@login_required_view
def profile_update_avatar(request):
    if request.method != 'POST':
        return redirect('profile')

    player = _get_or_create_profile_player(request.user)
    if not player:
        messages.error(request, '请先创建或加入俱乐部后再设置头像')
        return redirect('profile')

    if request.POST.get('clear_avatar'):
        if player.avatar:
            player.avatar.delete(save=False)
        player.avatar = None
        player.save(update_fields=['avatar'])
        messages.success(request, '头像已清除')
        return redirect('profile')

    if 'avatar' not in request.FILES:
        messages.error(request, '请选择要上传的图片')
        return redirect('profile')

    form = PlayerAvatarForm(request.POST, request.FILES, instance=player)
    if form.is_valid():
        form.save()
        messages.success(request, '头像已更新')
    else:
        errors = []
        for field_errors in form.errors.values():
            errors.extend(field_errors)
        messages.error(request, '；'.join(errors) if errors else '头像上传失败')
    return redirect('profile')


@login_required_view
def profile_update_gender(request):
    if request.method != 'POST':
        return redirect('profile')

    player = _get_or_create_profile_player(request.user)
    if not player:
        messages.error(request, '请先创建或加入俱乐部后再设置性别')
        return redirect('profile')

    form = PlayerGenderForm(request.POST, instance=player)
    if form.is_valid():
        form.save()
        label = player.get_gender_display() or '未设置'
        messages.success(request, f'性别已更新为{label}')
    else:
        errors = []
        for field_errors in form.errors.values():
            errors.extend(field_errors)
        messages.error(request, '；'.join(errors) if errors else '保存失败')
    return redirect('profile')


@login_required_view
def club_home(request):
    club = get_user_club(request.user)
    admin = is_site_admin(request.user)
    if not club and not admin:
        return render(request, 'rotation/club_home.html', {'needs_setup': True})

    return render(request, 'rotation/club_home.html', {
        'club_tab': 'overview',
        **get_club_page_context(request.user),
    })


@login_required_view
def club_setup(request):
    if user_has_club(request.user) or is_site_admin(request.user):
        return redirect('club_home')

    return render(request, 'rotation/club_setup.html', {
        'next_url': request.GET.get('next', ''),
    })


@login_required_view
def club_create(request):
    if user_has_club(request.user):
        messages.info(request, f'你已在俱乐部「{get_user_club(request.user).name}」中')
        return redirect('club_home')

    if request.method == 'POST':
        form = ClubForm(request.POST)
        if form.is_valid():
            club = form.save(commit=False)
            club.owner = request.user
            club.save()
            messages.success(request, f'俱乐部「{club.name}」创建成功')
            return _redirect_after_club_action(request)
    else:
        form = ClubForm()

    return render(request, 'rotation/club_create.html', {'form': form})


@login_required_view
def club_join(request):
    if user_has_club(request.user):
        messages.info(request, f'你已在俱乐部「{get_user_club(request.user).name}」中')
        return redirect('club_home')

    if user_owns_club(request.user):
        messages.error(request, '你已创建俱乐部，无法再加入其他俱乐部')
        return redirect('club_home')

    if request.method == 'POST':
        form = ClubJoinForm(user=request.user, data=request.POST)
        if form.is_valid():
            club = form.cleaned_data['club']
            ClubMembership.objects.create(user=request.user, club=club)
            messages.success(request, f'已加入俱乐部「{club.name}」')
            return _redirect_after_club_action(request)
    else:
        form = ClubJoinForm(user=request.user)

    clubs_available = form.fields['club'].queryset.exists()
    return render(request, 'rotation/club_join.html', {
        'form': form,
        'clubs_available': clubs_available,
    })
