"""
Reverse geocode images with GPS data to assign cities.

Usage:
  manage.py geocode
  manage.py geocode --force  # Re-geocode all images
"""

from django.core.management.base import BaseCommand

from core.models import City, ExifData


class Command(BaseCommand):
    help = "Reverse geocode images to assign cities"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help="Re-geocode images that already have a city",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Show what would be processed without processing",
        )

    def handle(self, *args, **options):
        import reverse_geocoder as rg

        qs = ExifData.objects.filter(
            gps_latitude__isnull=False, gps_longitude__isnull=False,
        ).select_related('image')

        if not options['force']:
            qs = qs.filter(image__city__isnull=True)

        exif_list = list(qs)
        self.stdout.write(f"Found {len(exif_list)} images to geocode")

        if not exif_list or options['dry_run']:
            return

        # Batch geocode all at once — much faster than one at a time
        coords = [(float(e.gps_latitude), float(e.gps_longitude)) for e in exif_list]
        self.stdout.write("Reverse geocoding...")
        results = rg.search(coords)

        geocoded = 0
        for exif, result in zip(exif_list, results):
            city = City.from_coordinates(float(exif.gps_latitude), float(exif.gps_longitude))
            if city:
                exif.image.city = city
                exif.image.save(update_fields=['city', 'updated_at'])
                geocoded += 1

            if geocoded % 100 == 0 and geocoded > 0:
                self.stdout.write(f"  {geocoded}/{len(exif_list)}")

        self.stdout.write(self.style.SUCCESS(f"Done: {geocoded} images geocoded"))
