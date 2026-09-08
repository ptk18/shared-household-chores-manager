from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from chores.models import ChoreOccurrence, Member
from chores.tests.factories import make_chore, make_household, make_member, make_occurrence


class DashboardTests(TestCase):
    def setUp(self):
        self.household = make_household()
        self.ada = make_member(self.household, display_name='Ada')
        self.bob = make_member(self.household, display_name='Bob')
        self.today = timezone.localdate()
        self.client.force_login(self.ada.user)

    def test_anonymous_visitors_are_sent_to_login(self):
        self.client.logout()
        response = self.client.get(reverse('chores:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_all_four_sections_render(self):
        response = self.client.get(reverse('chores:dashboard'))

        self.assertEqual(response.status_code, 200)
        for heading in (b'Today', b'My chores', b'Overdue', b'Household health'):
            self.assertIn(heading, response.content)

    def test_today_shows_only_todays_open_work(self):
        chore = make_chore(household=self.household, name='Dishes')
        make_occurrence(chore, self.today)
        make_occurrence(chore, self.today - timezone.timedelta(days=2))

        response = self.client.get(reverse('chores:dashboard'))

        self.assertEqual(len(response.context['due_today']), 1)

    def test_my_chores_excludes_other_peoples_work(self):
        chore = make_chore(household=self.household, name='Dishes')
        make_occurrence(chore, self.today, assigned_to=self.bob)

        response = self.client.get(reverse('chores:dashboard'))

        self.assertEqual(len(response.context['my_chores']), 0)

    def test_another_households_chores_never_appear(self):
        other = make_household(name='Cabin')
        make_occurrence(make_chore(household=other, name='Secret'), self.today)

        response = self.client.get(reverse('chores:dashboard'))

        self.assertNotIn(b'Secret', response.content)


class CompleteAndClaimTests(TestCase):
    def setUp(self):
        self.household = make_household()
        self.ada = make_member(self.household, display_name='Ada')
        self.bob = make_member(self.household, display_name='Bob')
        self.chore = make_chore(household=self.household)
        self.today = timezone.localdate()
        self.client.force_login(self.ada.user)

    def test_completing_round_trips_through_the_dashboard(self):
        occurrence = make_occurrence(self.chore, self.today, assigned_to=self.ada)

        response = self.client.post(
            reverse('chores:complete', args=[occurrence.pk]), follow=True
        )

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.status, ChoreOccurrence.Status.DONE)
        self.assertEqual(occurrence.completed_by, self.ada)
        self.assertContains(response, 'is done')

    def test_completing_someone_elses_chore_is_refused(self):
        occurrence = make_occurrence(self.chore, self.today, assigned_to=self.bob)

        self.client.post(reverse('chores:complete', args=[occurrence.pk]), follow=True)

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.status, ChoreOccurrence.Status.PENDING)

    def test_get_requests_cannot_change_state(self):
        occurrence = make_occurrence(self.chore, self.today, assigned_to=self.ada)

        response = self.client.get(reverse('chores:complete', args=[occurrence.pk]))

        self.assertEqual(response.status_code, 405)
        occurrence.refresh_from_db()
        self.assertEqual(occurrence.status, ChoreOccurrence.Status.PENDING)

    def test_claiming_assigns_the_occurrence(self):
        occurrence = make_occurrence(self.chore, self.today)

        self.client.post(reverse('chores:claim', args=[occurrence.pk]), follow=True)

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.assigned_to, self.ada)

    def test_cannot_touch_another_households_occurrence(self):
        other = make_household(name='Cabin')
        occurrence = make_occurrence(make_chore(household=other), self.today)

        response = self.client.post(reverse('chores:complete', args=[occurrence.pk]))

        self.assertEqual(response.status_code, 404)

    def test_completion_moves_the_fairness_numbers(self):
        heavy = make_chore(household=self.household, name='Bathroom', effort_weight=5)
        occurrence = make_occurrence(heavy, self.today, assigned_to=self.ada)

        self.client.post(reverse('chores:complete', args=[occurrence.pk]))
        response = self.client.get(reverse('chores:dashboard'))

        self.assertEqual(response.context['fairness'].total_effort, 5)


class HouseholdSettingsTests(TestCase):
    def setUp(self):
        self.household = make_household()
        self.admin = make_member(self.household, display_name='Admin', role=Member.Role.ADMIN)
        self.ada = make_member(self.household, display_name='Ada')

    def test_an_admin_can_open_settings(self):
        self.client.force_login(self.admin.user)
        response = self.client.get(reverse('chores:household_settings'))
        self.assertEqual(response.status_code, 200)

    def test_a_plain_member_cannot_open_settings(self):
        self.client.force_login(self.ada.user)
        response = self.client.get(reverse('chores:household_settings'))
        self.assertEqual(response.status_code, 403)

    def test_a_user_with_no_household_is_refused(self):
        from django.contrib.auth.models import User

        self.client.force_login(User.objects.create_user('stranger', password='pw'))
        response = self.client.get(reverse('chores:dashboard'))
        self.assertEqual(response.status_code, 403)


class OccurrenceDetailTests(TestCase):
    def test_detail_shows_the_ranked_suggestions(self):
        household = make_household()
        ada = make_member(household, display_name='Ada')
        make_member(household, display_name='Bob')
        occurrence = make_occurrence(
            make_chore(household=household, name='Vacuuming'), timezone.localdate()
        )
        self.client.force_login(ada.user)

        response = self.client.get(
            reverse('chores:occurrence_detail', args=[occurrence.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['recommendations']), 2)
        self.assertContains(response, 'Suggested for')
