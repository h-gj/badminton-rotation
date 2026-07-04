from datetime import datetime, time
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from rotation.models import Session


class SessionScoresEditableTests(TestCase):
    def _make_session(self, **kwargs):
        defaults = {
            'title': '8人多人轮转赛',
            'event_date': timezone.make_aware(datetime(2026, 7, 10, 20, 0)),
        }
        defaults.update(kwargs)
        return Session.objects.create(**defaults)

    def test_editable_on_creation_day_without_end_time(self):
        created = timezone.make_aware(datetime(2026, 7, 4, 12, 0))
        session = self._make_session(event_end_time=None, created_at=created)
        now = timezone.make_aware(datetime(2026, 7, 4, 23, 30))
        with patch('rotation.models._local_now', return_value=now):
            self.assertTrue(session.scores_editable)

    def test_locked_after_creation_day_without_end_time(self):
        created = timezone.make_aware(datetime(2026, 7, 4, 12, 0))
        session = self._make_session(event_end_time=None, created_at=created)
        now = timezone.make_aware(datetime(2026, 7, 5, 0, 30))
        with patch('rotation.models._local_now', return_value=now):
            self.assertFalse(session.scores_editable)

    def test_editable_before_event_end_time(self):
        session = self._make_session(
            event_date=timezone.make_aware(datetime(2026, 7, 10, 20, 0)),
            event_end_time=time(23, 0),
        )
        now = timezone.make_aware(datetime(2026, 7, 10, 22, 0))
        with patch('rotation.models._local_now', return_value=now):
            self.assertTrue(session.scores_editable)

    def test_locked_after_event_end_time(self):
        session = self._make_session(
            event_date=timezone.make_aware(datetime(2026, 7, 4, 20, 0)),
            event_end_time=time(23, 0),
        )
        now = timezone.make_aware(datetime(2026, 7, 4, 23, 30))
        with patch('rotation.models._local_now', return_value=now):
            self.assertFalse(session.scores_editable)

    def test_editable_when_end_before_creation_bad_date(self):
        """结束时间早于创建时刻（日期解析错误）时，按创建当天可编辑。"""
        created = timezone.make_aware(datetime(2026, 7, 4, 12, 0))
        session = self._make_session(
            event_date=timezone.make_aware(datetime(2023, 7, 9, 20, 0)),
            event_end_time=time(23, 0),
            created_at=created,
        )
        now = timezone.make_aware(datetime(2026, 7, 4, 12, 30))
        with patch('rotation.models._local_now', return_value=now):
            self.assertTrue(session.scores_editable)

    def test_new_session_without_end_time_not_locked_same_day(self):
        now = timezone.make_aware(datetime(2026, 7, 4, 12, 30))
        session = Session.objects.create(
            title='8人多人轮转赛',
            event_date=now.replace(hour=20, minute=0, second=0, microsecond=0),
            event_end_time=None,
        )
        with patch('rotation.models._local_now', return_value=now):
            self.assertTrue(session.scores_editable)
