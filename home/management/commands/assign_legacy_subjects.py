from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from home.models import Subject


class Command(BaseCommand):
    help = (
        'Assign subjects that have no owner (created before per-user data '
        'isolation) to one user. Data only; no schema change.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        try:
            user = User.objects.get(username=opts['username'])
        except User.DoesNotExist:
            raise CommandError(f"User {opts['username']!r} does not exist.")
        orphans = Subject.objects.filter(user__isnull=True)
        count = orphans.count()
        if opts['dry_run']:
            self.stdout.write(f'Would assign {count} subject(s) to {user.username}.')
            return
        orphans.update(user=user)
        self.stdout.write(self.style.SUCCESS(f'Assigned {count} subject(s) to {user.username}.'))
