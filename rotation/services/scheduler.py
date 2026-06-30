from itertools import combinations
from random import shuffle


def _pair_key(a_id, b_id):
    return (a_id, b_id) if a_id < b_id else (b_id, a_id)


def _effective_slots(player_count, courts):
    slots = min(player_count, courts * 4)
    return (slots // 4) * 4


class RotationScheduler:
    """Doubles rotation scheduler with fair sit-outs and minimal repeat pairings."""

    def __init__(self, player_ids, courts, rounds):
        self.player_ids = list(player_ids)
        self.courts = courts
        self.rounds = rounds
        self.partner_count = {}
        self.opponent_count = {}
        self.play_count = {pid: 0 for pid in self.player_ids}
        self.sit_out_streak = {pid: 0 for pid in self.player_ids}

    def generate(self):
        if _effective_slots(len(self.player_ids), self.courts) < 4:
            raise ValueError('至少需要 4 名球员才能生成双打对阵')

        matches = []
        slots_per_round = self.courts * 4

        for round_num in range(1, self.rounds + 1):
            round_matches = self._schedule_round(round_num, slots_per_round)
            matches.extend(round_matches)

        return matches

    def _schedule_round(self, round_num, slots_per_round):
        max_play = _effective_slots(len(self.player_ids), self.courts)
        max_play = min(max_play, slots_per_round)
        playing = self._pick_players(max_play)
        sitting = [p for p in self.player_ids if p not in playing]

        for pid in playing:
            self.play_count[pid] += 1
            self.sit_out_streak[pid] = 0
        for pid in sitting:
            self.sit_out_streak[pid] += 1

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

    def _pick_players(self, count):
        ranked = sorted(
            self.player_ids,
            key=lambda pid: (self.sit_out_streak[pid], -self.play_count[pid], pid),
            reverse=True,
        )
        return ranked[:count]

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
            )
            if best_score is None or score < best_score:
                best_score = score
                best = (list(team1), team2)
        return best

    def _record_pair(self, a, b):
        key = _pair_key(a, b)
        self.partner_count[key] = self.partner_count.get(key, 0) + 1

    def _record_opponent(self, a, b):
        key = _pair_key(a, b)
        self.opponent_count[key] = self.opponent_count.get(key, 0) + 1


def generate_session_matches(session):
    from rotation.models import Match

    player_ids = list(
        session.registrations.values_list('player_id', flat=True).order_by('registered_at')
    )
    scheduler = RotationScheduler(player_ids, session.courts, session.rounds)
    planned = scheduler.generate()

    Match.objects.filter(session=session).delete()
    Match.objects.bulk_create([
        Match(session=session, **m) for m in planned
    ])

    session.status = session.Status.SCHEDULED
    session.save(update_fields=['status'])
    return len(planned)
