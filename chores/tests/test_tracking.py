from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from chores.models import ChoreOccurrence
from chores.services.tracking import (
    TransitionError,
    claim_occurrence,
    complete_occurrence,
    mark_overdue,
    skip_occurrence,
)
from chores.tests.factories import make_chore, make_household, make_member, make_occurrence


class CompletionTests(TestCase):
    def setUp(self):
        self.household = make_household()
        self.ada = make_member(self.household, display_name='Ada')
        self.bob = make_member(self.household, display_name='Bob')
        self.chore = make_chore(household=self.household)
        self.today = timezone.localdate()

    def test_completing_stamps_who_and_when(self):
        occurrence = make_occurrence(self.chore, self.today, assigned_to=self.ada)

        complete_occurrence(occurrence, self.ada)

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.status, ChoreOccurrence.Status.DONE)
        self.assertEqual(occurrence.completed_by, self.ada)
        self.assertIsNotNone(occurrence.completed_at)

    def test_credit_follows_the_doer_not_the_assignee(self):
        occurrence = make_occurrence(self.chore, self.today, assigned_to=self.ada)

        complete_occurrence(occurrence, self.bob)

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.assigned_to, self.ada)
        self.assertEqual(occurrence.completed_by, self.bob)

    def test_an_overdue_chore_can_still_be_completed(self):
        occurrence = make_occurrence(
            self.chore,
            self.today - timedelta(days=3),
            status=ChoreOccurrence.Status.OVERDUE,
        )

        complete_occurrence(occurrence, self.ada)

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.status, ChoreOccurrence.Status.DONE)

    def test_double_completion_is_refused(self):
        occurrence = make_occurrence(self.chore, self.today)
        complete_occurrence(occurrence, self.ada)

        with self.assertRaises(TransitionError):
            complete_occurrence(occurrence, self.bob)

    def test_a_skipped_chore_cannot_be_completed(self):
        occurrence = make_occurrence(self.chore, self.today)
        skip_occurrence(occurrence)

        with self.assertRaises(TransitionError):
            complete_occurrence(occurrence, self.ada)


class ClaimTests(TestCase):
    def setUp(self):
        self.household = make_household()
        self.ada = make_member(self.household, display_name='Ada')
        self.bob = make_member(self.household, display_name='Bob')
        self.chore = make_chore(household=self.household)
        self.today = timezone.localdate()

    def test_claiming_an_open_unassigned_occurrence(self):
        occurrence = make_occurrence(self.chore, self.today)

        claim_occurrence(occurrence, self.ada)

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.assigned_to, self.ada)

    def test_cannot_claim_what_someone_already_holds(self):
        occurrence = make_occurrence(self.chore, self.today, assigned_to=self.ada)

        with self.assertRaises(TransitionError):
            claim_occurrence(occurrence, self.bob)

    def test_cannot_claim_a_finished_occurrence(self):
        occurrence = make_occurrence(self.chore, self.today)
        complete_occurrence(occurrence, self.ada)

        with self.assertRaises(TransitionError):
            claim_occurrence(occurrence, self.bob)


class OverdueSweepTests(TestCase):
    def setUp(self):
        self.chore = make_chore()
        self.today = timezone.localdate()

    def test_due_today_is_not_yet_overdue(self):
        occurrence = make_occurrence(self.chore, self.today)

        mark_overdue(today=self.today)

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.status, ChoreOccurrence.Status.PENDING)

    def test_due_yesterday_is_overdue(self):
        occurrence = make_occurrence(self.chore, self.today - timedelta(days=1))

        self.assertEqual(mark_overdue(today=self.today), 1)

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.status, ChoreOccurrence.Status.OVERDUE)

    def test_the_sweep_never_touches_finished_work(self):
        done = make_occurrence(self.chore, self.today - timedelta(days=5))
        complete_occurrence(done, make_member(self.chore.household))

        mark_overdue(today=self.today)

        done.refresh_from_db()
        self.assertEqual(done.status, ChoreOccurrence.Status.DONE)
