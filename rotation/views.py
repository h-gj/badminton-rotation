from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from rotation.forms import MatchScoreForm, PlayerForm, RegistrationForm, SessionCreateForm, parse_player_names
from rotation.models import Match, Player, Registration, Session
from rotation.services.scheduler import generate_session_matches
from rotation.services.stats import compute_player_stats, compute_session_stats


def home(request):
    sessions = Session.objects.annotate(
        reg_count=Count('registrations')
    ).order_by('-event_date')[:20]
    return render(request, 'rotation/home.html', {'sessions': sessions})


def session_create(request):
    if request.method == 'POST':
        form = SessionCreateForm(request.POST)
        if form.is_valid():
            player_names = parse_player_names(form.cleaned_data.get('players', ''))
            session = Session.objects.create(
                title=form.cleaned_data['title'],
                event_date=form.cleaned_data['event_datetime'],
                location=form.cleaned_data.get('location', ''),
                max_players=max(16, len(player_names)) if player_names else 16,
            )
            for name in player_names:
                player, _ = Player.objects.get_or_create(name=name)
                Registration.objects.get_or_create(session=session, player=player)
            msg = f'活动「{session.title}」已创建'
            if player_names:
                msg += f'，已添加 {len(player_names)} 名报名人员'
            messages.success(request, msg)
            return redirect('session_detail', pk=session.pk)
    else:
        form = SessionCreateForm()
    return render(request, 'rotation/session_form.html', {'form': form, 'title': '创建活动'})


def session_detail(request, pk):
    session = get_object_or_404(
        Session.objects.annotate(reg_count=Count('registrations')), pk=pk
    )
    registrations = session.registrations.select_related('player')
    match_count = session.matches.count()
    completed_count = session.matches.filter(is_completed=True).count()
    return render(request, 'rotation/session_detail.html', {
        'session': session,
        'registrations': registrations,
        'match_count': match_count,
        'completed_count': completed_count,
    })


def session_register(request, pk):
    session = get_object_or_404(Session, pk=pk)
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
                player, _ = Player.objects.get_or_create(
                    name=name,
                    defaults={'nickname': nickname},
                )
                if nickname and not player.nickname:
                    player.nickname = nickname
                    player.save(update_fields=['nickname'])
                _, created = Registration.objects.get_or_create(session=session, player=player)
                if created:
                    messages.success(request, f'{player.display_name} 报名成功')
                else:
                    messages.warning(request, f'{player.display_name} 已经报过名了')
                return redirect('session_detail', pk=pk)
    else:
        form = RegistrationForm()

    return render(request, 'rotation/register.html', {'session': session, 'form': form})


def session_generate(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method != 'POST':
        return redirect('session_detail', pk=pk)

    if not session.can_generate:
        messages.error(request, '当前无法生成对阵（需至少 4 人，且人数与场地数能组成完整双打）')
        return redirect('session_detail', pk=pk)

    try:
        count = generate_session_matches(session)
        messages.success(request, f'已生成 {count} 场对阵')
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect('session_matches', pk=pk)


def session_matches(request, pk):
    session = get_object_or_404(Session, pk=pk)
    matches = session.matches.select_related(
        'team1_player1', 'team1_player2', 'team2_player1', 'team2_player2',
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
    return render(request, 'rotation/matches.html', {
        'session': session,
        'round_list': round_list,
        'flat_matches': flat_matches,
        'match_count': match_count,
        'completed_count': completed_count,
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


def match_score(request, pk):
    match = get_object_or_404(Match.objects.select_related('session'), pk=pk)
    session_pk = match.session.pk
    if request.method != 'POST':
        return redirect('session_matches', pk=session_pk)

    form = MatchScoreForm(request.POST, instance=match)
    if form.is_valid():
        form.save()
        _update_session_status(match.session)
        messages.success(
            request,
            f'第 {match.round_number} 轮 场地 {match.court_number} 比分已保存',
        )
    else:
        errors = []
        for field_errors in form.errors.values():
            errors.extend(field_errors)
        messages.error(request, '；'.join(errors) if errors else '比分无效')
    return redirect('session_matches', pk=session_pk)


def session_leaderboard(request, pk):
    session = get_object_or_404(Session, pk=pk)
    leaderboard = compute_session_stats(session)
    match_count = session.matches.count()
    completed_count = session.matches.filter(is_completed=True).count()
    return render(request, 'rotation/leaderboard.html', {
        'session': session,
        'leaderboard': leaderboard,
        'match_count': match_count,
        'completed_count': completed_count,
    })


def player_list(request):
    players = Player.objects.annotate(session_count=Count('registrations')).order_by('name')
    return render(request, 'rotation/player_list.html', {'players': players})


def player_detail(request, pk):
    player = get_object_or_404(Player, pk=pk)
    stats = compute_player_stats(player)
    return render(request, 'rotation/player_detail.html', {'player': player, 'stats': stats})


def player_create(request):
    if request.method == 'POST':
        form = PlayerForm(request.POST)
        if form.is_valid():
            player = form.save()
            messages.success(request, f'球员 {player.display_name} 已添加')
            return redirect('player_list')
    else:
        form = PlayerForm()
    return render(request, 'rotation/player_form.html', {'form': form, 'title': '添加球员'})
