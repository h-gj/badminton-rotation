from rotation.models import Match


def _pair_key(a_id, b_id):
    return (a_id, b_id) if a_id < b_id else (b_id, a_id)


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

    for match in matches:
        in_t1 = player.id in [match.team1_player1_id, match.team1_player2_id]
        team = match.team1_players() if in_t1 else match.team2_players()
        partner = team[1] if team[0].id == player.id else team[0]
        w = match.winner_team

        total['matches'] += 1
        sid = match.session_id
        sessions.setdefault(sid, {'session': match.session, 'wins': 0, 'losses': 0, 'matches': 0})
        sessions[sid]['matches'] += 1

        pk = _pair_key(player.id, partner.id)
        partners.setdefault(pk, {'partner': partner, 'wins': 0, 'losses': 0, 'matches': 0})
        partners[pk]['matches'] += 1

        if w == 0:
            total['draws'] += 1
        elif (w == 1 and in_t1) or (w == 2 and not in_t1):
            total['wins'] += 1
            sessions[sid]['wins'] += 1
            partners[pk]['wins'] += 1
        else:
            total['losses'] += 1
            sessions[sid]['losses'] += 1
            partners[pk]['losses'] += 1

    m = total['matches']
    total['win_rate'] = round(total['wins'] / m * 100, 1) if m else 0.0

    partner_list = sorted(
        [
            {
                **v,
                'win_rate': round(v['wins'] / v['matches'] * 100, 1) if v['matches'] else 0.0,
            }
            for v in partners.values()
        ],
        key=lambda x: (-x['win_rate'], -x['matches']),
    )

    return {
        'total': total,
        'sessions': sorted(sessions.values(), key=lambda x: x['session'].event_date, reverse=True),
        'partners': partner_list,
    }


def models_q_player(player):
    from django.db.models import Q
    return (
        Q(team1_player1=player) | Q(team1_player2=player)
        | Q(team2_player1=player) | Q(team2_player2=player)
    )
