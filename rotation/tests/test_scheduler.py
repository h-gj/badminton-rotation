from django.test import TestCase

from rotation.services.round_options import (
    ROUND_OPTIONS_BY_PLAYERS,
    expected_games_per_player,
    is_balanced_schedule,
    recommend_round_options,
)
from rotation.services.scheduler import RotationScheduler, _pair_key


class RoundOptionsTests(TestCase):
    def test_lookup_table(self):
        cases = {
            5: [5, 10],
            6: [6, 9, 15],
            7: [14, 21],
            8: [14],
            9: [18],
            10: [25],
            11: [33],
            12: [24, 33],
        }
        for player_count, expected in cases.items():
            with self.subTest(player_count=player_count):
                self.assertEqual(recommend_round_options(player_count), expected)

    def test_all_lookup_entries_are_balanced(self):
        for player_count, rounds_list in ROUND_OPTIONS_BY_PLAYERS.items():
            for rounds in rounds_list:
                with self.subTest(player_count=player_count, rounds=rounds):
                    self.assertTrue(is_balanced_schedule(player_count, rounds))
                    self.assertIsNotNone(expected_games_per_player(player_count, rounds))

    def test_unknown_player_count(self):
        self.assertEqual(recommend_round_options(4), [])
        self.assertEqual(recommend_round_options(13), [])


class BalancedRotationTests(TestCase):
    def test_equal_play_counts_for_all_lookup_entries(self):
        for player_count, rounds_list in ROUND_OPTIONS_BY_PLAYERS.items():
            for rounds in rounds_list:
                with self.subTest(player_count=player_count, rounds=rounds):
                    target = expected_games_per_player(player_count, rounds)
                    ids = list(range(1, player_count + 1))
                    scheduler = RotationScheduler(ids, courts=2, rounds=rounds)
                    scheduler.generate()
                    counts = list(scheduler.play_count.values())
                    self.assertEqual(len(set(counts)), 1)
                    self.assertEqual(counts[0], target)

    def test_rejects_unbalanced_round_count(self):
        scheduler = RotationScheduler(list(range(1, 7)), courts=2, rounds=10)
        with self.assertRaises(ValueError):
            scheduler.generate()


class SchedulerTests(TestCase):
    def test_eight_players_two_courts(self):
        ids = list(range(1, 9))
        scheduler = RotationScheduler(ids, courts=2, rounds=3)
        matches = scheduler.generate()
        self.assertEqual(len(matches), 6)

    def test_twelve_players_two_courts(self):
        ids = list(range(1, 13))
        scheduler = RotationScheduler(ids, courts=2, rounds=24)
        matches = scheduler.generate()
        self.assertEqual(len(matches), 48)
        self.assertEqual(len(set(scheduler.play_count.values())), 1)
        self.assertEqual(scheduler.play_count[1], 16)

    def test_six_players_fifteen_rounds_balanced_partners(self):
        for player_ids in (list(range(1, 7)), list(range(45, 51))):
            with self.subTest(player_ids=player_ids[0]):
                scheduler = RotationScheduler(player_ids, courts=2, rounds=15)
                scheduler.generate()
                self.assertEqual(set(scheduler.partner_count.values()), {2})
                self.assertEqual(len(scheduler.partner_count), 15)
                if 49 in player_ids:
                    self.assertEqual(scheduler.partner_count[_pair_key(49, 50)], 2)

    def test_balanced_partner_counts_for_feasible_configs(self):
        configs = (
            (5, 5, 1),
            (5, 10, 2),
            (6, 15, 2),
            (8, 14, 2),
        )
        for player_count, rounds, target in configs:
            with self.subTest(player_count=player_count, rounds=rounds):
                scheduler = RotationScheduler(
                    list(range(1, player_count + 1)),
                    courts=2,
                    rounds=rounds,
                )
                scheduler.generate()
                self.assertEqual(set(scheduler.partner_count.values()), {target})
                self.assertEqual(
                    len(scheduler.partner_count),
                    player_count * (player_count - 1) // 2,
                )
