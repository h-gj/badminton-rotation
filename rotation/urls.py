from django.urls import path

from rotation import views

urlpatterns = [
    path('', views.home, name='home'),
    path('sessions/create/', views.session_create, name='session_create'),
    path('sessions/<int:pk>/', views.session_detail, name='session_detail'),
    path('sessions/<int:pk>/register/', views.session_register, name='session_register'),
    path('sessions/<int:pk>/generate/', views.session_generate, name='session_generate'),
    path('sessions/<int:pk>/matches/', views.session_matches, name='session_matches'),
    path('sessions/<int:pk>/leaderboard/', views.session_leaderboard, name='session_leaderboard'),
    path('matches/<int:pk>/score/', views.match_score, name='match_score'),
    path('players/', views.player_list, name='player_list'),
    path('players/<int:pk>/', views.player_detail, name='player_detail'),
]
