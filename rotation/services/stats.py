from django.utils import timezone

from rotation.models import Match

MIN_PARTNER_MATCHES_FOR_RATE = 4


def _classify_doubles_team(p1, p2):
    """根据搭档两人性别判定双打类型，与排阵逻辑一致。"""
    g1, g2 = p1.gender, p2.gender
    if not g1 or not g2:
        return None
    if g1 == 'M' and g2 == 'M':
        return 'mm'
    if g1 == 'F' and g2 == 'F':
        return 'ff'
    return 'mixed'


def _empty_bucket():
    return {'wins': 0, 'losses': 0, 'matches': 0}


def _finalize_bucket(bucket):
    m = bucket['matches']
    bucket['win_rate'] = round(bucket['wins'] / m * 100, 1) if m else None
    return bucket


def _build_doubles_rates(by_type, player_gender):
    order = ('mm', 'mixed', 'ff')
    hide_map = {'mm': 'F', 'ff': 'M', 'mixed': None}
    label_map = {'mm': '男双', 'ff': '女双', 'mixed': '混双'}
    rates = []
    for key in order:
        if player_gender and hide_map[key] == player_gender:
            continue
        bucket = _finalize_bucket(by_type.get(key, _empty_bucket()))
        if not bucket['matches']:
            continue
        rates.append({
            'key': key,
            'label': label_map[key],
            **bucket,
        })
    return rates


def _pair_key(a_id, b_id):
    return (a_id, b_id) if a_id < b_id else (b_id, a_id)


def _build_win_rate_chart(session_list_chrono):
    """生成往期胜率曲线图坐标（viewBox 0–100，y=0 为 100% 胜率）。"""
    count = len(session_list_chrono)
    if not count:
        return {'points': [], 'polyline': '', 'area': '', 'min_width_rem': 6.0}

    points = []
    for i, s in enumerate(session_list_chrono):
        x = 50.0 if count == 1 else round(i / (count - 1) * 100, 2)
        y = round(100 - s['win_rate'], 2)
        local = timezone.localtime(s['session'].event_date)
        points.append({
            'x': x,
            'y': y,
            'win_rate': s['win_rate'],
            'wins': s['wins'],
            'matches': s['matches'],
            'label': f'{local.month}/{local.day}',
            'title': f"{s['session'].title} · {s['wins']}/{s['matches']} 胜",
        })

    polyline = ' '.join(f"{p['x']},{p['y']}" for p in points)
    area = f"{polyline} {points[-1]['x']},100 {points[0]['x']},100"
    return {
        'points': points,
        'polyline': polyline,
        'area': area,
        'min_width_rem': max(6.0, count * 2.5),
    }


def compute_session_stats(session, sort_by='wins'):
    """计算场次排行榜与个人统计。sort_by: wins（胜局）或 points（胜分）。"""
    matches = Match.objects.filter(session=session, is_completed=True).select_related(
        'team1_player1', 'team1_player2', 'team2_player1', 'team2_player2',
    )

    players = {
        r.player_id: r.player
        for r in session.registrations.select_related('player')
    }

    stats = {}
    for pid, player in players.items():
        stats[pid] = {
            'player': player,
            'wins': 0,
            'losses': 0,
            'draws': 0,
            'matches': 0,
            'points_for': 0,
            'points_against': 0,
            'partners': {},
        }

    for match in matches:
        t1 = match.team1_players()
        t2 = match.team2_players()
        s1, s2 = match.score_team1, match.score_team2

        for p in t1:
            if p.id in stats:
                stats[p.id]['points_for'] += s1
                stats[p.id]['points_against'] += s2
        for p in t2:
            if p.id in stats:
                stats[p.id]['points_for'] += s2
                stats[p.id]['points_against'] += s1

        winner = match.winner_team
        if winner == 0:
            for p in t1 + t2:
                if p.id in stats:
                    stats[p.id]['draws'] += 1
                    stats[p.id]['matches'] += 1
        elif winner == 1:
            for p in t1:
                if p.id in stats:
                    stats[p.id]['wins'] += 1
                    stats[p.id]['matches'] += 1
            for p in t2:
                if p.id in stats:
                    stats[p.id]['losses'] += 1
                    stats[p.id]['matches'] += 1
        elif winner == 2:
            for p in t2:
                if p.id in stats:
                    stats[p.id]['wins'] += 1
                    stats[p.id]['matches'] += 1
            for p in t1:
                if p.id in stats:
                    stats[p.id]['losses'] += 1
                    stats[p.id]['matches'] += 1

        if winner == 0:
            _accumulate_partner_stats(stats, t1, None)
            _accumulate_partner_stats(stats, t2, None)
        elif winner == 1:
            _accumulate_partner_stats(stats, t1, True)
            _accumulate_partner_stats(stats, t2, False)
        elif winner == 2:
            _accumulate_partner_stats(stats, t2, True)
            _accumulate_partner_stats(stats, t1, False)

    leaderboard = []
    for pid, s in stats.items():
        m = s['matches']
        s['win_rate'] = round(s['wins'] / m * 100, 1) if m else 0.0
        s['point_diff'] = s['points_for'] - s['points_against']
        partner_list = []
        for (a, b), ps in s['partners'].items():
            other_id = b if a == pid else a
            other = players.get(other_id)
            if not other:
                continue
            pm = ps['matches']
            if pm < MIN_PARTNER_MATCHES_FOR_RATE:
                continue
            partner_list.append({
                'partner': other,
                'wins': ps['wins'],
                'losses': ps['losses'],
                'draws': ps['draws'],
                'matches': pm,
                'win_rate': round(ps['wins'] / pm * 100, 1) if pm else 0.0,
            })
        partner_list.sort(key=lambda x: (-x['win_rate'], -x['matches']))
        s['partner_list'] = partner_list
        leaderboard.append(s)

    if sort_by == 'points':
        sort_key = lambda x: (-x['point_diff'], -x['wins'], -x['win_rate'], x['player'].display_name)
    else:
        sort_key = lambda x: (-x['wins'], -x['win_rate'], -x['point_diff'], x['player'].display_name)
    leaderboard.sort(key=sort_key)
    for i, row in enumerate(leaderboard, start=1):
        row['rank'] = i

    return leaderboard


