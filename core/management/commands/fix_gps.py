from django.core.management.base import BaseCommand

from core.exif import extract_exif
from core.models import ExifData


class Command(BaseCommand):
    help = "Re-extract GPS coordinates from originals to fix sign issues"

    def handle(self, *args, **options):
        qs = ExifData.objects.filter(gps_longitude__isnull=False).select_related('image')
        total = qs.count()
        fixed = 0

        self.stdout.write(f"Checking {total} images with GPS data...")

        for e in qs:
            try:
                f = e.image.original
                f.open('rb')
                exif = extract_exif(f)
                f.close()

                changed = False
                if exif['gps_latitude'] is not None and exif['gps_latitude'] != e.gps_latitude:
                    e.gps_latitude = exif['gps_latitude']
                    changed = True
                if exif['gps_longitude'] is not None and exif['gps_longitude'] != e.gps_longitude:
                    e.gps_longitude = exif['gps_longitude']
                    changed = True

                if changed:
                    e.save(update_fields=['gps_latitude', 'gps_longitude'])
                    fixed += 1
                    self.stdout.write(f"  Fixed {e.image_id}: ({e.gps_latitude}, {e.gps_longitude})")
            except Exception as ex:
                self.stdout.write(self.style.WARNING(f"  Error {e.image_id}: {ex}"))

        self.stdout.write(self.style.SUCCESS(f"Fixed {fixed} of {total} images"))
