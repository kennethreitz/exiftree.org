import logging

from celery import shared_task

from core.models import Image

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_image_task(self, image_id: str) -> None:
    """Async task to run the full ingest pipeline on an uploaded image."""
    from ingest.pipeline import process_image

    try:
        image = Image.objects.get(id=image_id)
    except Image.DoesNotExist:
        logger.error("Image %s not found, skipping processing", image_id)
        return

    try:
        process_image(image)
        logger.info("Successfully processed image %s", image_id)
    except Exception as exc:
        logger.exception("Failed to process image %s", image_id)
        raise self.retry(exc=exc)
