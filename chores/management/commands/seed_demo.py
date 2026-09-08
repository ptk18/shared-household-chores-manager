from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from chores.models import ChoreOccurrence, ChorePreference, ChoreTemplate, Household, Member
from chores.services.assignment import autoassign
from chores.services.scheduling import generate_occurrences
from chores.services.tracking import complete_occurrence, mark_overdue

DEMO_PEOPLE = [
    ('Ada', Member.Role.ADMIN, '1.00'),
    ('Bo', Member.Role.MEMBER, '1.00'),
    ('Cy', Member.Role.GUEST, '0.50'),
]


class Command(BaseCommand):
    help = 'Create a demo household with chores, history and an overdue item. Password: demo1234'

    def add_arguments(self, parser):
        parser.add_argument('--name', default='Flat 3B', help='Household name.')

    @transaction.atomic
    def handle(self, *args, **options):
        if not ChoreTemplate.objects.exists():
            self.stderr.write('No templates found — run `manage.py seed_templates` first.')
            return

        household, created = Household.objects.get_or_create(name=options['name'])
        if not created:
            self.stderr.write(f'Household "{household.name}" already exists — nothing to do.')
            return

        members = []
        for display_name, role, capacity in DEMO_PEOPLE:
            username = f'{display_name.lower()}_demo'
            user = User.objects.create_user(
                username, email=f'{username}@example.com', password='demo1234'
            )
            members.append(
                Member.objects.create(
                    household=household,
                    user=user,
                    display_name=display_name,
                    role=role,
                    capacity=capacity,
                )
            )

        chores = [t.create_chore_for(household) for t in ChoreTemplate.objects.all()[:6]]

        # Give the dashboard something opinionated to show: Cy loves cooking-adjacent
        # work and would rather not clean the bathroom.
        ChorePreference.objects.create(
            member=members[2], chore=chores[0], sentiment=ChorePreference.Sentiment.LIKES
        )

        generate_occurrences(household=household, horizon_days=10)
        for occurrence in ChoreOccurrence.objects.filter(chore__household=household):
            autoassign(occurrence)

        today = timezone.localdate()
        finished = ChoreOccurrence.objects.filter(
            chore__household=household, due_date__lte=today
        )[:5]
        for occurrence in finished:
            complete_occurrence(occurrence, occurrence.assigned_to or members[0])

        stale = ChoreOccurrence.objects.filter(
            chore__household=household, status=ChoreOccurrence.Status.PENDING
        ).first()
        if stale:
            stale.due_date = today - timedelta(days=3)
            stale.save(update_fields=['due_date'])
        mark_overdue()

        self.stdout.write(
            self.style.SUCCESS(
                f'Demo household "{household.name}" created with '
                f'{len(members)} members and {len(chores)} chores.\n'
                'Sign in as ada_demo / bo_demo / cy_demo, password demo1234.'
            )
        )
