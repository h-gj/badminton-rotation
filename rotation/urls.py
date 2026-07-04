from django.urls import path

from rotation import views
from rotation import views_auth

urlpatterns = [
    path('', views.home, name='home'),
    path('accounts/register/', views_auth.register, name='register'),
    path('accounts/login/', views_auth.login_view, name='login'),
    path('accounts/logout/', views_auth.logout_view, name='logout'),
    path('accounts/profile/', views_auth.profile, name='profile'),
    path('accounts/profile/avatar/', views_auth.profile_update_avatar, name='profile_update_avatar'),
    path('club/setup/', views_auth.club_setup, name='club_setup'),
    path('club/create/', views_auth.club_create, name='club_create'),
    path('club/join/', views_auth.club_join, name='club_join'),
    path('sessions/', views.home, name='session_list'),
    path('sessions/create/', views.session_create, name='session_create'),
    path('sessions/import-wechat/', views.session_import_wechat, name='session_import_wechat'),
    path('sessions/import-wechat/parse/', views.session_import_wechat_parse, name='session_import_wechat_parse'),
    path('sessions/import-wechat/create/', views.session_import_wechat_create, name='session_import_wechat_create'),
    path('sessions/<int:pk>/', views.session_detail, name='session_detail'),
    path('sessions/<int:pk>/meta/', views.session_update_meta, name='session_update_meta'),
    path('sessions/<int:pk>/add-players/', views.session_add_players, name='session_add_players'),
    path('sessions/<int:pk>/register/', views.session_register, name='session_register'),
    path('sessions/<int:pk>/generate/', views.session_generate, name='session_generate'),
    path('sessions/<int:pk>/matches/', views.session_matches, name='session_matches'),
    path('sessions/<int:pk>/leaderboard/', views.session_leaderboard, name='session_leaderboard'),
    path('matches/<int:pk>/score/', views.match_score, name='match_score'),
    path('players/', views.player_list, name='player_list'),
    path('players/<int:pk>/', views.player_detail, name='player_detail'),
    path('players/<int:pk>/avatar/', views.player_update_avatar, name='player_update_avatar'),
    path('rankings/', views.rankings, name='rankings'),
]
