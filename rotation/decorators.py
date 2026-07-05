from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


from rotation.services.club import get_user_club, is_site_admin


def login_required_view(view):
    @login_required(login_url='login')
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        return view(request, *args, **kwargs)

    return wrapper


def require_club(view):
    @login_required_view
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.club and not is_site_admin(request.user):
            messages.info(request, '请先创建或加入俱乐部')
            return redirect('club_home')
        return view(request, *args, **kwargs)

    return wrapper
