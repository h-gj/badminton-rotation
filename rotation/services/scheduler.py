from itertools import combinations
from random import shuffle


def _pair_key(a_id, b_id):
    return (a_id, b_id) if a_id < b_id else (b_id, a_id)


def _effective_slots(player_count, courts):
    slots = min(player_count, courts * 4)
    return (slots // 4) * 4


def _expected_games_per_player(player_count, rounds, courts):
    active = _effective_slots(player_count, courts)
    if active < 4:
        return None
    total_slots = active * rounds
    if total_slots % player_count != 0:
        return None
    return total_slots // player_count


class RotationScheduler:
    """Doubles rotation scheduler with equal games per player and minimal repeat pairings."""

    def __init__(self, player_ids, courts, rounds, avoid_mixed_gender_doubles=False, player_genders=None):
        self.player_ids = list(player_ids)
        self.courts = courts
        self.rounds = rounds
        self.avoid_mixed_gender_doubles = avoid_mixed_gender_doubles
        self.player_genders = player_genders or {}
        self.partner_count = {}
        self.opponent_count = {}
        self.play_count = {pid: 0 for pid in self.player_ids}

    def generate(self):
        n = len(self.player_ids)
        if _effective_slots(n, self.courts) < 4:
            raise ValueError('至少需要 4 名球员才能生成双打对阵')

        target = _expected_games_per_player(n, self.rounds, self.courts)
        if target is None:
            raise ValueError('当前人数与局数无法保证每人上场次数相同，请重新选择局数')

        matches = []
        slots_per_round = self.courts * 4

        for round_num in range(1, self.rounds + 1):
            round_matches = self._schedule_round(round_num, slots_per_round)
            matches.extend(round_matches)

        self._assert_balanced_play_counts(target)
        return matches

    def _assert_balanced_play_counts(self, target):
        counts = list(self.play_count.values())
        if not counts or any(c != target for c in counts):
            detail = ', '.join(f'{pid}:{self.play_count[pid]}' for pid in self.player_ids)
            raise ValueError(f'上场次数未均分（目标每人 {target} 场）：{detail}')

    def _players_for_round(self, round_num):
        """Deterministic sit-out rotation so each player plays the same number of rounds."""
        n = len(self.player_ids)
        max_play = min(_effective_slots(n, self.courts), self.courts * 4)
        sit_count = n - max_play
        if sit_count <= 0:
            return list(self.player_ids)

        round_idx = round_num - 1
        sit_indices = {(round_idx * sit_count + j) % n for j in range(sit_count)}
        return [pid for idx, pid in enumerate(self.player_ids) if idx not in sit_indices]

    def _schedule_round(self, round_num, slots_per_round):
        max_play = min(_effective_slots(len(self.player_ids), self.courts), slots_per_round)
        playing = self._players_for_round(round_num)
        if len(playing) != max_play:
            raise ValueError(f'第 {round_num} 轮上场人数异常')

        for pid in playing:
            self.play_count[pid] += 1

        court_assignments = self._assign_courts(playing)
        round_matches = []
        for court_idx, group in enumerate(court_assignments, start=1):
            team1, team2 = self._split_teams(group)
            p1, p2 = team1
            p3, p4 = team2
            self._record_pair(p1, p2)
            self._record_pair(p3, p4)
            for a in team1:
                for b in team2:
                    self._record_opponent(a, b)
            round_matches.append({
                'round_number': round_num,
                'court_number': court_idx,
                'team1_player1_id': p1,
                'team1_player2_id': p2,
                'team2_player1_id': p3,
                'team2_player2_id': p4,
            })
        return round_matches

    def _assign_courts(self, playing):
        players = list(playing)
        shuffle(players)
        groups = []
        for i in range(0, len(players), 4):
            groups.append(players[i:i + 4])
        return groups

    def _split_teams(self, group):
        best = None
        best_score = None
        for team1 in combinations(group, 2):
            team2 = [p for p in group if p not in team1]
            score = (
                self.partner_count.get(_pair_key(*team1), 0)
                + self.partner_count.get(_pair_key(*team2), 0)
                + sum(
                    self.opponent_count.get(_pair_key(a, b), 0)
                    for a in team1 for b in team2
                )
                + self._gender_penalty(list(team1), team2)
            )
            if best_score is None or score < best_score:
                best_score = score
                best = (list(team1), team2)
        return best

    def _team_gender_type(self, team):
        genders = [self.player_genders.get(pid, '') for pid in team]
        if not all(genders):
            return 'unknown'
        if all(g == 'F' for g in genders):
            return 'ff'
        if all(g == 'M' for g in genders):
            return 'mm'
        return 'mixed'

    def _gender_penalty(self, team1, team2):
        if not self.avoid_mixed_gender_doubles:
            return 0
        t1 = self._team_gender_type(team1)
        t2 = self._team_gender_type(team2)
        if (t1 == 'ff' and t2 == 'mm') or (t1 == 'mm' and t2 == 'ff'):
            return 10000
        return 0

    def _record_pair(self, a, b):
        key = _pair_key(a, b)
        self.partner_count[key] = self.partner_count.get(key, 0) + 1

    def _record_opponent(self, a, b):
        key = _pair_key(a, b)
        self.opponent_count[key] = self.opponent_count.get(key, 0) + 1


def generate_session_matches(session):
    from rotation.models import Match, Player

    player_ids = list(
        session.registrations.values_list('player_id', flat=True).order_by('registered_at')
    )
    player_genders = dict(
        Player.objects.filter(id__in=player_ids).values_list('id', 'gender')
    )
    scheduler = RotationScheduler(
        player_ids,
        session.courts,
        session.rounds,
        avoid_mixed_gender_doubles=session.avoid_mixed_gender_doubles,
        player_genders=player_genders,
    )
    planned = scheduler.generate()

    Match.objects.filter(session=session).delete()
    Match.objects.bulk_create([
        Match(session=session, **m) for m in planned
    ])

    session.status = session.Status.SCHEDULED
    session.save(update_fields=['status'])
    return len(planned)
