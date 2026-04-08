"""
Generate AI descriptions for images that don't have one yet.

Usage:
  manage.py ai_describe
  manage.py ai_describe --limit=100
  manage.py ai_describe --workers=8
  manage.py ai_describe --force  # Re-describe all images
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand

from core.models import Image


class Command(BaseCommand):
    help = "Generate AI descriptions for images"

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=0,
            help="Max images to process (0 = all)",
        )
        parser.add_argument(
            '--workers', type=int, default=4,
            help="Number of concurrent workers (default: 4)",
        )
        parser.add_argument(
            '--force', action='store_true',
            help="Re-describe images that already have descriptions",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Show what would be processed without processing",
        )

    def handle(self, *args, **options):
        from core.models import SiteConfig

        config = SiteConfig.load()
        if not config.openai_api_key:
            self.stderr.write(self.style.ERROR(
                "No OpenAI API key configured. Set it in /admin/core/siteconfig/"
            ))
            return

        qs = Image.objects.filter(is_processing=False).order_by('-upload_date')
        if not options['force']:
            qs = qs.filter(ai_description='')

        if options['limit']:
            qs = qs[:options['limit']]

        images = list(qs)
        self.stdout.write(f"Found {len(images)} images to describe")

        if not images:
            return

        if options['dry_run']:
            for img in images:
                self.stdout.write(f"  {img.title or img.id}")
            return

        if options['force']:
            Image.objects.filter(id__in=[i.id for i in images]).update(ai_description='')

        from ingest.tasks import generate_ai_description_task

        total = len(images)
        done = 0
        errors = 0

        def describe_one(img):
            generate_ai_description_task(str(img.id))
            img.refresh_from_db()
            return img

        workers = options['workers']
        self.stdout.write(f"Processing with {workers} workers...")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(describe_one, img): img for img in images}
            for future in as_completed(futures):
                img = futures[future]
                done += 1
                try:
                    result = future.result()
                    title = result.ai_title or result.title or result.id
                    self.stdout.write(f"  [{done}/{total}] {title} → /images/{img.id}/")
                except Exception as e:
                    errors += 1
                    self.stderr.write(self.style.ERROR(f"  [{done}/{total}] ERROR {img.title or img.id}: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone: {done - errors} described, {errors} errors"
        ))
