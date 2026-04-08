"""
Import photos and sets from a Flickr account.

Usage:
  manage.py import_flickr <flickr_username> --api-key=<key>
  manage.py import_flickr <flickr_username> --api-key=<key> --sets-only
  manage.py import_flickr <flickr_username> --api-key=<key> --set=<set_id>

Requires a free Flickr API key from https://www.flickr.com/services/api/keys/
Set FLICKR_API_KEY in .env to avoid passing it every time.
"""

import hashlib
import os
import time

import httpx
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.models import Image, User
from gallery.models import Collection, CollectionImage
from ingest.pipeline import process_image

FLICKR_API = "https://www.flickr.com/services/rest/"


class Command(BaseCommand):
    help = "Import photos and photosets from a Flickr account"

    def add_arguments(self, parser):
        parser.add_argument('flickr_user', help="Flickr username or NSID")
        parser.add_argument('--api-key', default=os.environ.get('FLICKR_API_KEY', ''),
                            help="Flickr API key (or set FLICKR_API_KEY env var)")
        parser.add_argument('--user', default=settings.SINGLE_TENANT or '',
                            help="ExifTree username to import as")
        parser.add_argument('--sets-only', action='store_true',
                            help="Only list sets, don't import")
        parser.add_argument('--set', dest='set_id',
                            help="Import only this photoset ID")
        parser.add_argument('--max', type=int, default=0,
                            help="Max photos to import (0 = all)")

    def handle(self, *args, **options):
        api_key = options['api_key']
        if not api_key:
            self.stderr.write(self.style.ERROR(
                "Flickr API key required. Get one at https://www.flickr.com/services/api/keys/\n"
                "Pass --api-key=KEY or set FLICKR_API_KEY in .env"
            ))
            return

        username = options['user']
        if not username:
            self.stderr.write(self.style.ERROR("ExifTree --user required (or set SINGLE_TENANT)"))
            return

        try:
            exiftree_user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"ExifTree user '{username}' not found"))
            return

        self.client = httpx.Client(timeout=30)
        self.api_key = api_key

        # Resolve Flickr user ID
        nsid = self._get_nsid(options['flickr_user'])
        if not nsid:
            self.stderr.write(self.style.ERROR(f"Flickr user '{options['flickr_user']}' not found"))
            return
        self.stdout.write(f"Flickr user: {nsid}")

        # Get sets
        sets = self._get_sets(nsid)
        self.stdout.write(f"Found {len(sets)} photosets")

        if options['sets_only']:
            for s in sets:
                self.stdout.write(f"  {s['id']}: {s['title']['_content']} ({s['photos']} photos)")
            return

        if options['set_id']:
            sets = [s for s in sets if s['id'] == options['set_id']]
            if not sets:
                self.stderr.write(self.style.ERROR(f"Set {options['set_id']} not found"))
                return

        max_photos = options['max']
        total_imported = 0

        for photoset in sets:
            set_title = photoset['title']['_content']
            set_id = photoset['id']
            self.stdout.write(f"\nImporting set: {set_title} ({photoset['photos']} photos)")

            # Create collection
            collection, created = Collection.objects.get_or_create(
                user=exiftree_user,
                slug=slugify(set_title) or f"flickr-{set_id}",
                defaults={
                    'title': set_title,
                    'description': photoset.get('description', {}).get('_content', ''),
                },
            )
            if created:
                self.stdout.write(f"  Created collection: {set_title}")

            # Get photos in set
            photos = self._get_set_photos(set_id, nsid)
            self.stdout.write(f"  {len(photos)} photos in set")

            for i, photo in enumerate(photos):
                if max_photos and total_imported >= max_photos:
                    self.stdout.write(f"\nReached max ({max_photos}), stopping.")
                    return

                photo_id = photo['id']
                title = photo.get('title', '')

                # Get original URL
                sizes = self._get_sizes(photo_id)
                if not sizes:
                    self.stdout.write(self.style.WARNING(f"    Skipping {photo_id}: no sizes"))
                    continue

                # Prefer Original, then Large, then Medium
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
                try:
                    resp = self.client.get(url)
                    resp.raise_for_status()
                    contents = resp.content
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"    Skipping {photo_id}: download failed: {e}"))
                    continue

                # Dedup by content hash
                content_hash = hashlib.sha256(contents).hexdigest()
                existing = Image.objects.filter(content_hash=content_hash).first()
                if existing:
                    # Add to collection if not already
                    CollectionImage.objects.get_or_create(
                        collection=collection, image=existing,
                        defaults={'sort_order': i},
                    )
                    self.stdout.write(f"    [{i+1}/{len(photos)}] {title or photo_id} — already exists, added to set")
                    continue

                # Create image
                filename = f"{slugify(title) or photo_id}.jpg"
                img = Image.objects.create(
                    user=exiftree_user,
                    title=title,
                    description='',
                    slug=slugify(title) or f"flickr-{photo_id}",
                    original=ContentFile(contents, name=filename),
                    content_hash=content_hash,
                    is_processing=True,
                )

                # Process (EXIF, thumbnails, phash)
                try:
                    process_image(img)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"    Processing error: {e}"))

                # Add to collection
                CollectionImage.objects.get_or_create(
                    collection=collection, image=img,
                    defaults={'sort_order': i},
                )

                total_imported += 1
                self.stdout.write(f"    [{i+1}/{len(photos)}] {title or photo_id} — imported")

                # Be nice to Flickr
                time.sleep(0.5)

        self.stdout.write(self.style.SUCCESS(f"\nDone. Imported {total_imported} photos."))

    def _flickr(self, method, **kwargs):
        params = {
            'method': method,
            'api_key': self.api_key,
            'format': 'json',
            'nojsoncallback': '1',
            **kwargs,
        }
        resp = self.client.get(FLICKR_API, params=params)
        resp.raise_for_status()
        return resp.json()

    def _get_nsid(self, username):
        # Try as NSID first
        if '@' in username:
            return username
        try:
            data = self._flickr('flickr.people.findByUsername', username=username)
            return data['user']['nsid']
        except Exception:
            return None

    def _get_sets(self, nsid):
        data = self._flickr('flickr.photosets.getList', user_id=nsid, per_page='500')
        return data.get('photosets', {}).get('photoset', [])

    def _get_set_photos(self, set_id, nsid):
        photos = []
        page = 1
        while True:
            data = self._flickr(
                'flickr.photosets.getPhotos',
                photoset_id=set_id, user_id=nsid,
                extras='url_o,title', per_page='500', page=str(page),
            )
            batch = data.get('photoset', {}).get('photo', [])
            photos.extend(batch)
            pages = int(data.get('photoset', {}).get('pages', 1))
            if page >= pages:
                break
            page += 1
        return photos

    def _get_sizes(self, photo_id):
        try:
            data = self._flickr('flickr.photos.getSizes', photo_id=photo_id)
            return data.get('sizes', {}).get('size', [])
        except Exception:
            return []
