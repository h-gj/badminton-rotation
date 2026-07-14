import re

from django.contrib.auth import get_user_model
from pypinyin import Style, lazy_pinyin

from rotation.models import ClubMembership, Player

DEFAULT_PLAYER_PASSWORD = '666666'


def name_to_username(name):
    """姓名转拼音部分：中文取拼音全拼，去掉空白与特殊符号。"""
    name = (name or '').strip()
    if not name:
        return 'user'
    compact = re.sub(r'[\s,，、/\\|.\-_]+', '', name)
    chinese = re.sub(r'[a-zA-Z0-9]', '', compact)
    ascii_part = re.sub(r'[^a-zA-Z0-9]', '', compact).lower()
    pinyin_part = (
        ''.join(lazy_pinyin(chinese, style=Style.NORMAL)).lower()
        if chinese else ''
    )
    username = re.sub(r'[^a-z0-9]', '', f'{pinyin_part}{ascii_part}')
    return username or 'user'


def login_username_for_club(club, name):
    """生成可预期的登录用户名：邀请码_姓名拼音，如 418cac_zhangsan。"""
    pinyin = name_to_username(name)
    prefix = (club.invite_code or str(club.pk)).lower()
    return f'{prefix}_{pinyin}'


def login_username_hint(club):
    prefix = (club.invite_code or str(club.pk)).lower()
    return f'{prefix}_姓名拼音（如 {prefix}_zhangsan）'


def _allocate_username(base):
    User = get_user_model()
    candidate = base[:150] or 'user'
    suffix = 2
    while User.objects.filter(username=candidate).exists():
        tail = str(suffix)
        candidate = f'{base[:150 - len(tail)]}{tail}'
        suffix += 1
    return candidate


def _create_club_member_user(club, display_name):
    User = get_user_model()
    username = _allocate_username(login_username_for_club(club, display_name))
    user = User.objects.create_user(username=username, password=DEFAULT_PLAYER_PASSWORD)
    ClubMembership.objects.create(user=user, club=club)
    return user


def provision_player_login(player):
    """
    为已有球员开通登录账号并绑定。
    返回登录用户名。
    """
    if player.user_id:
        raise ValueError('该球员已有登录账号')
    if not player.club_id:
        raise ValueError('球员未归属俱乐部，无法开通账号')
    user = _create_club_member_user(player.club, player.name)
    player.user = user
    player.save(update_fields=['user'])
    return user.username


def find_club_player(club, name, nickname=''):
    """在本俱乐部按姓名/昵称查找球员。"""
    if not club:
        return None
    name = (name or '').strip()
    nickname = (nickname or '').strip()
    if name:
        player = Player.objects.filter(club=club, name=name).first()
        if player:
            return player
    if nickname:
        return Player.objects.filter(club=club, nickname=nickname).first()
    return None


def create_club_player(club, name, nickname='', gender='', phone='', create_account=True):
    """
    在本俱乐部新建球员。
    若 create_account 为 True，同时创建登录用户并加入俱乐部。
    返回 (player, login_username)。
    """
    if not club:
        raise ValueError('缺少俱乐部')
    name = (name or '').strip()
    nickname = (nickname or '').strip()
    if not name:
        raise ValueError('姓名不能为空')
    if find_club_player(club, name, nickname):
        raise ValueError('该俱乐部已有同名或同昵称球员')

    user = None
    login_username = ''
    if create_account:
        user = _create_club_member_user(club, name)
        login_username = user.username

    player = Player.objects.create(
        club=club,
        name=name,
        nickname=nickname,
        gender=gender or '',
        phone=phone or '',
        user=user,
    )
    return player, login_username


def get_or_create_club_player(club, name, nickname=''):
    """
    获取或创建本俱乐部球员。
    不存在时：创建登录用户（用户名=邀请码_拼音，密码 666666）并加入俱乐部。
    返回 (player, created, login_username)。
    """
    if not club:
        raise ValueError('缺少俱乐部')
    name = (name or '').strip()
    nickname = (nickname or '').strip()
    if not name:
        raise ValueError('姓名不能为空')

    existing = find_club_player(club, name, nickname)
    if existing:
        if nickname and not existing.nickname:
            existing.nickname = nickname
            existing.save(update_fields=['nickname'])
        return existing, False, existing.login_username

    user = _create_club_member_user(club, name)
    player = Player.objects.create(
        club=club,
        name=name,
        nickname=nickname,
        user=user,
    )
    return player, True, user.username
