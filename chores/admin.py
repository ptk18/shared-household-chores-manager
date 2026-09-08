from django.contrib import admin

from chores.models import (
    Availability,
    Chore,
    ChoreOccurrence,
    ChorePreference,
    ChoreTemplate,
    EscalationEvent,
    Household,
    Member,
    MemberSkill,
)


class ChorePreferenceInline(admin.TabularInline):
    model = ChorePreference
    extra = 0
    autocomplete_fields = ['chore']


class AvailabilityInline(admin.TabularInline):
    model = Availability
    extra = 0


class MemberSkillInline(admin.TabularInline):
    model = MemberSkill
    extra = 0
    autocomplete_fields = ['chore']


class MemberInline(admin.TabularInline):
    model = Member
    extra = 0
    fields = ['user', 'display_name', 'role']


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ['name', 'member_count', 'chore_count', 'created_at']
    search_fields = ['name']
    inlines = [MemberInline]

    @admin.display(description='Members')
    def member_count(self, household):
        return household.members.count()

    @admin.display(description='Chores')
    def chore_count(self, household):
        return household.chores.count()


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'household', 'role', 'joined_at']
    list_filter = ['role', 'household']
    search_fields = ['display_name', 'user__username']
    autocomplete_fields = ['user']
    inlines = [ChorePreferenceInline, AvailabilityInline, MemberSkillInline]


@admin.register(Chore)
class ChoreAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'household',
        'category',
        'frequency',
        'effort_weight',
        'is_active',
    ]
    list_filter = ['household', 'category', 'frequency', 'is_active']
    search_fields = ['name']
    list_editable = ['effort_weight', 'is_active']


@admin.register(ChoreOccurrence)
class ChoreOccurrenceAdmin(admin.ModelAdmin):
    list_display = ['chore', 'due_date', 'status', 'assigned_to', 'completed_by']
    list_filter = ['status', 'due_date', 'chore__household']
    search_fields = ['chore__name']
    date_hierarchy = 'due_date'
    autocomplete_fields = ['chore', 'assigned_to', 'completed_by']


@admin.register(ChoreTemplate)
class ChoreTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'category',
        'default_effort_weight',
        'default_frequency',
        'estimated_minutes',
    ]
    list_filter = ['category', 'default_frequency']
    search_fields = ['name']


@admin.register(EscalationEvent)
class EscalationEventAdmin(admin.ModelAdmin):
    """Read-only: the ladder is written by the escalation service, not by hand."""

    list_display = ['occurrence', 'level', 'sent_at']
    list_filter = ['level', 'sent_at']
    readonly_fields = ['occurrence', 'level', 'sent_at', 'detail']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
