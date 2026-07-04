from datetime import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from rotation.forms import default_session_title
from rotation.models import Player, Registration, Session
from rotation.services.rotation_analysis import build_round_list, format_analysis_report
from rotation.services.scheduler import generate_session_matches


TEST_PLAYER_NAMES = ['测试A', '测试B', '测试C', '测试D', '测试E', '测试F']

PRESETS = {
    '6x15': {'players': 6, 'rounds': 15},
    '6x9': {'players': 6, 'rounds': 9},
    '6x6': {'players': 6, 'rounds': 6},
    '8x14': {'players': 8, 'rounds': 14},
}


class Command(BaseCommand):
    help = '生成轮转测试活动并打印连打分析（用于核实是否连打三局）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--preset',
            default='6x15',
            choices=sorted(PRESETS.keys()),
            help='测试预设（默认 6x15 = 6人15局）',
        )
        parser.add_argument(
            '--players',
            type=int,
            help='覆盖预设：人数',
        )
        parser.add_argument(
            '--rounds',
            type=int,
            help='覆盖预设：局数',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='删除同名测试球员与标题相同的旧测试活动后重建',
        )

    def handle(self, *args, **options):
        preset = PRESETS[options['preset']]
        player_count = options['players'] or preset['players']
        rounds = options['rounds'] or preset['rounds']

        if options['reset']:
            self._reset_test_data(player_count)

        players = self._get_or_create_players(player_count)
        session = self._create_session(players, player_count, rounds)
        generate_session_matches(session)

        ordered_players = [
            reg.player for reg in session.registrations.select_related('player').order_by('registered_at')
        ]
        matches = list(
            session.matches.select_related(
                'team1_player1', 'team1_player2', 'team2_player1', 'team2_player2',
            ).order_by('round_number', 'court_number')
        )
        round_list = build_round_list(matches)
        report = format_analysis_report(session, ordered_players, round_list)

        self.stdout.write(self.style.SUCCESS(f'已生成测试活动 id={session.pk}'))
        self.stdout.write(f'标题：{session.title}')
        self.stdout.write(f'人数：{player_count}  局数：{rounds}  对阵：{len(matches)} 场')
        self.stdout.write(f'对局计分页：/sessions/{session.pk}/matches/')
        self.stdout.write(report)

    def _reset_test_data(self, player_count):
        title = default_session_title(player_count)
        deleted_sessions, _ = Session.objects.filter(title=title, notes='连打测试数据').delete()
        if deleted_sessions:
            self.stdout.write(f'已删除 {deleted_sessions} 个旧测试活动')

    def _get_or_create_players(self, count):
        players = []
        for i in range(count):
            name = TEST_PLAYER_NAMES[i] if i < len(TEST_PLAYER_NAMES) else f'测试{i + 1}'
            player, _ = Player.objects.get_or_create(name=name, defaults={'nickname': name})
            players.append(player)
        return players

    def _create_session(self, players, player_count, rounds):
        now = timezone.localtime()
        start = now.replace(hour=20, minute=0, second=0, microsecond=0)
        session = Session.objects.create(
            title=default_session_title(player_count),
            event_date=start,
            event_end_time=time(23, 0),
            courts=2,
            rounds=rounds,
            max_players=player_count,
            notes='连打测试数据',
        )
        for player in players:
            Registration.objects.create(session=session, player=player)
        return session
