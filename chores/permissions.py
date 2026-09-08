"""
Role-based access rules (plan section 8).

Policy lives here, mechanism lives in `services.tracking`. The service layer will
happily let anyone complete anything — that is what makes covering for a
housemate possible — so these functions decide who is *allowed* to ask.
"""

from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from chores.models import Member


def get_member(user):
    """The Member profile for `user`, or None if they have not joined a household."""
    if not user.is_authenticated:
        return None
    return Member.objects.filter(user=user).select_related('household').first()


def in_same_household(member, occurrence):
    return member is not None and occurrence.chore.household_id == member.household_id


def can_manage_household(member):
    """Only admins change household-level settings and membership."""
    return member is not None and member.role == Member.Role.ADMIN


def can_complete(member, occurrence):
    """
    Members complete their own work and pick up unclaimed work.

    Completing a chore assigned to somebody else is an admin action: it rewrites
    who earned the fairness credit, so it should not be unilateral.
    """
    if not in_same_household(member, occurrence):
        return False
    if occurrence.assigned_to_id in (None, member.pk):
        return True
    return can_manage_household(member)


def can_claim(member, occurrence):
    """Guests do not take on new work; they only finish what was given to them."""
    if not in_same_household(member, occurrence):
        return False
    if member.role == Member.Role.GUEST:
        return False
    return occurrence.assigned_to_id is None and occurrence.is_open


def member_required(view):
    """Resolve request.member, or send the caller somewhere useful."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        member = get_member(request.user)
        if member is None:
            raise PermissionDenied('You are not a member of any household.')
        request.member = member
        return view(request, *args, **kwargs)

    return wrapper


def admin_required(view):
    """Household-admin gate, layered on top of member_required."""

    @wraps(view)
    @member_required
    def wrapper(request, *args, **kwargs):
        if not can_manage_household(request.member):
            raise PermissionDenied('Only household admins can do that.')
        return view(request, *args, **kwargs)

    return wrapper