def _accumulate_partner_stats(stats, team, won_or_draw):
    if len(team) != 2:
        return
    p1, p2 = team
    for pid in (p1.id, p2.id):
        if pid not in stats:
            continue
        other_id = p2.id if pid == p1.id else p1.id
        key = _pair_key(pid, other_id)
        bucket = stats[pid]['partners'].setdefault(
            key, {'wins': 0, 'losses': 0, 'draws': 0, 'matches': 0}
        )
        bucket['matches'] += 1
        if won_or_draw is True:
            bucket['wins'] += 1
        elif won_or_draw is False:
            bucket['losses'] += 1
        else:
            bucket['draws'] += 1


def compute_player_stats(player):
    """球员跨场次汇总统计。"""
    matches = Match.objects.filter(is_completed=True).filter(
        models_q_player(player)
    ).select_related('session', 'team1_player1', 'team1_player2', 'team2_player1', 'team2_player2')

    total = {'wins': 0, 'losses': 0, 'draws': 0, 'matches': 0}
    sessions = {}
    partners = {}
    by_doubles = {'mm': _empty_bucket(), 'ff': _empty_bucket(), 'mixed': _empty_bucket()}

    for match in matches:
        in_t1 = player.id in [match.team1_player1_id, match.team1_player2_id]
        team = match.team1_players() if in_t1 else match.team2_players()
        partner = team[1] if team[0].id == player.id else team[0]
        w = match.winner_team
        won = (w == 1 and in_t1) or (w == 2 and not in_t1)
        lost = w != 0 and not won

        total['matches'] += 1
        sid = match.session_id
        sessions.setdefault(sid, {'session': match.session, 'wins': 0, 'losses': 0, 'matches': 0})
        sessions[sid]['matches'] += 1

        pk = _pair_key(player.id, partner.id)
        partners.setdefault(pk, {'partner': partner, 'wins': 0, 'losses': 0, 'matches': 0})
        partners[pk]['matches'] += 1

        doubles_type = _classify_doubles_team(player, partner)
        if doubles_type:
            by_doubles[doubles_type]['matches'] += 1

        if w == 0:
            total['draws'] += 1
        elif won:
            total['wins'] += 1
            sessions[sid]['wins'] += 1
            partners[pk]['wins'] += 1
            if doubles_type:
                by_doubles[doubles_type]['wins'] += 1
        elif lost:
            total['losses'] += 1
            sessions[sid]['losses'] += 1
            partners[pk]['losses'] += 1
            if doubles_type:
                by_doubles[doubles_type]['losses'] += 1

    m = total['matches']
    total['win_rate'] = round(total['wins'] / m * 100, 1) if m else 0.0

    session_list = list(sessions.values())
    for s in session_list:
        sm = s['matches']
        s['win_rate'] = round(s['wins'] / sm * 100, 1) if sm else 0.0

    session_list_chrono = sorted(session_list, key=lambda x: x['session'].event_date)
    win_rate_delta = None
    if len(session_list_chrono) >= 2:
        win_rate_delta = round(
            session_list_chrono[-1]['win_rate'] - session_list_chrono[-2]['win_rate'],
            1,
        )

    chart = _build_win_rate_chart(session_list_chrono)
    doubles_rates = _build_doubles_rates(by_doubles, player.gender)

    partner_list = sorted(
        [
            {
                **v,
                'win_rate': round(v['wins'] / v['matches'] * 100, 1) if v['matches'] else 0.0,
            }
            for v in partners.values()
            if v['matches'] >= MIN_PARTNER_MATCHES_FOR_RATE
        ],
        key=lambda x: (-x['win_rate'], -x['matches']),
    )

    return {
        'total': total,
        'sessions': sorted(session_list, key=lambda x: x['session'].event_date, reverse=True),
        'partners': partner_list,
        'trends': {
            'chart_sessions': session_list_chrono,
            'chart': chart,
            'delta': win_rate_delta,
        },
        'doubles_rates': doubles_rates,
    }


