from django.test import TestCase
from django.utils import timezone

from chores.models import Member
from chores.permissions import can_claim, can_complete, can_manage_household
from chores.tests.factories import make_chore, make_household, make_member, make_occurrence


class PermissionRuleTests(TestCase):
    def setUp(self):
        self.household = make_household()
        self.admin = make_member(self.household, display_name='Admin', role=Member.Role.ADMIN)
        self.ada = make_member(self.household, display_name='Ada')
        self.bob = make_member(self.household, display_name='Bob')
        self.guest = make_member(self.household, display_name='Kid', role=Member.Role.GUEST)
        self.chore = make_chore(household=self.household)
        self.today = timezone.localdate()

    def test_only_admins_manage_the_household(self):
        self.assertTrue(can_manage_household(self.admin))
        self.assertFalse(can_manage_household(self.ada))
        self.assertFalse(can_manage_household(self.guest))

    def test_a_member_can_complete_their_own_chore(self):
        occurrence = make_occurrence(self.chore, self.today, assigned_to=self.ada)
        self.assertTrue(can_complete(self.ada, occurrence))

    def test_a_member_cannot_complete_someone_elses_chore(self):
        occurrence = make_occurrence(self.chore, self.today, assigned_to=self.bob)
        self.assertFalse(can_complete(self.ada, occurrence))

    def test_an_admin_can_complete_on_someone_elses_behalf(self):
        occurrence = make_occurrence(self.chore, self.today, assigned_to=self.bob)
        self.assertTrue(can_complete(self.admin, occurrence))

    def test_anyone_in_the_household_can_complete_unassigned_work(self):
        occurrence = make_occurrence(self.chore, self.today)
        self.assertTrue(can_complete(self.ada, occurrence))

    def test_outsiders_are_refused(self):
        outsider = make_member(make_household(name='Cabin'), display_name='Zed')
        occurrence = make_occurrence(self.chore, self.today)

        self.assertFalse(can_complete(outsider, occurrence))
        self.assertFalse(can_claim(outsider, occurrence))

    def test_guests_do_not_take_on_new_work(self):
        occurrence = make_occurrence(self.chore, self.today)

        self.assertFalse(can_claim(self.guest, occurrence))
        self.assertTrue(can_claim(self.ada, occurrence))

    def test_claimed_work_cannot_be_claimed_again(self):
        occurrence = make_occurrence(self.chore, self.today, assigned_to=self.bob)
        self.assertFalse(can_claim(self.ada, occurrence))
