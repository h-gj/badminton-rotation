from django.contrib import messages
from datetime import datetime, time
import json
import logging

from django.conf import settings
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from urllib.parse import urlencode

from rotation.decorators import require_club
from rotation.forms import (
    MatchScoreForm,
    PlayerAvatarForm,
    PlayerForm,
    RegistrationForm,
    SessionAddPlayersForm,
    SessionGenerateSettingsForm,
    SessionMetaForm,
    default_event_schedule,
    default_session_title,
    parse_player_names,
)
from rotation.models import Match, Player, Registration, Session
from rotation.services.round_options import pick_default_rounds, recommend_round_options
from rotation.services.club import (
    get_user_club,
    get_club_page_context,
    is_site_admin,
    user_club_scope,
    user_player_queryset,
    user_session_queryset,
)
from rotation.services.player_provision import get_or_create_club_player
from rotation.services.scheduler import generate_session_matches
from rotation.services.stats import compute_player_stats, compute_session_stats
from rotation.services.rankings import (
    build_attendance_rankings,
    build_partner_rankings,
    build_win_rate_rankings,
)
from rotation.services.wechat_import import (
    WechatImportError,
    build_import_preview,
    create_session_from_import,
    get_wechat_import_vision_providers,
    parse_wechat_screenshot,
)

logger = logging.getLogger(__name__)


def _get_club_session(request, pk):
    if is_site_admin(request.user):
        return get_object_or_404(Session, pk=pk)
    club = get_user_club(request.user)
    if not club:
        raise Http404
    return get_object_or_404(Session, pk=pk, club_id=club.pk)


def _get_viewable_session(request, pk):
    """已登录且属本俱乐部时校验归属；管理员与未登录可通过链接查看。"""
    if request.user.is_authenticated:
        if is_site_admin(request.user):
            return get_object_or_404(Session, pk=pk)
        club = get_user_club(request.user)
        if club:
            return get_object_or_404(Session, pk=pk, club_id=club.pk)
    return get_object_or_404(Session, pk=pk)


def _can_score_session(request, session):
    if not session.scores_editable:
        return False
    if not request.user.is_authenticated:
        return False
    club = get_user_club(request.user)
    if not club:
        return False
    return session.club_id == club.pk


def _login_redirect(request, next_path):
    login_url = reverse('login') + '?' + urlencode({'next': next_path})
    return login_url


def _get_club_player(request, pk):
    if is_site_admin(request.user):
        return get_object_or_404(Player, pk=pk)
    club = get_user_club(request.user)
    if not club:
        raise Http404
    return get_object_or_404(Player, pk=pk, club_id=club.pk)


def _serialize_session(session, request):
    local = timezone.localtime(session.event_date)
    return {
        'id': session.pk,
        'title': session.title,
        'status': session.status,
        'status_display': session.get_status_display(),
        'event_date_label': local.strftime('%m-%d %H:%M'),
        'location': session.location or '未填场地',
        'reg_count': session.reg_count,
        'courts': session.courts,
        'rounds': session.rounds,
        'detail_url': reverse('session_detail', args=[session.pk]),
    }


@require_club
def home(request):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        paginator = Paginator(user_session_queryset(request.user), 10)
        page_num = request.GET.get('page', 1)
        try:
            page_obj = paginator.page(page_num)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages or 1)
        return JsonResponse({
            'total': paginator.count,
            'page': page_obj.number,
            'num_pages': paginator.num_pages,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'items': [_serialize_session(s, request) for s in page_obj],
        })
    return render(request, 'rotation/home.html')


def _sync_session_title(session):
    count = session.registrations.count()
    if count > 0:
        session.title = default_session_title(count)
        round_options = recommend_round_options(count, session.courts)
        session.rounds = pick_default_rounds(session.rounds, round_options)
        session.save(update_fields=['title', 'rounds'])


def _session_meta_initial(session):
    local = timezone.localtime(session.event_date)
    return {
        'event_date': local.date(),
        'event_start_time': local.time().replace(second=0, microsecond=0),
        'event_end_time': session.event_end_time,
        'location': session.location,
    }


@require_club
def session_create(request):
    max_players = 8
    event_start, _, event_end = default_event_schedule()
    session = Session.objects.create(
        title=default_session_title(max_players),
        event_date=event_start,
        event_end_time=event_end,
        max_players=max_players,
        club=request.club,
    )
    return redirect('session_detail', pk=session.pk)


