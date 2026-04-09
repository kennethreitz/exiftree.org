import logging

import imagehash
from celery import shared_task

from core.models import Image

logger = logging.getLogger(__name__)

PHASH_THRESHOLD = 10


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

        # Post-processing perceptual dedup
        if image.perceptual_hash and image.perceptual_hash != '8000000000000000':
            upload_hash = imagehash.hex_to_hash(image.perceptual_hash)
            candidates = list(
                Image.objects.exclude(id=image.id)
                .exclude(perceptual_hash='')
                .exclude(perceptual_hash='8000000000000000')
                .values_list('id', 'perceptual_hash')
            )
            for cid, chash in candidates:
                if imagehash.hex_to_hash(chash) - upload_hash <= PHASH_THRESHOLD:
                    logger.info("Image %s is visual dupe of %s, deleting", image_id, cid)
                    image.delete()
                    return

        # Generate AI description
        try:
            generate_ai_description_task.delay(str(image.id))
        except Exception:
            pass

        logger.info("Successfully processed image %s", image_id)
    except Exception as exc:
        logger.exception("Failed to process image %s", image_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_ai_description_task(self, image_id: str) -> None:
    """Generate AI title, description, and tags for an image using OpenAI vision."""
    import json

    from django.utils.text import slugify

    from core.models import SiteConfig, Tag

    config = SiteConfig.load()
    if not config.openai_api_key:
        return

    try:
        image = Image.objects.get(id=image_id)
    except Image.DoesNotExist:
        return

    # Skip if already described
    if image.ai_description:
        return

    # Get thumbnail URL
    thumb = image.thumbnail_medium or image.thumbnail_small or image.original
    if not thumb:
        return

    try:
        import openai
        client = openai.OpenAI(api_key=config.openai_api_key)

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": config.ai_prompt},
                            {"type": "image_url", "image_url": {"url": thumb.url}},
                        ],
                    }
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "image_metadata",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "Short, evocative artistic title (3-7 words)",
                                },
                                "description": {
                                    "type": "string",
                                    "description": "2-3 sentence description of the photograph",
                                },
                                "tags": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "5-10 single-word lowercase tags",
                                },
                            },
                            "required": ["title", "description", "tags"],
                            "additionalProperties": False,
                        },
                    },
                },
                max_tokens=400,
            )
        finally:
            client.close()

        data = json.loads(response.choices[0].message.content)

        image.ai_title = data.get('title', '')[:255]
        image.ai_description = data.get('description', '')
        # Use AI title as the display title if no manual title was set
        if not image.title and image.ai_title:
            image.title = image.ai_title
            image.slug = slugify(image.ai_title) or image.slug
        image.save(update_fields=['ai_title', 'ai_description', 'title', 'slug', 'updated_at'])

        # Create/link tags
        tag_names = data.get('tags', [])
        for name in tag_names[:15]:
            name = name.lower().strip()[:100]
            if not name:
                continue
            slug = slugify(name)
            if not slug:
                continue
            tag, _ = Tag.objects.get_or_create(
                slug=slug, defaults={'name': name},
            )
            image.tags.add(tag)

        logger.info("AI metadata generated for image %s: %s", image_id, image.ai_title)

    except Exception as exc:
        logger.exception("Failed to generate AI metadata for %s", image_id)
        raise self.retry(exc=exc)
