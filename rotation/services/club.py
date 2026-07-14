from django.db.models import Count, Q

from rotation.models import Club, ClubMembership, Player, Session


def is_site_admin(user):
    """站点管理员：可查看所有俱乐部数据（Django staff / superuser）。"""
    return user.is_authenticated and (user.is_superuser or user.is_staff)


def get_user_club(user):
    if not user.is_authenticated:
        return None
    owned = Club.objects.filter(owner=user).first()
    if owned:
        return owned
    membership = (
        ClubMembership.objects.filter(user=user)
        .select_related('club')
        .first()
    )
    return membership.club if membership else None


def user_has_club(user):
    return get_user_club(user) is not None


def user_owns_club(user):
    if not user.is_authenticated:
        return False
    return Club.objects.filter(owner=user).exists()


def user_joined_club(user):
    if not user.is_authenticated:
        return False
    return ClubMembership.objects.filter(user=user).exists()


def user_club_scope(user):
    """返回用于筛选的俱乐部；管理员返回 None 表示不限俱乐部。"""
    if is_site_admin(user):
        return None
    return get_user_club(user)


def user_session_queryset(user):
    """当前用户可见的活动：管理员看全部，其余仅限其创建或加入的俱乐部。"""
    qs = Session.objects.annotate(reg_count=Count('registrations'))
    if is_site_admin(user):
        return qs.order_by('-event_date', '-created_at')
    club = get_user_club(user)
    if not club:
        return Session.objects.none()
    return qs.filter(club_id=club.pk).order_by('-event_date', '-created_at')


def user_player_queryset(user, q=''):
    """当前用户可见的球员：管理员看全部，其余仅限其俱乐部。"""
    if is_site_admin(user):
        qs = Player.objects.all()
    else:
        club = get_user_club(user)
        if not club:
            return Player.objects.none()
        qs = Player.objects.filter(club_id=club.pk)
    qs = qs.annotate(session_count=Count('registrations')).order_by('-session_count', 'name')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(nickname__icontains=q))
    return qs


def user_can_access_session(user, session):
    if is_site_admin(user):
        return True
    club = get_user_club(user)
    if not club or not session.club_id:
        return False
    return session.club_id == club.pk


def user_can_access_player(user, player):
    if is_site_admin(user):
        return True
    club = get_user_club(user)
    if not club or not player.club_id:
        return False
    return player.club_id == club.pk


def _club_owner_display(club):
    player = Player.objects.filter(user=club.owner, club=club).first()
    if player:
        return player.display_name
    full_name = club.owner.get_full_name()
    return full_name or club.owner.username


def _club_member_count(club):
    count = club.memberships.count()
    if not club.memberships.filter(user_id=club.owner_id).exists():
        count += 1
    return count


def can_access_manage(user):
    """站点管理员或俱乐部创建者可进入管理后台。"""
    if not user.is_authenticated:
        return False
    return is_site_admin(user) or user_owns_club(user)


def user_can_manage_club(user, club):
    if is_site_admin(user):
        return True
    return user.is_authenticated and club.owner_id == user.id


def user_can_manage_player(user, player):
    if is_site_admin(user):
        return True
    if not user.is_authenticated or not player.club_id:
        return False
    owned = Club.objects.filter(owner=user).first()
    return owned is not None and player.club_id == owned.pk


def manage_club_queryset(user):
    qs = Club.objects.select_related('owner').annotate(
        player_count=Count('players'),
        member_count=Count('memberships'),
    )
    if is_site_admin(user):
        return qs.order_by('name')
    owned = Club.objects.filter(owner=user).first()
    if owned:
        return qs.filter(pk=owned.pk)
    return Club.objects.none()


def manage_player_queryset(user, club_id=None, q=''):
    if is_site_admin(user):
        qs = Player.objects.select_related('club', 'user')
        if club_id:
            qs = qs.filter(club_id=club_id)
    else:
        owned = Club.objects.filter(owner=user).first()
        if not owned:
            return Player.objects.none()
        qs = Player.objects.filter(club=owned).select_related('club', 'user')
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(nickname__icontains=q)
            | Q(phone__icontains=q)
            | Q(user__username__icontains=q)
        )
    return qs.order_by('name')


def get_club_page_context(user):
    club = get_user_club(user)
    admin = is_site_admin(user)
    owned_club = Club.objects.filter(owner=user).first() if user.is_authenticated else None
    club_info = None
    if club:
        club = Club.objects.select_related('owner').get(pk=club.pk)
        club_info = {
            'created_at': club.created_at,
            'owner_display': _club_owner_display(club),
            'member_count': _club_member_count(club),
        }
    return {
        'club': club,
        'club_info': club_info,
        'owned_club': owned_club,
        'is_admin': admin,
    }
