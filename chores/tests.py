from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from chores.models import Chore, Household, Member


class HouseholdModelTests(TestCase):
    def test_str_is_the_name(self):
        household = Household.objects.create(name='Flat 3B')
        self.assertEqual(str(household), 'Flat 3B')


class MemberModelTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name='Flat 3B')
        self.user = User.objects.create_user('ada', password='pw')

    def test_defaults_to_member_role(self):
        member = Member.objects.create(
            household=self.household, user=self.user, display_name='Ada'
        )
        self.assertEqual(member.role, Member.Role.MEMBER)
        self.assertFalse(member.is_admin)

    def test_is_admin_reflects_role(self):
        member = Member.objects.create(
            household=self.household,
            user=self.user,
            display_name='Ada',
            role=Member.Role.ADMIN,
        )
        self.assertTrue(member.is_admin)

    def test_one_member_profile_per_user(self):
        Member.objects.create(
            household=self.household, user=self.user, display_name='Ada'
        )
        other_household = Household.objects.create(name='Cabin')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Member.objects.create(
                    household=other_household, user=self.user, display_name='Ada'
                )

    def test_deleting_household_removes_its_members(self):
        Member.objects.create(
            household=self.household, user=self.user, display_name='Ada'
        )
        self.household.delete()
        self.assertEqual(Member.objects.count(), 0)


class ChoreModelTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name='Flat 3B')

    def test_sensible_defaults(self):
        chore = Chore.objects.create(household=self.household, name='Vacuuming')
        self.assertEqual(chore.effort_weight, 1)
        self.assertEqual(chore.frequency, Chore.Frequency.WEEKLY)
        self.assertEqual(chore.category, Chore.Category.OTHER)
        self.assertTrue(chore.is_active)
        self.assertIsNone(chore.estimated_minutes)

    def test_name_is_unique_within_a_household(self):
        Chore.objects.create(household=self.household, name='Dishes')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Chore.objects.create(household=self.household, name='Dishes')

    def test_same_name_allowed_in_a_different_household(self):
        Chore.objects.create(household=self.household, name='Dishes')
        other = Household.objects.create(name='Cabin')
        Chore.objects.create(household=other, name='Dishes')
        self.assertEqual(Chore.objects.filter(name='Dishes').count(), 2)

    def test_effort_weight_is_bounded_to_the_declared_scale(self):
        too_heavy = Chore(household=self.household, name='Repaint house', effort_weight=11)
        with self.assertRaises(ValidationError):
            too_heavy.full_clean()

        too_light = Chore(household=self.household, name='Blink', effort_weight=0)
        with self.assertRaises(ValidationError):
            too_light.full_clean()

    def test_effort_weight_accepts_the_scale_boundaries(self):
        for weight in (1, 10):
            chore = Chore(
                household=self.household, name=f'Chore {weight}', effort_weight=weight
            )
            chore.full_clean()
            chore.save()
        self.assertEqual(Chore.objects.count(), 2)
