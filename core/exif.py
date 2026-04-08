"""
EXIF extraction — pulls metadata from image files and returns a structured dict.

Uses exifread for broad format support. Returns both a raw tag dict (for storage)
and parsed fields (for indexing).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any

import exifread


def extract_exif(file) -> dict[str, Any]:
    """
    Extract EXIF data from an image file.

    Accepts a file-like object or Django FieldFile. Returns a dict with:
      - 'raw': dict of all EXIF tags as strings (for JSONField storage)
      - 'make': raw camera make string
      - 'model': raw camera model string
      - 'lens_model': raw lens model string
      - 'focal_length': Decimal in mm or None
      - 'aperture': Decimal f-number or None
      - 'shutter_speed': string representation or ''
      - 'iso': int or None
      - 'date_taken': datetime or None
      - 'gps_latitude': Decimal or None
      - 'gps_longitude': Decimal or None
    """
    # Ensure we're reading from the start
    if hasattr(file, 'seek'):
        file.seek(0)

    # exifread wants a file-like object
    if hasattr(file, 'read'):
        tags = exifread.process_file(file, details=False)
    else:
        tags = exifread.process_file(BytesIO(file), details=False)

    # Build raw dict (all values as strings for JSON serialization)
    raw = {k: str(v) for k, v in tags.items()}

    return {
        'raw': raw,
        'make': _get_str(tags, 'Image Make'),
        'model': _get_str(tags, 'Image Model'),
        'lens_model': _get_str(tags, 'EXIF LensModel'),
        'focal_length': _get_focal_length(tags),
        'aperture': _get_aperture(tags),
        'shutter_speed': _get_shutter_speed(tags),
        'iso': _get_iso(tags),
        'date_taken': _get_date_taken(tags),
        'gps_latitude': _get_gps_coord(tags, 'GPS GPSLatitude', 'GPS GPSLatitudeRef'),
        'gps_longitude': _get_gps_coord(tags, 'GPS GPSLongitude', 'GPS GPSLongitudeRef'),
    }


def _get_str(tags: dict, key: str) -> str:
    val = tags.get(key)
    return str(val).strip() if val else ''


def _get_focal_length(tags: dict) -> Decimal | None:
    val = tags.get('EXIF FocalLength')
    if not val:
        return None
    try:
        return Decimal(str(_ratio_to_float(val)))
    except (InvalidOperation, ValueError, ZeroDivisionError):
        return None


def _get_aperture(tags: dict) -> Decimal | None:
    val = tags.get('EXIF FNumber')
    if not val:
        return None
    try:
        return Decimal(str(_ratio_to_float(val)))
    except (InvalidOperation, ValueError, ZeroDivisionError):
        return None


def _get_shutter_speed(tags: dict) -> str:
    val = tags.get('EXIF ExposureTime')
    return str(val).strip() if val else ''


def _get_iso(tags: dict) -> int | None:
    val = tags.get('EXIF ISOSpeedRatings')
    if not val:
        return None
    try:
        return int(str(val))
    except (ValueError, TypeError):
        return None


def _get_date_taken(tags: dict) -> datetime | None:
    for key in ['EXIF DateTimeOriginal', 'EXIF DateTimeDigitized', 'Image DateTime']:
        val = tags.get(key)
        if val:
            try:
                return datetime.strptime(str(val).strip(), '%Y:%m:%d %H:%M:%S')
            except ValueError:
                continue
    return None


def _get_gps_coord(tags: dict, coord_key: str, ref_key: str) -> Decimal | None:
    coord = tags.get(coord_key)
    ref = tags.get(ref_key)
    if not coord:
        return None
    try:
        values = coord.values
        degrees = _ratio_to_float(values[0])
        minutes = _ratio_to_float(values[1])
        seconds = _ratio_to_float(values[2])
        decimal = degrees + (minutes / 60) + (seconds / 3600)
        if ref and str(ref).strip().upper() in ('S', 'W'):
            decimal = -decimal
        return Decimal(str(round(decimal, 6)))
    except (IndexError, ValueError, ZeroDivisionError, AttributeError):
        return None


def _ratio_to_float(val) -> float:
    """Convert an exifread Ratio or IfdTag value to float."""
    if hasattr(val, 'num') and hasattr(val, 'den'):
        if val.den == 0:
            raise ZeroDivisionError
        return val.num / val.den
    # Some tags come as a list of ratios
    if hasattr(val, 'values') and val.values:
        first = val.values[0]
        if hasattr(first, 'num') and hasattr(first, 'den'):
            if first.den == 0:
                raise ZeroDivisionError
            return first.num / first.den
    return float(str(val))
