"""Minimal builders so tests state only what they care about."""

from django.contrib.auth.models import User

from chores.models import Chore, ChoreOccurrence, Household, Member


def make_household(name='Flat 3B'):
    return Household.objects.create(name=name)


def make_member(household=None, username=None, display_name='Ada', role=Member.Role.MEMBER):
    household = household or make_household()
    username = username or display_name.lower()
    user = User.objects.create_user(username, password='pw')
    return Member.objects.create(
        household=household, user=user, display_name=display_name, role=role
    )


def make_chore(household=None, name='Dishes', **kwargs):
    household = household or make_household()
    return Chore.objects.create(household=household, name=name, **kwargs)


def make_occurrence(chore=None, due_date=None, **kwargs):
    chore = chore or make_chore()
    return ChoreOccurrence.objects.create(chore=chore, due_date=due_date, **kwargs)