@require_club
def session_import_wechat(request):
    providers = get_wechat_import_vision_providers()
    return render(request, 'rotation/session_import_wechat.html', {
        'vision_configured': bool(providers),
        'vision_providers': [p['name'] for p in providers],
    })


@require_club
def session_import_wechat_parse(request):
    if request.method != 'POST':
        return JsonResponse({'error': '方法不允许'}, status=405)

    image = request.FILES.get('screenshot')
    if not image:
        return JsonResponse({'error': '请上传微信群聊天信息截图'}, status=400)
    if image.size > 10 * 1024 * 1024:
        return JsonResponse({'error': '图片不能超过 10MB'}, status=400)

    try:
        parsed = parse_wechat_screenshot(image.read())
        preview = build_import_preview(parsed, club=request.club)
        return JsonResponse({'ok': True, 'data': preview})
    except WechatImportError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception:
        logger.exception('wechat screenshot parse failed')
        return JsonResponse({'error': '解析失败，请换一张更清晰的截图重试'}, status=500)


@require_club
def session_import_wechat_create(request):
    if request.method != 'POST':
        return JsonResponse({'error': '方法不允许'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': '请求数据无效'}, status=400)

    try:
        session = create_session_from_import(payload, club=request.club)
        return JsonResponse({
            'ok': True,
            'redirect_url': reverse('session_detail', args=[session.pk]),
        })
    except WechatImportError as exc:
        return JsonResponse({'error': str(exc)}, status=400)


@require_club
def session_detail(request, pk):
    session = get_object_or_404(
        user_session_queryset(request.user).select_related('club'),
        pk=pk,
    )
    registrations = list(session.registrations.select_related('player'))
    match_count = session.matches.count()
    completed_count = session.matches.filter(is_completed=True).count()
    add_players_form = SessionAddPlayersForm(session)
    meta_initial = _session_meta_initial(session)
    meta_form = SessionMetaForm(initial=meta_initial)
    round_options = recommend_round_options(session.reg_count, session.courts)
    default_rounds = pick_default_rounds(session.rounds, round_options)
    return render(request, 'rotation/session_detail.html', {
        'session': session,
        'registrations': registrations,
        'match_count': match_count,
        'completed_count': completed_count,
        'add_players_form': add_players_form,
        'meta_form': meta_form,
        'previous_players': add_players_form.fields['players'].queryset,
        'meta_initial': meta_initial,
        'round_options': round_options,
        'default_rounds': default_rounds,
    })


@require_club
def session_update_meta(request, pk):
    session = _get_club_session(request, pk)
    if request.method != 'POST':
        return redirect('session_detail', pk=pk)

    form = SessionMetaForm(request.POST)
    if form.is_valid():
        event_date = form.cleaned_data['event_date']
        start_time = form.cleaned_data['event_start_time']
        session.event_date = timezone.make_aware(datetime.combine(event_date, start_time))
        session.event_end_time = form.cleaned_data['event_end_time']
        session.location = form.cleaned_data.get('location', '')
        session.save(update_fields=['event_date', 'event_end_time', 'location'])
        messages.success(request, '活动信息已更新')
    else:
        messages.error(request, '请检查时间和地点格式')
    return redirect('session_detail', pk=pk)


@require_club
def session_add_players(request, pk):
    session = _get_club_session(request, pk)
    if session.status != Session.Status.OPEN:
        messages.error(request, '该活动已停止报名')
        return redirect('session_detail', pk=pk)
    if request.method != 'POST':
        return redirect('session_detail', pk=pk)

    form = SessionAddPlayersForm(session, request.POST)
    if not form.is_valid():
        messages.error(request, '添加报名失败，请重试')
        return redirect('session_detail', pk=pk)

    selected_players = list(form.cleaned_data.get('players') or [])
    seen_ids = {player.pk for player in selected_players}
    registered_ids = set(session.registrations.values_list('player_id', flat=True))
    new_accounts = []

    for name in parse_player_names(form.cleaned_data.get('players_manual', '')):
        player, created, login_name = get_or_create_club_player(request.club, name)
        if created and login_name:
            new_accounts.append(f'{player.display_name}（{login_name}）')
        if player.pk not in seen_ids and player.pk not in registered_ids:
            selected_players.append(player)
            seen_ids.add(player.pk)

    added = 0
    skipped = 0
    current_count = session.registrations.count()
    for player in selected_players:
        if player.pk in registered_ids:
            skipped += 1
            continue
        if current_count >= session.max_players:
            messages.warning(request, f'已达人数上限 {session.max_players} 人，部分人员未添加')
            break
        _, created = Registration.objects.get_or_create(session=session, player=player)
        if created:
            added += 1
            current_count += 1
            registered_ids.add(player.pk)

    if added:
        _sync_session_title(session)
        messages.success(request, f'已添加 {added} 名报名人员')
    if new_accounts:
        messages.info(
            request,
            f'新登录账号（默认密码 666666）：{"；".join(new_accounts)}',
        )
    elif skipped and not added:
        messages.warning(request, '所选人员均已在报名名单中')
    elif not selected_players:
        messages.warning(request, '请选择或输入要添加的人员')

    return redirect('session_detail', pk=pk)


@require_club
def session_register(request, pk):
    session = _get_club_session(request, pk)
    if session.status != Session.Status.OPEN:
        messages.error(request, '该活动已停止报名')
        return redirect('session_detail', pk=pk)

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            if session.player_count >= session.max_players:
                messages.error(request, '报名人数已满')
            else:
                name = form.cleaned_data['name'].strip()
                nickname = form.cleaned_data.get('nickname', '').strip()
                player, player_created, login_name = get_or_create_club_player(
                    request.club, name, nickname=nickname,
                )
                _, reg_created = Registration.objects.get_or_create(session=session, player=player)
                if reg_created:
                    _sync_session_title(session)
                    msg = f'{player.display_name} 报名成功'
                    if login_name:
                        msg += f'，登录用户名 {login_name}，默认密码 666666'
                    messages.success(request, msg)
                else:
                    messages.warning(request, f'{player.display_name} 已经报过名了')
                return redirect('session_detail', pk=pk)
    else:
        form = RegistrationForm()

    return render(request, 'rotation/register.html', {'session': session, 'form': form})


@require_club
def session_generate(request, pk):
    session = _get_club_session(request, pk)
    if request.method != 'POST':
        return redirect('session_detail', pk=pk)

    if not session.can_generate:
        messages.error(request, '当前无法生成对阵（需至少 4 人，且人数与场地数能组成完整双打）')
        return redirect('session_detail', pk=pk)

    form = SessionGenerateSettingsForm(request.POST)
    if not form.is_valid():
        messages.error(request, '设置无效，请重试')
        return redirect('session_detail', pk=pk)

    player_count = session.registrations.count()
    allowed_rounds = recommend_round_options(player_count, session.courts)
    if not allowed_rounds:
        messages.error(request, '当前人数无法推荐局数，请检查报名人数')
        return redirect('session_detail', pk=pk)

    rounds = form.cleaned_data['rounds']
    if rounds not in allowed_rounds:
        rounds = pick_default_rounds(rounds, allowed_rounds)

    session.rounds = rounds
    session.avoid_mixed_gender_doubles = form.cleaned_data['avoid_mixed_gender_doubles']
    session.save(update_fields=['rounds', 'avoid_mixed_gender_doubles'])

    try:
        count = generate_session_matches(session)
        messages.success(request, f'已生成 {count} 场对阵')
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect('session_matches', pk=pk)


def _print_match_schedule(session, flat_matches):
    print(f'\n=== 对阵信息：{session.title}（共 {len(flat_matches)} 场 / {session.rounds} 局）===', flush=True)
    current_round = None
    for m in flat_matches:
        if m.round_number != current_round:
            current_round = m.round_number
            print(f'--- 第 {current_round} 局 ---', flush=True)
        team1 = f'{m.team1_player1.display_name}/{m.team1_player2.display_name}'
        team2 = f'{m.team2_player1.display_name}/{m.team2_player2.display_name}'
        if m.is_completed:
            score = f'{m.score_team1}:{m.score_team2}'
            print(f'  {m.court_number}号场  {team1}  vs  {team2}  [{score}]', flush=True)
        else:
            print(f'  {m.court_number}号场  {team1}  vs  {team2}', flush=True)
    print('', flush=True)


@ensure_csrf_cookie
def session_matches(request, pk):
    session = _get_viewable_session(request, pk)
    can_score = _can_score_session(request, session)
    matches = session.matches.select_related(
        'team1_player1', 'team1_player2', 'team2_player1', 'team2_player2', 'scored_by',
    )
    rounds = {}
    flat_matches = []
    for i, m in enumerate(matches, start=1):
        m.match_number = i
        flat_matches.append(m)
        rounds.setdefault(m.round_number, []).append(m)

    round_list = sorted(rounds.items())
    match_count = len(flat_matches)
    completed_count = sum(1 for m in flat_matches if m.is_completed)
    if flat_matches:
        _print_match_schedule(session, flat_matches)
    return render(request, 'rotation/matches.html', {
        'session': session,
        'round_list': round_list,
        'flat_matches': flat_matches,
        'match_count': match_count,
        'completed_count': completed_count,
        'can_score': can_score,
    })


def _update_session_status(session):
    if session.status == Session.Status.SCHEDULED:
        session.status = Session.Status.IN_PROGRESS
        session.save(update_fields=['status'])
    total = session.matches.count()
    done = session.matches.filter(is_completed=True).count()
    if total and done == total:
        session.status = Session.Status.COMPLETED
        session.save(update_fields=['status'])


def _match_score_json(match, session):
    completed_count = session.matches.filter(is_completed=True).count()
    match_count = session.matches.count()
    scored_at = timezone.localtime(match.scored_at) if match.scored_at else None
    return {
        'ok': True,
        'score_team1': match.score_team1,
        'score_team2': match.score_team2,
        'score_diff': match.score_diff,
        'match_id': match.pk,
        'completed_count': completed_count,
        'match_count': match_count,
        'scored_by_display': match.scored_by_display,
        'scored_at_label': scored_at.strftime('%m-%d %H:%M') if scored_at else '',
    }


@ensure_csrf_cookie
def match_score(request, pk):
    match = get_object_or_404(Match.objects.select_related('session'), pk=pk)
    session = match.session
    session_pk = session.pk
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method != 'POST':
        if is_ajax:
            return JsonResponse({'ok': False, 'errors': ['无效请求']}, status=405)
        return redirect('session_matches', pk=session_pk)

    if not request.user.is_authenticated:
        login_url = _login_redirect(request, reverse('session_matches', args=[session_pk]))
        if is_ajax:
            return JsonResponse({'ok': False, 'login_url': login_url}, status=401)
        return redirect(login_url)

    club = get_user_club(request.user)
    if not club:
        if is_ajax:
            return JsonResponse({'ok': False, 'errors': ['请先创建或加入俱乐部']}, status=403)
        messages.info(request, '请先创建或加入俱乐部，才能录入比分')
        return redirect('club_home')

    if session.club_id != club.pk:
        if is_ajax:
            return JsonResponse({'ok': False, 'errors': ['无权修改此活动比分']}, status=403)
        messages.error(request, '无权修改此活动比分')
        return redirect('session_matches', pk=session_pk)

    if not session.scores_editable:
        locked_msg = '比赛已结束，不能再修改比分'
        if is_ajax:
            return JsonResponse({'ok': False, 'errors': [locked_msg]}, status=403)
        messages.error(request, locked_msg)
        return redirect('session_matches', pk=session_pk)

    form = MatchScoreForm(request.POST, instance=match)
    if form.is_valid():
        match = form.save(commit=False)
        match.scored_by = request.user
        match.scored_at = timezone.now()
        match.save()
        _update_session_status(match.session)
        if is_ajax:
            return JsonResponse(_match_score_json(match, match.session))
    else:
        errors = []
        for field_errors in form.errors.values():
            errors.extend(field_errors)
        if is_ajax:
            return JsonResponse({'ok': False, 'errors': errors or ['比分无效']}, status=400)
        messages.error(request, '；'.join(errors) if errors else '比分无效')
    return redirect('session_matches', pk=session_pk)


@require_club
def session_leaderboard(request, pk):
    """比赛成绩页，支持 ?sort=wins|points 排序。"""
    session = _get_club_session(request, pk)
    sort_by = request.GET.get('sort', 'wins')
    if sort_by not in ('wins', 'points'):
        sort_by = 'wins'
    leaderboard = compute_session_stats(session, sort_by=sort_by)
    match_count = session.matches.count()
    completed_count = session.matches.filter(is_completed=True).count()
    return render(request, 'rotation/leaderboard.html', {
        'session': session,
        'leaderboard': leaderboard,
        'sort_by': sort_by,
        'match_count': match_count,
        'completed_count': completed_count,
    })


def _player_list_queryset(user, q=''):
    return user_player_queryset(user, q)


def _serialize_player(player, request):
    return {
        'id': player.pk,
        'name': player.name,
        'nickname': player.nickname,
        'display_name': player.display_name,
        'session_count': getattr(player, 'session_count', 0),
        'avatar_url': player.avatar.url if player.avatar else '',
        'detail_url': reverse('player_detail', args=[player.pk]),
    }


RANKINGS_TABS = ('win_rate', 'attendance', 'partner')


def _paginate_rankings(rows, page_num, per_page=10):
    paginator = Paginator(rows, per_page)
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)
    return paginator, page_obj


@require_club
def rankings(request):
    tab = request.GET.get('tab', 'win_rate')
    if tab not in RANKINGS_TABS:
        tab = 'win_rate'

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        q = request.GET.get('q', '').strip()
        page_num = request.GET.get('page', 1)
        total_sessions = None
        club = user_club_scope(request.user)

        if tab == 'win_rate':
            rows = build_win_rate_rankings(q, club=club)
        elif tab == 'attendance':
            rows, total_sessions = build_attendance_rankings(q, club=club)
        else:
            rows = build_partner_rankings(q, club=club)

        paginator, page_obj = _paginate_rankings(rows, page_num)
        base_rank = (page_obj.number - 1) * paginator.per_page
        items = []

        for i, row in enumerate(page_obj.object_list):
            rank = base_rank + i + 1
            if tab == 'partner':
                items.append({
                    'rank': rank,
                    'player1': _serialize_player(row['player1'], request),
                    'player2': _serialize_player(row['player2'], request),
                    'wins': row['wins'],
                    'losses': row['losses'],
                    'matches': row['matches'],
                    'win_rate': row['win_rate'],
                })
            else:
                p = row['player']
                item = {
                    'rank': rank,
                    'id': p.pk,
                    'name': p.name,
                    'nickname': p.nickname,
                    'display_name': p.display_name,
                    'avatar_url': p.avatar.url if p.avatar else '',
                    'detail_url': reverse('player_detail', args=[p.pk]),
                }
                if tab == 'win_rate':
                    item.update({
                        'wins': row['wins'],
                        'losses': row['losses'],
                        'matches': row['matches'],
                        'win_rate': row['win_rate'],
                    })
                else:
                    item.update({
                        'sessions_attended': row['sessions_attended'],
                        'total_sessions': total_sessions,
                        'attendance_rate': row['attendance_rate'],
                    })
                items.append(item)

        payload = {
            'tab': tab,
            'total': paginator.count,
            'page': page_obj.number,
            'num_pages': paginator.num_pages,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'items': items,
        }
        if tab == 'attendance':
            payload['total_sessions'] = total_sessions
        return JsonResponse(payload)

    return render(request, 'rotation/rankings.html', {
        'tab': tab,
        'club_tab': 'rankings',
        **get_club_page_context(request.user),
    })


@require_club
def player_list(request):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        q = request.GET.get('q', '').strip()
        paginator = Paginator(_player_list_queryset(request.user, q), 10)
        page_num = request.GET.get('page', 1)
        try:
            page_obj = paginator.page(page_num)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages or 1)
        return JsonResponse({
            'total': paginator.count,
            'page': page_obj.number,
            'num_pages': paginator.num_pages,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
            'players': [_serialize_player(p, request) for p in page_obj],
        })
    return render(request, 'rotation/player_list.html', {
        'club_tab': 'players',
        **get_club_page_context(request.user),
    })


