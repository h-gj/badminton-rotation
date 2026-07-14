from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from rotation.decorators import require_manager
from rotation.forms_manage import (
    ManageClubCreateForm,
    ManageClubForm,
    ManagePlayerCreateForm,
    ManagePlayerEditForm,
    ManagePlayerPasswordForm,
)
from rotation.models import Club, Player
from rotation.services.club import (
    is_site_admin,
    manage_club_queryset,
    manage_player_queryset,
    user_can_manage_club,
    user_can_manage_player,
)
from rotation.services.player_provision import create_club_player, provision_player_login


def _manage_context(user, manage_tab):
    clubs = manage_club_queryset(user)
    return {
        'manage_tab': manage_tab,
        'is_manage_admin': is_site_admin(user),
        'manage_clubs': clubs,
    }


@require_manager
def manage_dashboard(request):
    user = request.user
    clubs = manage_club_queryset(user)
    players = manage_player_queryset(user)
    stats = {
        'club_count': clubs.count(),
        'player_count': players.count(),
        'account_count': players.filter(user__isnull=False).count(),
    }
    return render(request, 'rotation/manage/dashboard.html', {
        **_manage_context(user, 'dashboard'),
        'stats': stats,
    })


@require_manager
def manage_club_list(request):
    user = request.user
    clubs = manage_club_queryset(user)
    return render(request, 'rotation/manage/club_list.html', {
        **_manage_context(user, 'clubs'),
        'clubs': clubs,
    })


@require_manager
def manage_club_create(request):
    if not is_site_admin(request.user):
        messages.error(request, '仅站点管理员可创建俱乐部')
        return redirect('manage_club_list')

    if request.method == 'POST':
        form = ManageClubCreateForm(request.POST)
        if form.is_valid():
            club = form.save(commit=False)
            club.owner = form.cleaned_data['owner']
            club.save()
            messages.success(request, f'俱乐部「{club.name}」已创建')
            return redirect('manage_club_edit', pk=club.pk)
    else:
        form = ManageClubCreateForm()

    return render(request, 'rotation/manage/club_form.html', {
        **_manage_context(request.user, 'clubs'),
        'form': form,
        'title': '新建俱乐部',
    })


@require_manager
def manage_club_edit(request, pk):
    club = get_object_or_404(Club.objects.select_related('owner'), pk=pk)
    if not user_can_manage_club(request.user, club):
        messages.error(request, '无权编辑该俱乐部')
        return redirect('manage_club_list')

    if request.method == 'POST':
        form = ManageClubForm(request.POST, instance=club)
        if form.is_valid():
            form.save()
            messages.success(request, f'俱乐部「{club.name}」已更新')
            return redirect('manage_club_list')
    else:
        form = ManageClubForm(instance=club)

    member_count = club.memberships.count()
    if not club.memberships.filter(user_id=club.owner_id).exists():
        member_count += 1

    return render(request, 'rotation/manage/club_form.html', {
        **_manage_context(request.user, 'clubs'),
        'form': form,
        'title': '编辑俱乐部',
        'club': club,
        'member_count': member_count,
        'player_count': club.players.count(),
    })


@require_manager
def manage_player_list(request):
    user = request.user
    q = request.GET.get('q', '').strip()
    club_id = request.GET.get('club')
    if club_id and club_id.isdigit():
        club_id = int(club_id)
    else:
        club_id = None

    if club_id and not is_site_admin(user):
        owned = Club.objects.filter(owner=user).first()
        if not owned or owned.pk != club_id:
            club_id = owned.pk if owned else None
    elif club_id and is_site_admin(user):
        if not Club.objects.filter(pk=club_id).exists():
            club_id = None

    qs = manage_player_queryset(user, club_id=club_id, q=q)
    paginator = Paginator(qs, 15)
    page_num = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    clubs = manage_club_queryset(user)
    return render(request, 'rotation/manage/player_list.html', {
        **_manage_context(user, 'players'),
        'page_obj': page_obj,
        'q': q,
        'club_id': club_id,
        'filter_clubs': clubs if is_site_admin(user) else None,
    })


@require_manager
def manage_player_create(request):
    user = request.user
    if request.method == 'POST':
        form = ManagePlayerCreateForm(user, request.POST)
        if form.is_valid():
            club = form.cleaned_data['club']
            if not user_can_manage_club(user, club):
                messages.error(request, '无权在该俱乐部添加球员')
                return redirect('manage_player_list')
            try:
                player, login_username = create_club_player(
                    club=club,
                    name=form.cleaned_data['name'],
                    nickname=form.cleaned_data.get('nickname', ''),
                    gender=form.cleaned_data.get('gender', ''),
                    phone=form.cleaned_data.get('phone', ''),
                    create_account=form.cleaned_data.get('create_account', False),
                )
            except ValueError as exc:
                form.add_error('name', str(exc))
            else:
                if login_username:
                    messages.success(
                        request,
                        f'球员 {player.display_name} 已添加，登录用户名：{login_username}，默认密码 666666',
                    )
                else:
                    messages.success(request, f'球员 {player.display_name} 已添加')
                return redirect('manage_player_list')
    else:
        form = ManagePlayerCreateForm(user)

    return render(request, 'rotation/manage/player_form.html', {
        **_manage_context(user, 'players'),
        'form': form,
        'title': '新增球员',
    })


@require_manager
def manage_player_edit(request, pk):
    player = get_object_or_404(
        Player.objects.select_related('club', 'user'),
        pk=pk,
    )
    if not user_can_manage_player(request.user, player):
        messages.error(request, '无权编辑该球员')
        return redirect('manage_player_list')

    if request.method == 'POST':
        form = ManagePlayerEditForm(request.POST, instance=player)
        if form.is_valid():
            form.save()
            messages.success(request, f'球员 {player.display_name} 已更新')
            return redirect('manage_player_list')
    else:
        form = ManagePlayerEditForm(instance=player)

    return render(request, 'rotation/manage/player_form.html', {
        **_manage_context(request.user, 'players'),
        'form': form,
        'title': '编辑球员',
        'player': player,
    })


@require_manager
def manage_player_enable_account(request, pk):
    player = get_object_or_404(
        Player.objects.select_related('club', 'user'),
        pk=pk,
    )
    if not user_can_manage_player(request.user, player):
        messages.error(request, '无权操作该球员')
        return redirect('manage_player_list')

    if request.method != 'POST':
        return redirect('manage_player_list')

    try:
        login_username = provision_player_login(player)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f'已为 {player.display_name} 开通登录账号：{login_username}，默认密码 666666',
        )

    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect('manage_player_list')


@require_manager
def manage_player_password(request, pk):
    player = get_object_or_404(
        Player.objects.select_related('club', 'user'),
        pk=pk,
    )
    if not user_can_manage_player(request.user, player):
        messages.error(request, '无权修改该球员密码')
        return redirect('manage_player_list')

    if not player.user_id:
        messages.error(request, '该球员尚未绑定登录账号，无法修改密码')
        return redirect('manage_player_edit', pk=player.pk)

    if request.method == 'POST':
        form = ManagePlayerPasswordForm(request.POST)
        if form.is_valid():
            player.user.set_password(form.cleaned_data['password1'])
            player.user.save(update_fields=['password'])
            messages.success(request, f'已更新 {player.display_name} 的登录密码')
            return redirect('manage_player_list')
    else:
        form = ManagePlayerPasswordForm()

    return render(request, 'rotation/manage/player_password.html', {
        **_manage_context(request.user, 'players'),
        'form': form,
        'player': player,
    })
