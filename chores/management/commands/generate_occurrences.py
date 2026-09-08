from django.core.management.base import BaseCommand

from chores.models import Household
from chores.services.scheduling import DEFAULT_HORIZON_DAYS, generate_occurrences


class Command(BaseCommand):
    help = (
        'Create chore occurrences out to the horizon for all active chores. '
        'Safe to run repeatedly — existing occurrences are never modified.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--household',
            type=int,
            help='Limit generation to one household id.',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=DEFAULT_HORIZON_DAYS,
            help=f'How many days ahead to generate (default {DEFAULT_HORIZON_DAYS}).',
        )

    def handle(self, *args, **options):
        household = None
        if options['household']:
            household = Household.objects.get(pk=options['household'])

        created = generate_occurrences(household=household, horizon_days=options['days'])
        scope = household.name if household else 'all households'
        self.stdout.write(
            self.style.SUCCESS(f'{created} occurrence(s) created for {scope}.')
        )
