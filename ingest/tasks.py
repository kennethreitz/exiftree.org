import hashlib
import logging
import time

import imagehash
import requests
from celery import shared_task

from core.models import Image

logger = logging.getLogger(__name__)

PHASH_THRESHOLD = 10
FLICKR_API = "https://www.flickr.com/services/rest/"


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

        logger.info("Successfully processed image %s", image_id)
    except Exception as exc:
        logger.exception("Failed to process image %s", image_id)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Flickr import tasks
# ---------------------------------------------------------------------------

def _flickr_api(session, api_key, method, **kwargs):
    """Call Flickr API with backoff on 429."""
    params = {
        'method': method,
        'api_key': api_key,
        'format': 'json',
        'nojsoncallback': '1',
        **kwargs,
    }
    for attempt in range(5):
        resp = session.get(FLICKR_API, params=params, timeout=15)
        if resp.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()


def _download_with_backoff(session, url):
    """Download a URL with exponential backoff on 429."""
    for attempt in range(5):
        resp = session.get(url, timeout=60)
        if resp.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        resp.raise_for_status()
        return resp.content
    resp.raise_for_status()


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def flickr_import_set_task(self, flickr_nsid: str, set_id: str, set_title: str,
                           set_desc: str, set_date: str, api_key: str,
                           username: str) -> None:
    """Import a single Flickr photoset — spawns per-photo tasks."""
    from django.utils.text import slugify
    from gallery.models import Collection

    user = Image._meta.get_field('user').related_model.objects.get(username=username)
    session = requests.Session()

    # Create collection
    slug = slugify(set_title) or f"flickr-{set_id}"
    collection, created = Collection.objects.get_or_create(
        user=user, slug=slug,
        defaults={'title': set_title, 'description': set_desc},
    )
    if created and set_date:
        try:
            from datetime import datetime
            collection.date = datetime.fromtimestamp(int(set_date)).date()
            collection.save(update_fields=['date'])
        except (ValueError, TypeError):
            pass

    logger.info("Importing Flickr set: %s (%s)", set_title, set_id)

    # Get photos in set
    photos = []
    page = 1
    while True:
        data = _flickr_api(
            session, api_key, 'flickr.photosets.getPhotos',
            photoset_id=set_id, user_id=flickr_nsid,
            extras='url_o,date_taken,description,tags',
            per_page='500', page=str(page),
        )
        batch = data.get('photoset', {}).get('photo', [])
        photos.extend(batch)
        pages = int(data.get('photoset', {}).get('pages', 1))
        if page >= pages:
            break
        page += 1

    # Dispatch per-photo tasks
    for i, photo in enumerate(photos):
        flickr_import_photo_task.delay(
            photo_id=photo['id'],
            title=photo.get('title', ''),
            sort_order=i,
            collection_id=str(collection.id),
            api_key=api_key,
            username=username,
        )

    logger.info("Dispatched %d photo tasks for set %s", len(photos), set_title)


@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def flickr_import_photo_task(self, photo_id: str, title: str, sort_order: int,
                             collection_id: str, api_key: str,
                             username: str) -> None:
    """Import a single photo from Flickr."""
    from django.core.files.base import ContentFile
    from django.utils.text import slugify
    from gallery.models import Collection, CollectionImage
    from ingest.pipeline import process_image

    user = Image._meta.get_field('user').related_model.objects.get(username=username)
    collection = Collection.objects.get(id=collection_id)
    session = requests.Session()

    try:
        # Get photo info
        info_data = _flickr_api(session, api_key, 'flickr.photos.getInfo', photo_id=photo_id)
        info = info_data.get('photo', {})
        description = info.get('description', {}).get('_content', '')
        date_taken = None
        dt_str = info.get('dates', {}).get('taken', '')
        if dt_str:
            try:
                from datetime import datetime
                date_taken = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass

        # Get sizes
        sizes_data = _flickr_api(session, api_key, 'flickr.photos.getSizes', photo_id=photo_id)
        sizes = sizes_data.get('sizes', {}).get('size', [])
        if not sizes:
            logger.warning("Flickr photo %s: no sizes available", photo_id)
            return

        # Pick best URL
        url = None
        for label in ['Original', 'Large 2048', 'Large 1600', 'Large', 'Medium 800', 'Medium']:
            for s in sizes:
                if s['label'] == label:
                    url = s['source']
                    break
            if url:
                break
        if not url:
            url = sizes[-1]['source']

        # Download
        contents = _download_with_backoff(session, url)

        # Dedup
        content_hash = hashlib.sha256(contents).hexdigest()
        existing = Image.objects.filter(content_hash=content_hash).first()
        if existing:
            CollectionImage.objects.get_or_create(
                collection=collection, image=existing,
                defaults={'sort_order': sort_order},
            )
            logger.info("Flickr photo %s already exists, added to collection", photo_id)
            return

        # Create image
        filename = f"{slugify(title) or photo_id}.jpg"
        img = Image.objects.create(
            user=user,
            title=title,
            description=description,
            slug=slugify(title) or f"flickr-{photo_id}",
            original=ContentFile(contents, name=filename),
            content_hash=content_hash,
            is_processing=True,
        )
        del contents

        # Process
        process_image(img)
        img.original.close()

        # Fill missing EXIF date
        if date_taken and hasattr(img, 'exif'):
            exif = img.exif
            if not exif.date_taken:
                from django.utils import timezone
                exif.date_taken = timezone.make_aware(date_taken)
                exif.save(update_fields=['date_taken'])

        # Add to collection
        CollectionImage.objects.get_or_create(
            collection=collection, image=img,
            defaults={'sort_order': sort_order},
        )

        logger.info("Flickr photo %s imported successfully", photo_id)

    except Exception as exc:
        logger.exception("Failed to import Flickr photo %s", photo_id)
        raise self.retry(exc=exc)


@shared_task(bind=True)
def flickr_import_all_task(self, flickr_user: str, api_key: str,
                           username: str, set_id: str = '') -> None:
    """Top-level task: resolve user, enumerate sets, dispatch set tasks."""
    session = requests.Session()

    # Resolve NSID
    if '@' in flickr_user:
        nsid = flickr_user
    else:
        data = _flickr_api(session, api_key, 'flickr.people.findByUsername', username=flickr_user)
        nsid = data['user']['nsid']

    # Get sets
    data = _flickr_api(session, api_key, 'flickr.photosets.getList', user_id=nsid, per_page='500')
    sets = data.get('photosets', {}).get('photoset', [])

    if set_id:
        sets = [s for s in sets if s['id'] == set_id]

    logger.info("Dispatching %d Flickr set import tasks for %s", len(sets), flickr_user)

    for photoset in sets:
        flickr_import_set_task.delay(
            flickr_nsid=nsid,
            set_id=photoset['id'],
            set_title=photoset['title']['_content'],
            set_desc=photoset.get('description', {}).get('_content', ''),
            set_date=photoset.get('date_create', ''),
            api_key=api_key,
            username=username,
        )
