from django.core.management.base import BaseCommand

from core.models import ExifData


class Command(BaseCommand):
    help = "Fix GPS longitude sign for photos with incorrect E ref in Western hemisphere"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        # Only fix images where raw ref says E but location is clearly Western hemisphere
        qs = ExifData.objects.filter(gps_longitude__isnull=False, gps_longitude__gt=0)
        total = qs.count()
        fixed = 0

        self.stdout.write(f"Checking {total} images with positive longitude...")

        for e in qs:
            lon = float(e.gps_longitude)
            lat = float(e.gps_latitude) if e.gps_latitude else 0
            raw = e.raw_data or {}
            lon_ref = raw.get('GPS GPSLongitudeRef', '')

            # Only fix if ref says E but coordinates are clearly in Americas
            # Americas: lat 15-72N, lon 50-170 (which should be negative)
            # Skip Southern hemisphere (Australia at lon 151 is correct with E)
            if lon_ref == 'E' and lat > 15 and lon > 50 and lon < 170:
                if dry_run:
                    self.stdout.write(f"  Would fix {e.image_id}: ({lat}, {lon}) -> ({lat}, {-lon})")
                else:
                    e.gps_longitude = -lon
                    e.save(update_fields=['gps_longitude'])
                    self.stdout.write(f"  Fixed {e.image_id}: ({lat}, {-lon})")
                fixed += 1

        self.stdout.write(self.style.SUCCESS(
            f"{'Would fix' if dry_run else 'Fixed'} {fixed} of {total} images"
        ))
