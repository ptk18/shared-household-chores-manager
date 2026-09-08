from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from chores.models import ChoreOccurrence, EscalationEvent
from chores.services.escalation import due_rung, escalate
from chores.services.tracking import complete_occurrence
from chores.tests.factories import make_chore, make_household, make_member, make_occurrence

Level = EscalationEvent.Level


class LadderRungTests(TestCase):
    def setUp(self):
        self.household = make_household()
        self.ada = make_member(self.household, display_name='Ada')
        self.chore = make_chore(household=self.household)
        self.today = timezone.localdate()

    def _occurrence(self, days_offset, **kwargs):
        return make_occurrence(
            self.chore, self.today + timedelta(days=days_offset), assigned_to=self.ada, **kwargs
        )

    def test_far_future_work_is_left_alone(self):
        self.assertIsNone(due_rung(self._occurrence(5), self.today))

    def test_one_day_out_gets_an_advance_reminder(self):
        self.assertEqual(due_rung(self._occurrence(1), self.today), Level.REMINDER)

    def test_due_today_gets_a_due_today_notice(self):
        self.assertEqual(due_rung(self._occurrence(0), self.today), Level.DUE_TODAY)

    def test_one_day_late_gets_an_overdue_notice(self):
        self.assertEqual(due_rung(self._occurrence(-1), self.today), Level.OVERDUE_NOTICE)

    def test_two_days_late_nudges_the_household(self):
        self.assertEqual(due_rung(self._occurrence(-2), self.today), Level.HOUSEHOLD_NUDGE)

    def test_four_days_late_offers_it_for_reassignment(self):
        self.assertEqual(due_rung(self._occurrence(-4), self.today), Level.REASSIGN_OFFER)

    def test_finished_work_never_escalates(self):
        occurrence = self._occurrence(-9)
        complete_occurrence(occurrence, self.ada)
        self.assertIsNone(due_rung(occurrence, self.today))

    def test_a_late_discovery_fires_one_rung_not_the_whole_ladder(self):
        self._occurrence(-9)

        notices = escalate(today=self.today)

        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0].level, Level.REASSIGN_OFFER)


class EscalationRunTests(TestCase):
    def setUp(self):
        self.household = make_household()
        self.ada = make_member(self.household, display_name='Ada')
        self.ada.user.email = 'ada@example.com'
        self.ada.user.save(update_fields=['email'])
        self.chore = make_chore(household=self.household, name='Bathroom')
        self.today = timezone.localdate()

    def test_each_rung_fires_only_once(self):
        make_occurrence(self.chore, self.today, assigned_to=self.ada)

        first = escalate(today=self.today)
        second = escalate(today=self.today)

        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(EscalationEvent.objects.count(), 1)

    def test_the_ladder_advances_as_days_pass(self):
        make_occurrence(self.chore, self.today, assigned_to=self.ada)

        escalate(today=self.today)
        escalate(today=self.today + timedelta(days=1))
        escalate(today=self.today + timedelta(days=2))

        self.assertEqual(
            list(EscalationEvent.objects.values_list('level', flat=True)),
            [Level.DUE_TODAY, Level.OVERDUE_NOTICE, Level.HOUSEHOLD_NUDGE],
        )

    def test_notices_reach_the_assignee(self):
        make_occurrence(self.chore, self.today, assigned_to=self.ada)

        escalate(today=self.today)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ada@example.com'])

    def test_the_household_nudge_reaches_everyone(self):
        bob = make_member(self.household, display_name='Bob')
        bob.user.email = 'bob@example.com'
        bob.user.save(update_fields=['email'])
        make_occurrence(self.chore, self.today - timedelta(days=2), assigned_to=self.ada)

        escalate(today=self.today)

        self.assertEqual(len(mail.outbox), 1)
        self.assertCountEqual(
            mail.outbox[0].to, ['ada@example.com', 'bob@example.com']
        )

    def test_the_top_rung_releases_the_chore_without_punishing_anyone(self):
        occurrence = make_occurrence(
            self.chore, self.today - timedelta(days=4), assigned_to=self.ada
        )

        escalate(today=self.today)

        occurrence.refresh_from_db()
        self.assertIsNone(occurrence.assigned_to)
        self.assertIn(occurrence.status, ChoreOccurrence.OPEN_STATUSES)
        self.assertEqual(self.ada.completed_occurrences.count(), 0)

    def test_escalation_never_marks_work_done_or_skipped(self):
        occurrence = make_occurrence(
            self.chore, self.today - timedelta(days=6), assigned_to=self.ada
        )

        escalate(today=self.today)

        occurrence.refresh_from_db()
        self.assertNotEqual(occurrence.status, ChoreOccurrence.Status.DONE)
        self.assertNotEqual(occurrence.status, ChoreOccurrence.Status.SKIPPED)

    def test_send_can_be_suppressed_for_a_dry_run(self):
        make_occurrence(self.chore, self.today, assigned_to=self.ada)

        notices = escalate(today=self.today, send=False)

        self.assertEqual(len(notices), 1)
        self.assertEqual(len(mail.outbox), 0)
