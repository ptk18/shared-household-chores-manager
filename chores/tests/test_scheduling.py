from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from chores.models import Chore, ChoreOccurrence
from chores.services.scheduling import due_dates_for, generate_occurrences
from chores.tests.factories import make_chore, make_household


class DueDateRuleTests(TestCase):
    def setUp(self):
        self.household = make_household()
        self.start = date(2026, 3, 2)  # a Monday
        self.end = self.start + timedelta(days=13)

    def _chore_anchored_on(self, anchor, frequency):
        chore = make_chore(household=self.household, frequency=frequency)
        Chore.objects.filter(pk=chore.pk).update(
            created_at=timezone.make_aware(
                timezone.datetime.combine(anchor, timezone.datetime.min.time())
            )
        )
        chore.refresh_from_db()
        return chore

    def test_daily_fills_every_day_in_the_window(self):
        chore = self._chore_anchored_on(self.start, Chore.Frequency.DAILY)
        dates = due_dates_for(chore, self.start, self.end)
        self.assertEqual(len(dates), 14)
        self.assertEqual(dates[0], self.start)
        self.assertEqual(dates[-1], self.end)

    def test_weekly_repeats_on_the_anchor_weekday(self):
        chore = self._chore_anchored_on(date(2026, 3, 4), Chore.Frequency.WEEKLY)
        dates = due_dates_for(chore, self.start, self.end)
        self.assertEqual(dates, [date(2026, 3, 4), date(2026, 3, 11)])
        self.assertTrue(all(d.weekday() == 2 for d in dates))

    def test_monthly_clamps_to_short_months(self):
        chore = self._chore_anchored_on(date(2026, 1, 31), Chore.Frequency.MONTHLY)
        dates = due_dates_for(chore, date(2026, 2, 1), date(2026, 3, 31))
        self.assertEqual(dates, [date(2026, 2, 28), date(2026, 3, 31)])

    def test_one_off_yields_a_single_date_then_never_again(self):
        chore = self._chore_anchored_on(self.start, Chore.Frequency.ONCE)
        self.assertEqual(len(due_dates_for(chore, self.start, self.end)), 1)

        ChoreOccurrence.objects.create(chore=chore, due_date=self.start)
        self.assertEqual(due_dates_for(chore, self.start, self.end), [])


class GenerateOccurrencesTests(TestCase):
    def setUp(self):
        self.household = make_household()

    def test_running_twice_creates_no_duplicates(self):
        make_chore(household=self.household, frequency=Chore.Frequency.DAILY)

        first = generate_occurrences(horizon_days=6)
        second = generate_occurrences(horizon_days=6)

        self.assertEqual(first, 7)
        self.assertEqual(second, 0)
        self.assertEqual(ChoreOccurrence.objects.count(), 7)

    def test_inactive_chores_generate_nothing(self):
        make_chore(household=self.household, frequency=Chore.Frequency.DAILY, is_active=False)
        self.assertEqual(generate_occurrences(horizon_days=6), 0)

    def test_generation_can_be_scoped_to_one_household(self):
        other = make_household(name='Cabin')
        make_chore(household=self.household, frequency=Chore.Frequency.DAILY)
        make_chore(household=other, frequency=Chore.Frequency.DAILY)

        generate_occurrences(household=self.household, horizon_days=3)

        self.assertEqual(
            ChoreOccurrence.objects.filter(chore__household=other).count(), 0
        )
        self.assertEqual(
            ChoreOccurrence.objects.filter(chore__household=self.household).count(), 4
        )

    def test_regeneration_preserves_a_completed_occurrence(self):
        chore = make_chore(household=self.household, frequency=Chore.Frequency.DAILY)
        generate_occurrences(horizon_days=6)
        occurrence = chore.occurrences.first()
        occurrence.status = ChoreOccurrence.Status.DONE
        occurrence.save(update_fields=['status'])

        generate_occurrences(horizon_days=6)

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.status, ChoreOccurrence.Status.DONE)
