"""Turn recurring chore definitions into dated occurrences."""

import calendar
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from chores.models import Chore, ChoreOccurrence

DEFAULT_HORIZON_DAYS = 14


def _daily_dates(start, end, _anchor):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _weekly_dates(start, end, anchor):
    """Every occurrence of the anchor's weekday within the window."""
    offset = (anchor.weekday() - start.weekday()) % 7
    current = start + timedelta(days=offset)
    while current <= end:
        yield current
        current += timedelta(days=7)


def _monthly_dates(start, end, anchor):
    """
    The anchor's day-of-month within the window, clamped to short months.

    A chore anchored on the 31st falls on the 28th/29th in February rather than
    silently skipping the month.
    """
    year, month = start.year, start.month
    while True:
        last_day = calendar.monthrange(year, month)[1]
        candidate = date(year, month, min(anchor.day, last_day))
        if candidate > end:
            return
        if candidate >= start:
            yield candidate
        month += 1
        if month > 12:
            year, month = year + 1, 1


_DATE_RULES = {
    Chore.Frequency.DAILY: _daily_dates,
    Chore.Frequency.WEEKLY: _weekly_dates,
    Chore.Frequency.MONTHLY: _monthly_dates,
}


def due_dates_for(chore, start, end):
    """
    The dates `chore` should fall due on within [start, end], inclusive.

    One-off chores yield a single date and only while they have no occurrence
    yet — re-running generation must never resurrect a completed one-off.
    """
    if chore.frequency == Chore.Frequency.ONCE:
        if chore.occurrences.exists():
            return []
        return [max(start, timezone.localdate(chore.created_at))]

    anchor = timezone.localdate(chore.created_at)
    return list(_DATE_RULES[chore.frequency](start, end, anchor))


@transaction.atomic
def generate_occurrences(household=None, start=None, horizon_days=DEFAULT_HORIZON_DAYS):
    """
    Create missing occurrences for every active chore, out to the horizon.

    Idempotent: existing (chore, due_date) pairs are left untouched, so running
    this daily from cron never duplicates work or overwrites a completion.
    Returns the number of occurrences created.
    """
    start = start or timezone.localdate()
    end = start + timedelta(days=horizon_days)

    chores = Chore.objects.filter(is_active=True).select_related('household')
    if household is not None:
        chores = chores.filter(household=household)

    pending = []
    for chore in chores:
        wanted = set(due_dates_for(chore, start, end))
        if not wanted:
            continue
        existing = set(
            chore.occurrences.filter(due_date__in=wanted).values_list(
                'due_date', flat=True
            )
        )
        pending.extend(
            ChoreOccurrence(chore=chore, due_date=due_date)
            for due_date in sorted(wanted - existing)
        )

    if not pending:
        return 0

    # ignore_conflicts guards the race where two schedulers overlap; the unique
    # constraint on (chore, due_date) is the real authority.
    ChoreOccurrence.objects.bulk_create(pending, ignore_conflicts=True)
    return len(pending)
