"""
Import photos from a local folder.

Usage:
  manage.py import_folder /path/to/photos
  manage.py import_folder /path/to/photos --collection="Trip to Japan"
  manage.py import_folder /path/to/photos --recursive
  manage.py import_folder /path/to/photos --visibility=private
"""

import hashlib
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.models import Image, User

SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif'}


class Command(BaseCommand):
    help = "Import photos from a local folder"

    def add_arguments(self, parser):
        parser.add_argument('path', type=str, help="Path to folder of images")
        parser.add_argument(
            '--user', type=str, default='',
            help="Username to import as (defaults to first user)",
        )
        parser.add_argument(
            '--collection', type=str, default='',
            help="Create or add to a collection with this name",
        )
        parser.add_argument(
            '--no-recursive', action='store_true',
            help="Don't recurse into subdirectories",
        )
        parser.add_argument(
            '--visibility', type=str, default='public',
            choices=['public', 'private', 'unlisted'],
            help="Visibility for imported images (default: public)",
        )
        parser.add_argument(
            '--skip', type=int, default=0,
            help="Skip the first N images",
        )
        parser.add_argument(
            '--workers', type=int, default=1,
            help="Number of concurrent upload workers (default: 1)",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Show what would be imported without importing",
        )

    def handle(self, *args, **options):
        folder = Path(options['path']).expanduser().resolve()
        if not folder.is_dir():
            self.stderr.write(self.style.ERROR(f"Not a directory: {folder}"))
            return

        # Resolve user
        username = options['user']
        if username:
            user = User.objects.filter(username=username).first()
            if not user:
                self.stderr.write(self.style.ERROR(f"User not found: {username}"))
                return
        else:
            user = User.objects.first()
            if not user:
                self.stderr.write(self.style.ERROR("No users exist. Create one first."))
                return

        self.stdout.write(f"Importing as: {user.username}")

        # Collect files
        if options['no_recursive']:
            files = sorted(f for f in folder.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS)
        else:
            files = sorted(f for f in folder.rglob('*') if f.suffix.lower() in SUPPORTED_EXTENSIONS)

        if not files:
            self.stderr.write(self.style.WARNING(f"No images found in {folder}"))
            return

        if options['skip']:
            files = files[options['skip']:]

        # Auto-skip: check by filename first (fast), then hash for ambiguous
        self.stdout.write(f"Found {len(files)} images, checking for duplicates...")
        existing_names = set(
            n.rsplit('/', 1)[-1].rsplit('.', 1)[0]
            for n in Image.objects.values_list('original', flat=True)
            if n
        )
        existing_hashes = None  # lazy load

        skipped = 0
        remaining = []
        for f in files:
            stem = f.stem
            if stem in existing_names:
                skipped += 1
                continue
            # Not matched by name — check hash
            if existing_hashes is None:
                existing_hashes = set(Image.objects.values_list('content_hash', flat=True))
            h = hashlib.sha256(f.read_bytes()).hexdigest()
            if h in existing_hashes:
                skipped += 1
                continue
            remaining.append(f)

        files = remaining
        if skipped:
            self.stdout.write(f"  Skipped {skipped} duplicates")
        self.stdout.write(f"  {len(files)} images to process")

        if options['dry_run']:
            for f in files:
                self.stdout.write(f"  {f.name}")
            return

        # Create collection if requested
        collection = None
        if options['collection']:
            from gallery.models import Collection
            import uuid
            col_title = options['collection']
            base_slug = slugify(col_title) or 'import'
            slug = base_slug
            while Collection.objects.filter(user=user, slug=slug).exists():
                slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"
            collection, created = Collection.objects.get_or_create(
                user=user, slug=slug,
                defaults={'title': col_title},
            )
            if created:
                self.stdout.write(f"Created collection: {col_title}")
            else:
                self.stdout.write(f"Adding to collection: {col_title}")

        # Import concurrently
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        imported = 0
        skipped = 0
        errors = 0
        lock = threading.Lock()
        total = len(files)

        def import_one(i: int, filepath: Path) -> tuple[str, str]:
            """Returns (status, filename). status is 'ok', 'skip', or 'error'."""
            from django.db import connection
            connection.close()
            try:
                contents = filepath.read_bytes()
                content_hash = hashlib.sha256(contents).hexdigest()

                existing = Image.objects.filter(content_hash=content_hash).first()
                if existing:
                    if collection:
                        with lock:
                            self._add_to_collection(collection, existing, i)
                    return 'skip', filepath.name

                title = filepath.stem.replace('_', ' ').replace('-', ' ')
                slug = slugify(title) or f"import-{i}"

                img = Image.objects.create(
                    user=user,
                    title=title,
                    slug=slug,
                    original=ContentFile(contents, name=filepath.name),
                    content_hash=content_hash,
                    visibility=options['visibility'],
                    is_processing=True,
                )
                del contents

                from ingest.tasks import process_image_task
                try:
                    process_image_task.delay(str(img.id))
                except Exception:
                    from ingest.pipeline import process_image
                    process_image(img)

                if collection:
                    with lock:
                        self._add_to_collection(collection, img, i)

                return 'ok', filepath.name

            except Exception as e:
                return 'error', f"{filepath.name}: {e}"

        workers = options['workers']
        self.stdout.write(f"Importing with {workers} workers...")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(import_one, i, fp): i
                for i, fp in enumerate(files)
            }
            for future in as_completed(futures):
                status, name = future.result()
                idx = futures[future] + 1
                if status == 'ok':
                    imported += 1
                    self.stdout.write(f"  [{idx}/{total}] OK {name}")
                elif status == 'skip':
                    skipped += 1
                    self.stdout.write(f"  [{idx}/{total}] SKIP (duplicate) {name}")
                else:
                    errors += 1
                    self.stderr.write(self.style.ERROR(f"  [{idx}/{total}] ERROR {name}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone: {imported} imported, {skipped} skipped, {errors} errors"
        ))

    def _add_to_collection(self, collection, image, sort_order: int):
        from gallery.models import CollectionImage
        CollectionImage.objects.get_or_create(
            collection=collection, image=image,
            defaults={'sort_order': sort_order},
        )
