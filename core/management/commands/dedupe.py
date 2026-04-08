import imagehash
from django.core.management.base import BaseCommand

from core.models import Image


class Command(BaseCommand):
    help = "Find and remove visually similar duplicate images via perceptual hashing"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Show duplicates without deleting",
        )
        parser.add_argument(
            '--threshold', type=int, default=10,
            help="Hamming distance threshold (default: 10)",
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        threshold = options['threshold']

        images = list(
            Image.objects.exclude(perceptual_hash='')
            .exclude(perceptual_hash='8000000000000000')
            .order_by('upload_date')
        )

        self.stdout.write(f"Scanning {len(images)} images (threshold={threshold})...")

        seen = []  # (hash, image) pairs we're keeping
        to_delete = []

        for img in images:
            h = imagehash.hex_to_hash(img.perceptual_hash)
            duplicate_of = None
            for kept_hash, kept_img in seen:
                if h - kept_hash <= threshold:
                    duplicate_of = kept_img
                    break

            if duplicate_of:
                to_delete.append((img, duplicate_of))
            else:
                seen.append((h, img))

        if not to_delete:
            self.stdout.write(self.style.SUCCESS("No duplicates found."))
            return

        self.stdout.write(f"\nFound {len(to_delete)} duplicates:\n")
        for dup, original in to_delete:
            dist = imagehash.hex_to_hash(dup.perceptual_hash) - imagehash.hex_to_hash(original.perceptual_hash)
            self.stdout.write(
                f"  DELETE {dup.id} ({dup.slug}) — duplicate of {original.id} ({original.slug}) [distance={dist}]"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING(f"\nDry run — {len(to_delete)} images would be deleted."))
        else:
            for dup, _ in to_delete:
                dup.delete()
            self.stdout.write(self.style.SUCCESS(f"\nDeleted {len(to_delete)} duplicate images."))
