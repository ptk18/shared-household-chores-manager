from django.core.management.base import BaseCommand

from chores.services.escalation import escalate


class Command(BaseCommand):
    help = (
        'Advance the gentle escalation ladder by one rung for each open chore. '
        'Safe to run repeatedly — each rung fires at most once per occurrence.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be sent without sending or recording anything.',
        )

    def handle(self, *args, **options):
        if options['dry_run']:
            from django.db import transaction

            with transaction.atomic():
                notices = escalate(send=False)
                for notice in notices:
                    self.stdout.write(f'{notice.level_label}: {notice.subject}')
                self.stdout.write(self.style.WARNING(f'{len(notices)} notice(s) — dry run, rolling back.'))
                transaction.set_rollback(True)
            return

        notices = escalate()
        for notice in notices:
            self.stdout.write(f'{notice.level_label}: {notice.subject}')
        self.stdout.write(self.style.SUCCESS(f'{len(notices)} notice(s) sent.'))
