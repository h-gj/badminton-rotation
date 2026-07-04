"""Analyze play/rest patterns from generated matches."""


def build_round_list(matches):
    rounds = {}
    for m in matches:
        rounds.setdefault(m.round_number, []).append(m)
    return sorted(rounds.items())


def analyze_play_streaks(ordered_players, round_list):
    """
    ordered_players: list of Player objects in registration order.
    round_list: [(round_number, [match, ...]), ...]
    """
    player_ids = [p.id for p in ordered_players]
    id_to_name = {p.id: p.display_name for p in ordered_players}
    streak = {pid: 0 for pid in player_ids}
    max_streak = {pid: 0 for pid in player_ids}
    timeline = []

    for round_number, matches in round_list:
        playing = set()
        for m in matches:
            playing.update([
                m.team1_player1_id,
                m.team1_player2_id,
                m.team2_player1_id,
                m.team2_player2_id,
            ])
        playing_names = []
        resting_names = []
        court_lines = []
        for m in sorted(matches, key=lambda x: x.court_number):
            t1 = f'{m.team1_player1.display_name}/{m.team1_player2.display_name}'
            t2 = f'{m.team2_player1.display_name}/{m.team2_player2.display_name}'
            court_lines.append(f'  {m.court_number}号场  {t1}  vs  {t2}')

        for pid in player_ids:
            name = id_to_name[pid]
            if pid in playing:
                playing_names.append(name)
                streak[pid] += 1
                max_streak[pid] = max(max_streak[pid], streak[pid])
            else:
                resting_names.append(name)
                streak[pid] = 0

        timeline.append({
            'round': round_number,
            'playing': playing_names,
            'resting': resting_names,
            'courts': court_lines,
        })

    overall_max = max(max_streak.values()) if max_streak else 0
    return {
        'max_streak': {id_to_name[pid]: max_streak[pid] for pid in player_ids},
        'overall_max': overall_max,
        'timeline': timeline,
    }


def format_analysis_report(session, ordered_players, round_list):
    result = analyze_play_streaks(ordered_players, round_list)
    lines = [
        '',
        f'=== {session.title}（{session.rounds} 局）连打分析 ===',
        f'共 {sum(len(ms) for _, ms in round_list)} 场对阵',
        '',
    ]
    for row in result['timeline']:
        lines.append(
            f"第{row['round']}局  上场：{', '.join(row['playing'])}  "
            f"休息：{', '.join(row['resting']) or '无'}"
        )
        lines.extend(row['courts'])
    lines.append('')
    lines.append('=== 每人最长连打 ===')
    for name, streak in result['max_streak'].items():
        flag = '  ⚠ 连打≥3' if streak >= 3 else ''
        lines.append(f'  {name}：{streak} 局{flag}')
    lines.append(f'全员最长连打：{result["overall_max"]} 局')
    if result['overall_max'] >= 3:
        lines.append('结论：存在连打 3 局及以上')
    else:
        lines.append('结论：无人连打 3 局及以上')
    lines.append('')
    return '\n'.join(lines)
