from django.contrib import admin

from rotation.models import Match, Player, Registration, Session


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['name', 'nickname', 'phone', 'created_at']
    search_fields = ['name', 'nickname', 'phone']


class RegistrationInline(admin.TabularInline):
    model = Registration
    extra = 0


class MatchInline(admin.TabularInline):
    model = Match
    extra = 0
    readonly_fields = ['round_number', 'court_number']


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'event_date', 'location', 'status', 'courts', 'rounds']
    list_filter = ['status', 'event_date']
    inlines = [RegistrationInline, MatchInline]


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = [
        'session', 'round_number', 'court_number', 'team1_label', 'team2_label',
        'score_team1', 'score_team2', 'is_completed',
    ]
    list_filter = ['session', 'is_completed']
