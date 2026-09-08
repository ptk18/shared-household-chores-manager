from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from chores.models import ChoreOccurrence
from chores.permissions import (
    admin_required,
    can_claim,
    can_complete,
    member_required,
)
from chores.services.assignment import recommend_for
from chores.services.fairness import household_fairness
from chores.services.tracking import (
    TransitionError,
    claim_occurrence,
    complete_occurrence,
)


def _household_occurrences(household):
    return ChoreOccurrence.objects.filter(
        chore__household=household
    ).select_related('chore', 'assigned_to', 'completed_by')


@member_required
def dashboard(request):
    """
    The plan section 6 command centre: Today, My chores, Household health, Overdue.

    One screen answering "what needs doing, what is mine, and are we square?"
    """
    member = request.member
    today = timezone.localdate()
    occurrences = _household_occurrences(member.household)
    open_statuses = ChoreOccurrence.OPEN_STATUSES

    due_today = occurrences.filter(due_date=today, status__in=open_statuses)
    mine = occurrences.filter(assigned_to=member, status__in=open_statuses)
    overdue = occurrences.filter(status=ChoreOccurrence.Status.OVERDUE)
    unclaimed = occurrences.filter(assigned_to__isnull=True, status__in=open_statuses)

    return render(
        request,
        'chores/dashboard.html',
        {
            'member': member,
            'household': member.household,
            'today': today,
            'due_today': due_today,
            'my_chores': mine,
            'overdue': overdue,
            'unclaimed': unclaimed,
            'fairness': household_fairness(member.household),
        },
    )


@member_required
def occurrence_detail(request, pk):
    """A single chore instance, with the engine's ranked suggestions."""
    occurrence = get_object_or_404(
        _household_occurrences(request.member.household), pk=pk
    )
    return render(
        request,
        'chores/occurrence_detail.html',
        {
            'occurrence': occurrence,
            'recommendations': recommend_for(occurrence),
            'can_complete': can_complete(request.member, occurrence),
            'can_claim': can_claim(request.member, occurrence),
        },
    )


@require_POST
@member_required
def complete(request, pk):
    occurrence = get_object_or_404(
        _household_occurrences(request.member.household), pk=pk
    )
    if not can_complete(request.member, occurrence):
        messages.error(request, 'That chore belongs to someone else.')
        return redirect('chores:dashboard')

    try:
        complete_occurrence(occurrence, request.member)
    except TransitionError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'Nice — {occurrence.chore.name} is done.')
    return redirect('chores:dashboard')


@require_POST
@member_required
def claim(request, pk):
    occurrence = get_object_or_404(
        _household_occurrences(request.member.household), pk=pk
    )
    if not can_claim(request.member, occurrence):
        messages.error(request, 'That chore is not available to claim.')
        return redirect('chores:dashboard')

    try:
        claim_occurrence(occurrence, request.member)
    except TransitionError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'{occurrence.chore.name} is yours.')
    return redirect('chores:dashboard')


@admin_required
def household_settings(request):
    """Household-level configuration. Admins only (plan section 8)."""
    household = request.member.household
    return render(
        request,
        'chores/household_settings.html',
        {
            'household': household,
            'members': household.members.all(),
            'chores': household.chores.all(),
        },
    )
