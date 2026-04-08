"""
Cleanup rules for unwanted photos. Rerun safely at any time.

Usage:
  manage.py cleanup
  manage.py cleanup --dry-run
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import Image


# ---------------------------------------------------------------------------
# Cleanup rules — add new rules here
# ---------------------------------------------------------------------------

RULES = [
    {
        'name': "All photos from 2008",
        'filter': Q(exif__date_taken__year=2008),
    },
    {
        'name': "Photos from Dec 26, 2014",
        'filter': Q(exif__date_taken__date='2014-12-26'),
    },
]


class Command(BaseCommand):
    help = "Delete photos matching cleanup rules"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Show what would be deleted without deleting",
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        total_deleted = 0

        for rule in RULES:
            qs = Image.objects.filter(rule['filter'])
            count = qs.count()

            if count == 0:
                self.stdout.write(f"  {rule['name']}: 0 matches")
                continue

            if dry_run:
                self.stdout.write(self.style.WARNING(
                    f"  {rule['name']}: {count} would be deleted"
                ))
            else:
                deleted, _ = qs.delete()
                total_deleted += count
                self.stdout.write(self.style.SUCCESS(
                    f"  {rule['name']}: {count} deleted"
                ))

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run — nothing deleted."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nDone: {total_deleted} images deleted."))
