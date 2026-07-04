from rotation.services.club import get_user_club, is_site_admin


def site_context(request):
    club = getattr(request, 'club', None)
    admin = is_site_admin(request.user) if request.user.is_authenticated else False
    return {
        'user_club': club,
        'is_site_admin': admin,
        'can_create_session': bool(
            request.user.is_authenticated and club is not None
        ),
    }
