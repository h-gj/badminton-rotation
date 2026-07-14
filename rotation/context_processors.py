from rotation.services.club import can_access_manage, get_user_club, is_site_admin


def _nav_active(request):
    if not request.user.is_authenticated:
        return {'nav_active_sessions': False, 'nav_active_club': False, 'nav_active_create': False}
    path = request.path
    if '/sessions/create' in path or '/sessions/import-wechat' in path:
        return {'nav_active_sessions': False, 'nav_active_club': False, 'nav_active_create': True}
    if path.startswith('/club/'):
        return {'nav_active_sessions': False, 'nav_active_club': True, 'nav_active_create': False}
    if path.startswith('/manage/'):
        return {'nav_active_sessions': False, 'nav_active_club': False, 'nav_active_create': False}
    if path == '/' or (path.startswith('/sessions/') and '/sessions/create' not in path):
        return {'nav_active_sessions': True, 'nav_active_club': False, 'nav_active_create': False}
    return {'nav_active_sessions': False, 'nav_active_club': False, 'nav_active_create': False}


def site_context(request):
    club = getattr(request, 'club', None)
    admin = is_site_admin(request.user) if request.user.is_authenticated else False
    can_manage = can_access_manage(request.user) if request.user.is_authenticated else False
    return {
        'user_club': club,
        'is_site_admin': admin,
        'can_access_manage': can_manage,
        'can_create_session': bool(
            request.user.is_authenticated and club is not None
        ),
        **_nav_active(request),
    }
