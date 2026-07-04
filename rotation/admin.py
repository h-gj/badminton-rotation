from django.contrib import admin

from rotation.models import Club, ClubMembership, Match, Player, Registration, Session


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'invite_code', 'created_at']
    search_fields = ['name', 'owner__username', 'invite_code']
    readonly_fields = ['invite_code']


@admin.register(ClubMembership)
class ClubMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'club', 'joined_at']
    list_filter = ['club']
    search_fields = ['user__username', 'club__name']


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['name', 'nickname', 'club', 'gender', 'phone', 'created_at']
    list_filter = ['club']
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
    list_display = ['title', 'club', 'event_date', 'status', 'courts', 'rounds', 'avoid_mixed_gender_doubles']
    list_filter = ['status', 'event_date', 'club']
    inlines = [RegistrationInline, MatchInline]


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = [
        'session', 'round_number', 'court_number', 'team1_label', 'team2_label',
        'score_team1', 'score_team2', 'is_completed',
    ]
    list_filter = ['session', 'is_completed']
