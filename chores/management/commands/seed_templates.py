from django.core.management.base import BaseCommand

from chores.models import Chore, ChoreTemplate

# Effort weights are on the 1-10 scale documented on Chore.effort_weight and are
# relative to each other, not to clock time: a short but unpleasant job can
# outweigh a long easy one.
TEMPLATES = [
    {
        'name': 'Washing dishes',
        'category': Chore.Category.KITCHEN,
        'default_effort_weight': 2,
        'default_frequency': Chore.Frequency.DAILY,
        'estimated_minutes': 15,
        'description': 'Wash, dry and put away.',
    },
    {
        'name': 'Laundry',
        'category': Chore.Category.LAUNDRY,
        'default_effort_weight': 3,
        'default_frequency': Chore.Frequency.WEEKLY,
        'estimated_minutes': 45,
        'description': 'Wash, dry, fold and put away one load.',
    },
    {
        'name': 'Vacuuming',
        'category': Chore.Category.CLEANING,
        'default_effort_weight': 3,
        'default_frequency': Chore.Frequency.WEEKLY,
        'estimated_minutes': 30,
        'description': 'All shared floors.',
    },
    {
        'name': 'Taking out trash',
        'category': Chore.Category.CLEANING,
        'default_effort_weight': 1,
        'default_frequency': Chore.Frequency.WEEKLY,
        'estimated_minutes': 5,
        'description': 'Bins out, liners replaced.',
    },
    {
        'name': 'Cleaning bathroom',
        'category': Chore.Category.CLEANING,
        'default_effort_weight': 5,
        'default_frequency': Chore.Frequency.WEEKLY,
        'estimated_minutes': 40,
        'description': 'Toilet, shower, sink, mirror, floor.',
    },
    {
        'name': 'Grocery shopping',
        'category': Chore.Category.SHOPPING,
        'default_effort_weight': 4,
        'default_frequency': Chore.Frequency.WEEKLY,
        'estimated_minutes': 60,
        'description': 'Shop the household list and unpack.',
    },
    {
        'name': 'Wiping kitchen surfaces',
        'category': Chore.Category.KITCHEN,
        'default_effort_weight': 1,
        'default_frequency': Chore.Frequency.DAILY,
        'estimated_minutes': 10,
        'description': 'Counters, hob and table.',
    },
    {
        'name': 'Mopping floors',
        'category': Chore.Category.CLEANING,
        'default_effort_weight': 4,
        'default_frequency': Chore.Frequency.MONTHLY,
        'estimated_minutes': 35,
        'description': 'Hard floors throughout.',
    },
]


class Command(BaseCommand):
    help = 'Create or refresh the built-in chore templates. Safe to run repeatedly.'

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for spec in TEMPLATES:
            _, created = ChoreTemplate.objects.update_or_create(
                name=spec['name'],
                defaults={k: v for k, v in spec.items() if k != 'name'},
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Templates seeded: {created_count} created, {updated_count} updated.'
            )
        )
