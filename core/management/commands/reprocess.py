from django.core.management.base import BaseCommand

from core.models import Image
from ingest.pipeline import process_image


class Command(BaseCommand):
    help = "Reprocess images that are stuck in processing state"

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help="Reprocess ALL images, not just stuck ones")

    def handle(self, *args, **options):
        if options['all']:
            qs = Image.objects.all()
        else:
            qs = Image.objects.filter(is_processing=True)

        total = qs.count()
        if not total:
            self.stdout.write("No images to reprocess.")
            return

        self.stdout.write(f"Reprocessing {total} images...")
        ok = 0
        for i, img in enumerate(qs, 1):
            try:
                process_image(img)
                img.original.close()
                ok += 1
                self.stdout.write(f"  [{i}/{total}] {img.id} ok")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  [{i}/{total}] {img.id} FAILED: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Done. {ok}/{total} succeeded."))
