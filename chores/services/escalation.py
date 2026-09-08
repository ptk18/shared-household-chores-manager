"""
The gentle escalation ladder (plan section 5).

Design stance: escalation informs, it does not punish. Nothing here reassigns
work away from someone or docks their fairness score. The strongest rung simply
*offers* the chore back to the household, and only after several days — the goal
is completion with minimal friction, not enforcement.

Each rung fires at most once per occurrence, recorded as an EscalationEvent.
"""

from dataclasses import dataclass

from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from chores.models import ChoreOccurrence, EscalationEvent

Level = EscalationEvent.Level

# Days relative to the due date at which each rung becomes appropriate.
# Negative is before the due date.
REMINDER_LEAD_DAYS = 1
HOUSEHOLD_NUDGE_AFTER_DAYS = 2
REASSIGN_OFFER_AFTER_DAYS = 4


@dataclass(frozen=True)
class Notice:
    """A message the ladder decided to send."""

    occurrence: ChoreOccurrence
    level: int
    subject: str
    body: str
    recipients: list

    @property
    def level_label(self):
        return Level(self.level).label


def _member_emails(members):
    return [m.user.email for m in members if m.user.email]


def _assignee_notice(occurrence, level, subject, body):
    assignee = occurrence.assigned_to
    recipients = _member_emails([assignee]) if assignee else []
    return Notice(
        occurrence=occurrence,
        level=level,
        subject=subject,
        body=body,
        recipients=recipients,
    )


def due_rung(occurrence, today):
    """
    The single rung `occurrence` has reached today, or None.

    Returns the *highest* applicable rung rather than replaying the whole ladder,
    so a chore discovered late does not fire four messages at once.
    """
    if occurrence.status not in ChoreOccurrence.OPEN_STATUSES:
        return None

    days_late = (today - occurrence.due_date).days

    if days_late >= REASSIGN_OFFER_AFTER_DAYS:
        return Level.REASSIGN_OFFER
    if days_late >= HOUSEHOLD_NUDGE_AFTER_DAYS:
        return Level.HOUSEHOLD_NUDGE
    if days_late >= 1:
        return Level.OVERDUE_NOTICE
    if days_late == 0:
        return Level.DUE_TODAY
    if days_late >= -REMINDER_LEAD_DAYS:
        return Level.REMINDER
    return None


def build_notice(occurrence, level):
    """Compose the message for one rung. Tone escalates in visibility, not blame."""
    name = occurrence.chore.name
    who = occurrence.assigned_to.display_name if occurrence.assigned_to else 'Nobody'
    household = occurrence.chore.household

    if level == Level.REMINDER:
        return _assignee_notice(
            occurrence,
            level,
            f'{name} is coming up',
            f'A friendly heads-up: {name} is due {occurrence.due_date:%A}.',
        )

    if level == Level.DUE_TODAY:
        return _assignee_notice(
            occurrence,
            level,
            f'{name} is due today',
            f'{name} is due today. Mark it done when you get to it.',
        )

    if level == Level.OVERDUE_NOTICE:
        return _assignee_notice(
            occurrence,
            level,
            f'{name} is overdue',
            f'{name} was due {occurrence.due_date:%A}. No rush — just a nudge.',
        )

    if level == Level.HOUSEHOLD_NUDGE:
        return Notice(
            occurrence=occurrence,
            level=level,
            subject=f'{name} is still outstanding',
            body=(
                f'{name} has been outstanding since {occurrence.due_date:%A}. '
                f'{who} has it. If someone else has a moment, lending a hand helps.'
            ),
            recipients=_member_emails(household.members.all()),
        )

    return Notice(
        occurrence=occurrence,
        level=level,
        subject=f'{name} is open for anyone',
        body=(
            f'{name} has been outstanding for several days and is now open for '
            'anyone in the household to pick up.'
        ),
        recipients=_member_emails(household.members.all()),
    )


@transaction.atomic
def apply_rung(occurrence, level):
    """
    Record the rung and perform its side effect.

    Only the top rung changes state, and only by *releasing* the chore: the
    assignment is cleared so anyone can claim it. The occurrence itself is never
    cancelled or marked against the member.
    """
    if level == Level.REASSIGN_OFFER and occurrence.assigned_to_id is not None:
        occurrence.assigned_to = None
        occurrence.save(update_fields=['assigned_to'])

    EscalationEvent.objects.create(
        occurrence=occurrence,
        level=level,
        detail=Level(level).label,
    )


def escalate(today=None, send=True):
    """
    Walk every open occurrence one rung, at most, and return the notices sent.

    Idempotent within a day: a rung already recorded for an occurrence never
    fires again, so running this hourly is as safe as running it nightly.
    """
    today = today or timezone.localdate()

    occurrences = (
        ChoreOccurrence.objects.filter(status__in=ChoreOccurrence.OPEN_STATUSES)
        .select_related('chore', 'chore__household', 'assigned_to', 'assigned_to__user')
        .prefetch_related('escalations')
    )

    notices = []
    for occurrence in occurrences:
        level = due_rung(occurrence, today)
        if level is None:
            continue
        if any(e.level == level for e in occurrence.escalations.all()):
            continue

        notice = build_notice(occurrence, level)
        apply_rung(occurrence, level)
        notices.append(notice)

        if send and notice.recipients:
            send_mail(
                subject=notice.subject,
                message=notice.body,
                from_email=None,
                recipient_list=notice.recipients,
                fail_silently=True,
            )

    return notices
