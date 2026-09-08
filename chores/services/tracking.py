"""Completion and overdue transitions for chore occurrences."""

from django.db import transaction
from django.utils import timezone

from chores.models import ChoreOccurrence


class TransitionError(Exception):
    """Raised when a requested status change is not legal for an occurrence."""


@transaction.atomic
def complete_occurrence(occurrence, member, when=None):
    """
    Mark `occurrence` done, crediting `member` with the effort.

    Credit follows whoever did the work, not whoever was assigned — a member who
    covers for someone else earns the fairness credit for it (plan section 4).
    Overdue occurrences can still be completed; that is the point of the gentle
    escalation loop rather than a punitive one.
    """
    if occurrence.status == ChoreOccurrence.Status.DONE:
        raise TransitionError(f'{occurrence} is already done.')
    if occurrence.status == ChoreOccurrence.Status.SKIPPED:
        raise TransitionError(f'{occurrence} was skipped and cannot be completed.')

    occurrence.status = ChoreOccurrence.Status.DONE
    occurrence.completed_at = when or timezone.now()
    occurrence.completed_by = member
    occurrence.save(update_fields=['status', 'completed_at', 'completed_by'])
    return occurrence


@transaction.atomic
def claim_occurrence(occurrence, member):
    """Assign an open, unassigned occurrence to `member`."""
    if not occurrence.is_open:
        raise TransitionError(f'{occurrence} is not open to claim.')
    if occurrence.assigned_to_id is not None:
        raise TransitionError(f'{occurrence} is already assigned.')

    occurrence.assigned_to = member
    occurrence.save(update_fields=['assigned_to'])
    return occurrence


@transaction.atomic
def skip_occurrence(occurrence, reason=''):
    """Retire an occurrence without completing it. Earns no fairness credit."""
    if occurrence.status == ChoreOccurrence.Status.DONE:
        raise TransitionError(f'{occurrence} is already done.')

    occurrence.status = ChoreOccurrence.Status.SKIPPED
    occurrence.save(update_fields=['status'])
    return occurrence


def mark_overdue(today=None):
    """
    Flip pending occurrences whose due date has passed to overdue.

    An occurrence due today is not overdue — the member still has the day to do
    it. Only strictly-past due dates escalate. Returns the number updated.
    """
    today = today or timezone.localdate()
    return ChoreOccurrence.objects.filter(
        status=ChoreOccurrence.Status.PENDING,
        due_date__lt=today,
    ).update(status=ChoreOccurrence.Status.OVERDUE)
