"""
Import collections from a directory structure.

Each subdirectory becomes a collection. Images are matched to existing
database records by content hash.

Usage:
  manage.py import_collections /path/to/photography
"""

import hashlib
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.models import Image, User
from gallery.models import Collection, CollectionImage

SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif'}


class Command(BaseCommand):
    help = "Import collections from directory structure"

    def add_arguments(self, parser):
        parser.add_argument('path', type=str, help="Path to directory with subdirectories of images")
        parser.add_argument('--user', type=str, default='', help="Username (defaults to first user)")
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        root = Path(options['path']).expanduser().resolve()
        if not root.is_dir():
            self.stderr.write(self.style.ERROR(f"Not a directory: {root}"))
            return

        user = User.objects.filter(username=options['user']).first() if options['user'] else User.objects.first()
        if not user:
            self.stderr.write(self.style.ERROR("No user found"))
            return

        # Find subdirectories (each is a collection)
        dirs = sorted([d for d in root.iterdir() if d.is_dir()])
        if not dirs:
            self.stderr.write(self.style.WARNING("No subdirectories found"))
            return

        self.stdout.write(f"Found {len(dirs)} collections in {root}")

        for d in dirs:
            files = sorted(f for f in d.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS)
            if not files:
                continue

            col_title = d.name.replace('-', ' ').replace('_', ' ').title()
            self.stdout.write(f"\n{col_title} ({len(files)} images):")

            if options['dry_run']:
                for f in files:
                    self.stdout.write(f"  {f.name}")
                continue

            # Get or create collection
            base_slug = slugify(col_title) or d.name
            collection, created = Collection.objects.get_or_create(
                user=user, slug=base_slug,
                defaults={'title': col_title},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Created collection: {col_title}"))
            else:
                self.stdout.write(f"  Using existing collection: {col_title}")

            # Match images by content hash, then by filename
            matched = 0
            not_found = 0
            for i, filepath in enumerate(files):
                # Try content hash first
                content_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()
                image = Image.objects.filter(content_hash=content_hash).first()

                # Fall back to filename match
                if not image:
                    stem = filepath.stem
                    image = Image.objects.filter(original__icontains=stem).first()

                if image:
                    CollectionImage.objects.get_or_create(
                        collection=collection, image=image,
                        defaults={'sort_order': i},
                    )
                    matched += 1
                    self.stdout.write(f"  [{i+1}/{len(files)}] MATCH {filepath.name}")
                else:
                    not_found += 1
                    self.stdout.write(self.style.WARNING(f"  [{i+1}/{len(files)}] NOT FOUND {filepath.name}"))

            self.stdout.write(f"  {matched} matched, {not_found} not found")

        self.stdout.write(self.style.SUCCESS("\nDone"))
