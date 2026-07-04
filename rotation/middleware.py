from rotation.services.club import get_user_club


class ClubMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.club = get_user_club(request.user) if request.user.is_authenticated else None
        return self.get_response(request)