def models_q_player(player):
    from django.db.models import Q
    return (
        Q(team1_player1=player) | Q(team1_player2=player)
        | Q(team2_player1=player) | Q(team2_player2=player)
    )


def build_player_match_entry(match, player):
    """从球员视角整理单场对局信息。"""
    in_t1 = player.id in (match.team1_player1_id, match.team1_player2_id)
    w = match.winner_team
    if w == 0:
        result = 'draw'
    elif (w == 1 and in_t1) or (w == 2 and not in_t1):
        result = 'win'
    else:
        result = 'loss'

    my_team = match.team1_players() if in_t1 else match.team2_players()
    opp_team = match.team2_players() if in_t1 else match.team1_players()
    my_score = match.score_team1 if in_t1 else match.score_team2
    opp_score = match.score_team2 if in_t1 else match.score_team1

    return {
        'match': match,
        'result': result,
        'won': result == 'win',
        'lost': result == 'loss',
        'my_team': my_team,
        'opp_team': opp_team,
        'my_score': my_score,
        'opp_score': opp_score,
        'score_diff': abs(my_score - opp_score) if my_score is not None and opp_score is not None else None,
    }


def get_player_match_groups(player, result_filter='all'):
    """按活动分组返回球员已完成对局。result_filter: all / win / loss。"""
    from collections import OrderedDict

    if result_filter not in ('all', 'win', 'loss'):
        result_filter = 'all'

    matches = (
        Match.objects.filter(is_completed=True)
        .filter(models_q_player(player))
        .select_related(
            'session',
            'team1_player1', 'team1_player2',
            'team2_player1', 'team2_player2',
            'scored_by',
        )
        .order_by('-session__event_date', '-session__created_at', 'round_number', 'court_number')
    )

    counts = {'all': 0, 'win': 0, 'loss': 0}
    groups = OrderedDict()

    for match in matches:
        entry = build_player_match_entry(match, player)
        counts['all'] += 1
        if entry['won']:
            counts['win'] += 1
        elif entry['lost']:
            counts['loss'] += 1

        if result_filter == 'win' and not entry['won']:
            continue
        if result_filter == 'loss' and not entry['lost']:
            continue

        sid = match.session_id
        if sid not in groups:
            groups[sid] = {'session': match.session, 'matches': []}
        entry['match_number'] = len(groups[sid]['matches']) + 1
        groups[sid]['matches'].append(entry)

    return list(groups.values()), counts


def get_session_leaderboard_context(session, user):
    """比赛成绩页状态：是否已结束，及当前用户剩余场次。"""
    match_count = session.matches.count()
    completed_count = session.matches.filter(is_completed=True).count()
    is_completed = (
        session.status == session.Status.COMPLETED
        or (match_count > 0 and completed_count >= match_count)
    )

    participant_remaining = None
    if not is_completed and user.is_authenticated:
        from rotation.models import Player

        player = Player.objects.filter(user=user).first()
        if player and session.registrations.filter(player_id=player.pk).exists():
            player_total = session.matches.filter(models_q_player(player)).count()
            player_done = session.matches.filter(is_completed=True).filter(models_q_player(player)).count()
            left = player_total - player_done
            if left > 0:
                participant_remaining = left

    return {
        'session_is_completed': is_completed,
        'participant_remaining': participant_remaining,
        'match_count': match_count,
        'completed_count': completed_count,
    }
