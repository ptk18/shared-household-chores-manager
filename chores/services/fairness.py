"""
Fairness measurement over completed work.

Fairness here is *weighted effort relative to capacity*, not chore count — plan
section 4. Two members who each did five chores are not necessarily square if one
scrubbed the bathroom five times and the other emptied the bin.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from chores.models import ChoreOccurrence, Member

DEFAULT_WINDOW_DAYS = 28


@dataclass(frozen=True)
class MemberEffort:
    """One member's standing in the fairness window."""

    member: Member
    effort: int
    capacity: Decimal
    actual_share: float
    expected_share: float

    @property
    def member_id(self):
        return self.member.pk

    @property
    def deviation(self):
        """Positive means carrying more than their share; negative means less."""
        return self.actual_share - self.expected_share

    @property
    def is_overloaded(self):
        return self.deviation > 0


@dataclass(frozen=True)
class FairnessReport:
    """Household-level fairness snapshot over a fixed window."""

    entries: list
    total_effort: int
    window_days: int

    @property
    def imbalance(self):
        """
        How unfairly the load is spread, from 0.0 (perfect) to 1.0 (one person
        carries everything nobody else should).

        Half the sum of absolute deviations: the fraction of total effort that
        would have to change hands to make the household square. Zero when
        nothing has been done — an idle household is not an unfair one.
        """
        if self.total_effort == 0 or len(self.entries) < 2:
            return 0.0
        return sum(abs(entry.deviation) for entry in self.entries) / 2

    @property
    def is_fair(self):
        """Under a tenth of the load misplaced reads as fair in practice."""
        return self.imbalance < 0.1

    def most_overloaded(self):
        return max(self.entries, key=lambda e: e.deviation, default=None)

    def most_underloaded(self):
        return min(self.entries, key=lambda e: e.deviation, default=None)

    def for_member(self, member):
        return next((e for e in self.entries if e.member_id == member.pk), None)


def completed_effort(member, since, until=None):
    """Total weighted effort `member` completed in the window."""
    until = until or timezone.now()
    total = ChoreOccurrence.objects.filter(
        completed_by=member,
        status=ChoreOccurrence.Status.DONE,
        completed_at__gte=since,
        completed_at__lte=until,
    ).aggregate(total=Sum('chore__effort_weight'))['total']
    return total or 0


def outstanding_effort(household):
    """
    Weighted effort each member is *holding but has not finished*, by member id.

    Distinct from completed effort: this is work already committed to somebody.
    The assignment engine needs it, because otherwise a batch of assignments made
    in one pass is invisible to the next one and the whole rota lands on whoever
    sorts first.
    """
    rows = (
        ChoreOccurrence.objects.filter(
            assigned_to__household=household,
            status__in=ChoreOccurrence.OPEN_STATUSES,
        )
        .values('assigned_to')
        .annotate(total=Sum('chore__effort_weight'))
    )
    return {row['assigned_to']: row['total'] or 0 for row in rows}


def household_fairness(household, window_days=DEFAULT_WINDOW_DAYS, now=None):
    """
    Score every member of `household` over a rolling window.

    A member with zero capacity is excused: they are reported with an expected
    share of zero, so doing nothing does not register as unfairness against them.
    """
    now = now or timezone.now()
    since = now - timedelta(days=window_days)

    members = list(household.members.all())
    efforts = {m.pk: completed_effort(m, since, now) for m in members}
    total_effort = sum(efforts.values())
    total_capacity = sum((m.capacity for m in members), Decimal('0'))

    entries = []
    for member in members:
        effort = efforts[member.pk]
        actual = effort / total_effort if total_effort else 0.0
        expected = (
            float(member.capacity / total_capacity) if total_capacity else 0.0
        )
        entries.append(
            MemberEffort(
                member=member,
                effort=effort,
                capacity=member.capacity,
                actual_share=actual,
                expected_share=expected,
            )
        )

    entries.sort(key=lambda e: e.deviation, reverse=True)
    return FairnessReport(
        entries=entries, total_effort=total_effort, window_days=window_days
    )
