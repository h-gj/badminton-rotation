"""Recommend round counts for doubles rotation sessions (2 courts, lookup table)."""

MIN_ROUNDS = 3
MAX_ROUNDS = 40

# 参考程序实测数据，2 片场；未列出的人数暂无推荐局数。
# 表中局数均满足：同时上场人数 × 局数 能被 总人数 整除，从而每人上场次数相同。
ROUND_OPTIONS_BY_PLAYERS = {
    5: [5, 10],
    6: [6, 9, 15],
    7: [14, 21],
    8: [14],
    9: [18],
    10: [25],
    11: [33],
    12: [24, 33],
}


def _effective_slots(player_count, courts):
    slots = min(player_count, courts * 4)
    return (slots // 4) * 4


def expected_games_per_player(player_count, rounds, courts=2):
    """每人应打几场；无法均分时返回 None。"""
    active = _effective_slots(player_count, courts)
    if active < 4:
        return None
    total_slots = active * rounds
    if total_slots % player_count != 0:
        return None
    return total_slots // player_count


def is_balanced_schedule(player_count, rounds, courts=2):
    return expected_games_per_player(player_count, rounds, courts) is not None


def recommend_round_options(player_count, courts=2):
    if courts != 2 or player_count < 4:
        return []
    options = ROUND_OPTIONS_BY_PLAYERS.get(player_count, [])
    return [r for r in options if is_balanced_schedule(player_count, r, courts)]


def pick_default_rounds(current_rounds, options):
    if not options:
        return MIN_ROUNDS
    if current_rounds in options:
        return current_rounds
    return options[0] if len(options) == 1 else options[len(options) // 2]
