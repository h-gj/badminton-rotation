from datetime import date, time

from django.test import SimpleTestCase
from django.utils import timezone

from rotation.services.wechat_import import parse_group_name_text


class ParseGroupNameTextTests(SimpleTestCase):
    def test_rongda_evening_session(self):
        reference = date(2026, 7, 4)
        result = parse_group_name_text('7.9 周四晚荣达 8 到 11 打转打水 6折', reference)
        self.assertEqual(result['event_date'], date(2026, 7, 9))
        self.assertEqual(result['location'], '荣达')
        self.assertEqual(result['event_start_time'], time(20, 0))
        self.assertEqual(result['event_end_time'], time(23, 0))

    def test_coerce_wrong_year_from_full_date(self):
        from rotation.services.wechat_import import _parse_date_value

        reference = date(2026, 7, 4)
        self.assertEqual(
            _parse_date_value('2023-07-09', reference),
            date(2026, 7, 9),
        )
