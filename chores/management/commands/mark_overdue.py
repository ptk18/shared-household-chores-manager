from django.core.management.base import BaseCommand

from chores.services.tracking import mark_overdue


class Command(BaseCommand):
    help = 'Flip pending occurrences past their due date to overdue.'

    def handle(self, *args, **options):
        count = mark_overdue()
        self.stdout.write(self.style.SUCCESS(f'{count} occurrence(s) marked overdue.'))
