from django.test import TestCase

from rotation.models import Player, Session
from rotation.services.scheduler import RotationScheduler


class SchedulerTests(TestCase):
    def test_eight_players_two_courts(self):
        ids = list(range(1, 9))
        scheduler = RotationScheduler(ids, courts=2, rounds=3)
        matches = scheduler.generate()
        self.assertEqual(len(matches), 6)

    def test_twelve_players_two_courts(self):
        ids = list(range(1, 13))
        scheduler = RotationScheduler(ids, courts=2, rounds=2)
        matches = scheduler.generate()
        self.assertEqual(len(matches), 4)
