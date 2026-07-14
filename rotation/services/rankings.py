from rotation.models import Match, Player, Registration, Session
from rotation.services.stats import MIN_PARTNER_MATCHES_FOR_RATE, _pair_key


def _aggregate_global_stats(club=None):
    """汇总比赛数据，供各类排行榜使用。可按俱乐部筛选。"""
    match_qs = Match.objects.filter(is_completed=True)
    if club:
        match_qs = match_qs.filter(session__club=club)

    session_ids = set(match_qs.values_list('session_id', flat=True).distinct())
    if club:
        session_ids |= set(
            Session.objects.filter(club=club).values_list('pk', flat=True)
        )
    total_sessions = Session.objects.filter(pk__in=session_ids).count() if session_ids else 0

    players_qs = Player.objects.filter(club=club) if club else Player.objects.all()
    players = {p.pk: p for p in players_qs}

    attendance = {pid: set() for pid in players}
    if session_ids:
        for reg in Registration.objects.filter(session_id__in=session_ids):
            if reg.player_id in attendance:
                attendance[reg.player_id].add(reg.session_id)

    player_stats = {
        pid: {
            'player': player,
            'wins': 0,
            'losses': 0,
            'draws': 0,
            'matches': 0,
            'sessions_attended': len(attendance.get(pid, set())),
        }
        for pid, player in players.items()
    }

    partner_buckets = {}

    matches = match_qs.select_related(
        'team1_player1', 'team1_player2', 'team2_player1', 'team2_player2',
    )
    for match in matches:
        t1 = match.team1_players()
        t2 = match.team2_players()
        winner = match.winner_team

        for p in t1 + t2:
            if p.id not in player_stats:
                player_stats[p.id] = {
                    'player': p,
                    'wins': 0,
                    'losses': 0,
                    'draws': 0,
                    'matches': 0,
                    'sessions_attended': len(attendance.get(p.id, set())),
                }

        if winner == 0:
            for p in t1 + t2:
                player_stats[p.id]['draws'] += 1
                player_stats[p.id]['matches'] += 1
            _accumulate_global_partner(partner_buckets, t1, None)
            _accumulate_global_partner(partner_buckets, t2, None)
        elif winner == 1:
            for p in t1:
                player_stats[p.id]['wins'] += 1
                player_stats[p.id]['matches'] += 1
            for p in t2:
                player_stats[p.id]['losses'] += 1
                player_stats[p.id]['matches'] += 1
            _accumulate_global_partner(partner_buckets, t1, True)
            _accumulate_global_partner(partner_buckets, t2, False)
        elif winner == 2:
            for p in t2:
                player_stats[p.id]['wins'] += 1
                player_stats[p.id]['matches'] += 1
            for p in t1:
                player_stats[p.id]['losses'] += 1
                player_stats[p.id]['matches'] += 1
            _accumulate_global_partner(partner_buckets, t2, True)
            _accumulate_global_partner(partner_buckets, t1, False)

    return {
        'total_sessions': total_sessions,
        'player_stats': player_stats,
        'partner_buckets': partner_buckets,
    }


def _accumulate_global_partner(buckets, team, won_or_draw):
    if len(team) != 2:
        return
    p1, p2 = team
    key = _pair_key(p1.id, p2.id)
    bucket = buckets.setdefault(key, {
        'player1': p1,
        'player2': p2,
        'wins': 0,
        'losses': 0,
        'draws': 0,
        'matches': 0,
    })
    bucket['matches'] += 1
    if won_or_draw is True:
        bucket['wins'] += 1
    elif won_or_draw is False:
        bucket['losses'] += 1
    else:
        bucket['draws'] += 1


def _player_matches_filter(row, q):
    if not q:
        return True
    p = row['player']
    haystack = f'{p.name} {p.nickname} {p.display_name}'.lower()
    return q.lower() in haystack


def _partner_matches_filter(row, q):
    if not q:
        return True
    p1, p2 = row['player1'], row['player2']
    haystack = (
        f'{p1.name} {p1.nickname} {p1.display_name} '
        f'{p2.name} {p2.nickname} {p2.display_name}'
    ).lower()
    return q.lower() in haystack


def _build_win_rate_rows(data, q=''):
    rows = []
    for row in data['player_stats'].values():
        if row['matches'] <= 0:
            continue
        if not _player_matches_filter(row, q):
            continue
        m = row['matches']
        rows.append({
            **row,
            'win_rate': round(row['wins'] / m * 100, 1),
        })
    rows.sort(key=lambda x: (
        -x['win_rate'], -x['matches'], -x['wins'], x['player'].display_name,
    ))
    return rows


def _build_attendance_rows(data, q=''):
    total = data['total_sessions']
    if not total:
        return []

    rows = []
    for row in data['player_stats'].values():
        attended = row['sessions_attended']
        if attended <= 0:
            continue
        if not _player_matches_filter(row, q):
            continue
        rows.append({
            **row,
            'attendance_rate': round(attended / total * 100, 1),
        })
    rows.sort(key=lambda x: (
        -x['attendance_rate'], -x['sessions_attended'], x['player'].display_name,
    ))
    return rows


def _build_partner_rows(data, q=''):
    rows = []
    for bucket in data['partner_buckets'].values():
        if bucket['matches'] < MIN_PARTNER_MATCHES_FOR_RATE:
            continue
        row = {**bucket}
        if not _partner_matches_filter(row, q):
            continue
        m = row['matches']
        row['win_rate'] = round(row['wins'] / m * 100, 1)
        rows.append(row)
    rows.sort(key=lambda x: (
        -x['win_rate'], -x['matches'], -x['wins'],
        x['player1'].display_name, x['player2'].display_name,
    ))
    return rows


def build_all_rankings(q='', club=None):
    data = _aggregate_global_stats(club=club)
    return {
        'win_rate': _build_win_rate_rows(data, q),
        'attendance': _build_attendance_rows(data, q),
        'partner': _build_partner_rows(data, q),
        'total_sessions': data['total_sessions'],
    }


def build_win_rate_rankings(q='', club=None):
    data = _aggregate_global_stats(club=club)
    return _build_win_rate_rows(data, q)


def build_attendance_rankings(q='', club=None):
    data = _aggregate_global_stats(club=club)
    return _build_attendance_rows(data, q), data['total_sessions']


def build_partner_rankings(q='', club=None):
    data = _aggregate_global_stats(club=club)
    return _build_partner_rows(data, q)
