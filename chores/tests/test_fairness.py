from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from chores.services.fairness import household_fairness
from chores.services.tracking import complete_occurrence
from chores.tests.factories import make_chore, make_household, make_member, make_occurrence


class FairnessTests(TestCase):
    def setUp(self):
        self.household = make_household()
        self.ada = make_member(self.household, display_name='Ada')
        self.bob = make_member(self.household, display_name='Bob')
        self.today = timezone.localdate()

    def _complete(self, member, weight, name):
        chore = make_chore(household=self.household, name=name, effort_weight=weight)
        occurrence = make_occurrence(chore, self.today)
        complete_occurrence(occurrence, member)

    def test_idle_household_is_fair_not_unfair(self):
        report = household_fairness(self.household)

        self.assertEqual(report.total_effort, 0)
        self.assertEqual(report.imbalance, 0.0)
        self.assertTrue(report.is_fair)

    def test_a_single_member_is_always_fair(self):
        solo = make_household(name='Studio')
        member = make_member(solo, display_name='Cass')
        chore = make_chore(household=solo, effort_weight=5)
        complete_occurrence(make_occurrence(chore, self.today), member)

        report = household_fairness(solo)

        self.assertEqual(report.imbalance, 0.0)
        self.assertTrue(report.is_fair)

    def test_equal_effort_at_equal_capacity_is_fair(self):
        self._complete(self.ada, 3, 'Vacuuming')
        self._complete(self.bob, 3, 'Laundry')

        report = household_fairness(self.household)

        self.assertEqual(report.total_effort, 6)
        self.assertAlmostEqual(report.imbalance, 0.0)
        self.assertTrue(report.is_fair)

    def test_counts_weighted_effort_not_chore_count(self):
        self._complete(self.ada, 5, 'Bathroom')
        self._complete(self.bob, 1, 'Trash A')
        self._complete(self.bob, 1, 'Trash B')
        self._complete(self.bob, 1, 'Trash C')

        report = household_fairness(self.household)
        ada = report.for_member(self.ada)
        bob = report.for_member(self.bob)

        self.assertEqual(ada.effort, 5)
        self.assertEqual(bob.effort, 3)
        self.assertTrue(ada.is_overloaded)
        self.assertFalse(bob.is_overloaded)

    def test_one_member_doing_everything_is_maximally_unfair(self):
        self._complete(self.ada, 4, 'Bathroom')

        report = household_fairness(self.household)

        self.assertAlmostEqual(report.imbalance, 0.5)
        self.assertFalse(report.is_fair)
        self.assertEqual(report.most_overloaded().member, self.ada)
        self.assertEqual(report.most_underloaded().member, self.bob)

    def test_lower_capacity_lowers_the_expected_share(self):
        self.bob.capacity = Decimal('0.50')
        self.bob.save(update_fields=['capacity'])
        self._complete(self.ada, 2, 'Vacuuming')
        self._complete(self.bob, 1, 'Trash')

        report = household_fairness(self.household)

        # Ada carries 2/3 of the effort and is expected to carry 2/3 of the load.
        self.assertAlmostEqual(report.imbalance, 0.0, places=6)
        self.assertTrue(report.is_fair)

    def test_zero_capacity_member_is_excused(self):
        self.bob.capacity = Decimal('0.00')
        self.bob.save(update_fields=['capacity'])
        self._complete(self.ada, 3, 'Vacuuming')

        report = household_fairness(self.household)
        bob = report.for_member(self.bob)

        self.assertEqual(bob.expected_share, 0.0)
        self.assertAlmostEqual(report.imbalance, 0.0)

    def test_work_outside_the_window_does_not_count(self):
        self._complete(self.ada, 5, 'Bathroom')
        occurrence = self.ada.completed_occurrences.first()
        occurrence.completed_at = timezone.now() - timezone.timedelta(days=60)
        occurrence.save(update_fields=['completed_at'])

        report = household_fairness(self.household, window_days=28)

        self.assertEqual(report.total_effort, 0)
