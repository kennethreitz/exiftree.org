"""
Image processing pipeline — orchestrates EXIF extraction, normalization,
and thumbnail generation for uploaded images.
"""

from __future__ import annotations

from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image as PILImage

from core.exif import extract_exif
from core.models import ExifData, Image
from core.normalization import get_or_create_camera, get_or_create_lens

THUMBNAIL_SIZES = {
    'small': (300, 300),
    'medium': (800, 800),
    'large': (1600, 1600),
}

ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP', 'TIFF'}


def process_image(image: Image) -> None:
    """
    Run the full ingest pipeline on an uploaded Image.

    1. Extract EXIF
    2. Normalize camera/lens
    3. Generate thumbnails
    4. Create ExifData record
    5. Mark image as processed
    """
    file = image.original

    # 1. Extract EXIF
    exif = extract_exif(file)

    # 2. Normalize camera/lens
    camera = None
    if exif['make'] or exif['model']:
        camera = get_or_create_camera(exif['make'], exif['model'])

    lens = None
    if exif['lens_model']:
        lens = get_or_create_lens(exif['lens_model'], exif['make'])

    # 3. Generate thumbnails
    file.seek(0)
    generate_thumbnails(image, file)

    # 4. Create ExifData
    ExifData.objects.update_or_create(
        image=image,
        defaults={
            'raw_data': exif['raw'],
            'camera': camera,
            'lens': lens,
            'focal_length': exif['focal_length'],
            'aperture': exif['aperture'],
            'shutter_speed': exif['shutter_speed'],
            'iso': exif['iso'],
            'date_taken': exif['date_taken'],
            'gps_latitude': exif['gps_latitude'],
            'gps_longitude': exif['gps_longitude'],
        },
    )

    # 5. Mark as processed
    image.is_processing = False
    image.save(update_fields=['is_processing', 'updated_at'])


def generate_thumbnails(image: Image, file) -> None:
    """Generate small, medium, and large thumbnails from the original."""
    file.seek(0)
    with PILImage.open(file) as img:
        # Validate format
        if img.format and img.format not in ALLOWED_FORMATS:
            raise ValueError(f"Unsupported image format: {img.format}")

        # Preserve orientation from EXIF
        img = _apply_exif_orientation(img)

        # Convert to RGB if needed (for JPEG output)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        for size_name, dimensions in THUMBNAIL_SIZES.items():
            thumb = img.copy()
            thumb.thumbnail(dimensions, PILImage.LANCZOS)

            buffer = BytesIO()
            thumb.save(buffer, format='JPEG', quality=85, optimize=True)
            buffer.seek(0)

            filename = f"{image.id}_{size_name}.jpg"
            field = getattr(image, f'thumbnail_{size_name}')
            field.save(filename, ContentFile(buffer.read()), save=False)

    image.save(update_fields=['thumbnail_small', 'thumbnail_medium', 'thumbnail_large'])


def _apply_exif_orientation(img: PILImage.Image) -> PILImage.Image:
    """Rotate/flip image according to EXIF orientation tag."""
    from PIL import ExifTags

    try:
        exif = img.getexif()
        orientation_key = next(
            k for k, v in ExifTags.TAGS.items() if v == 'Orientation'
        )
        orientation = exif.get(orientation_key)

        rotations = {
            3: 180,
            6: 270,
            8: 90,
        }
        if orientation in rotations:
            img = img.rotate(rotations[orientation], expand=True)
        elif orientation == 2:
            img = img.transpose(PILImage.FLIP_LEFT_RIGHT)
        elif orientation == 4:
            img = img.transpose(PILImage.FLIP_TOP_BOTTOM)
        elif orientation == 5:
            img = img.rotate(270, expand=True).transpose(PILImage.FLIP_LEFT_RIGHT)
        elif orientation == 7:
            img = img.rotate(90, expand=True).transpose(PILImage.FLIP_LEFT_RIGHT)
    except (StopIteration, AttributeError, KeyError):
        pass

    return img