@require_club
def player_detail(request, pk):
    player = _get_club_player(request, pk)
    stats = compute_player_stats(player)
    return render(request, 'rotation/player_detail.html', {'player': player, 'stats': stats})


@require_club
def player_create(request):
    if request.method == 'POST':
        form = PlayerForm(request.POST, request.FILES)
        if form.is_valid():
            player = form.save(commit=False)
            player.club = request.club
            player.save()
            messages.success(request, f'球员 {player.display_name} 已添加')
            return redirect('player_list')
    else:
        form = PlayerForm()
    return render(request, 'rotation/player_form.html', {'form': form, 'title': '添加球员'})


@require_club
def player_update_avatar(request, pk):
    player = _get_club_player(request, pk)
    next_url = request.POST.get('next') or request.GET.get('next') or reverse('player_detail', kwargs={'pk': pk})
    if request.method != 'POST':
        return redirect(next_url)

    if request.POST.get('clear_avatar'):
        if player.avatar:
            player.avatar.delete(save=False)
        player.avatar = None
        player.save(update_fields=['avatar'])
        messages.success(request, f'已清除 {player.display_name} 的头像')
        return redirect(next_url)

    if 'avatar' not in request.FILES:
        messages.error(request, '请选择要上传的图片')
        return redirect(next_url)

    form = PlayerAvatarForm(request.POST, request.FILES, instance=player)
    if form.is_valid():
        form.save()
        messages.success(request, f'已更新 {player.display_name} 的头像')
    else:
        errors = []
        for field_errors in form.errors.values():
            errors.extend(field_errors)
        messages.error(request, '；'.join(errors) if errors else '头像上传失败')
    return redirect(next_url)
