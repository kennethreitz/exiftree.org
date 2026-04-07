"""
EXIF string normalization — maps messy manufacturer/model strings to canonical records.

This is critical infrastructure. EXIF strings are wildly inconsistent across manufacturers.
The pipeline must be idempotent: running normalization twice on the same input produces
the same Camera/Lens record.

The alias tables here will grow over time as we encounter new gear strings in the wild.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.text import slugify

if TYPE_CHECKING:
    from core.models import Camera, Lens

# Canonical manufacturer name mappings.
# Keys are lowercased raw strings, values are the display name we use.
MANUFACTURER_ALIASES: dict[str, str] = {
    'nikon corporation': 'Nikon',
    'nikon': 'Nikon',
    'canon': 'Canon',
    'canon inc.': 'Canon',
    'sony': 'Sony',
    'sony corporation': 'Sony',
    'fujifilm': 'Fujifilm',
    'fujifilm corporation': 'Fujifilm',
    'fuji': 'Fujifilm',
    'fuji film': 'Fujifilm',
    'olympus': 'Olympus',
    'olympus corporation': 'Olympus',
    'olympus imaging corp.': 'Olympus',
    'om digital solutions': 'OM System',
    'panasonic': 'Panasonic',
    'matsushita': 'Panasonic',
    'leica': 'Leica',
    'leica camera ag': 'Leica',
    'pentax': 'Pentax',
    'ricoh imaging': 'Pentax',
    'ricoh imaging company, ltd.': 'Pentax',
    'hasselblad': 'Hasselblad',
    'dji': 'DJI',
    'gopro': 'GoPro',
    'apple': 'Apple',
    'samsung': 'Samsung',
    'sigma': 'Sigma',
    'sigma corporation': 'Sigma',
    'tamron': 'Tamron',
    'tamron co., ltd.': 'Tamron',
    'zeiss': 'Zeiss',
    'carl zeiss': 'Zeiss',
    'samyang': 'Samyang',
    'rokinon': 'Samyang',
    'voigtlander': 'Voigtlander',
    'cosina': 'Voigtlander',
}

# Known camera model aliases: (lowered raw string) -> (manufacturer, model)
# Use this for cases where the raw EXIF string is particularly gnarly.
CAMERA_ALIASES: dict[str, tuple[str, str]] = {
    'nikon z 9': ('Nikon', 'Z 9'),
    'nikon z 8': ('Nikon', 'Z 8'),
    'nikon z 7ii': ('Nikon', 'Z 7II'),
    'nikon z 6iii': ('Nikon', 'Z 6III'),
    'nikon z fc': ('Nikon', 'Z fc'),
    'ilce-7rm5': ('Sony', 'a7R V'),
    'ilce-7rm4': ('Sony', 'a7R IV'),
    'ilce-7m4': ('Sony', 'a7 IV'),
    'ilce-7m3': ('Sony', 'a7 III'),
    'ilce-9m3': ('Sony', 'a9 III'),
    'ilce-6700': ('Sony', 'a6700'),
    'ilce-1': ('Sony', 'a1'),
    'canon eos r5': ('Canon', 'EOS R5'),
    'canon eos r6': ('Canon', 'EOS R6'),
    'canon eos r6m2': ('Canon', 'EOS R6 Mark II'),
    'canon eos r1': ('Canon', 'EOS R1'),
    'x-t5': ('Fujifilm', 'X-T5'),
    'x-t4': ('Fujifilm', 'X-T4'),
    'x-h2s': ('Fujifilm', 'X-H2S'),
    'x-h2': ('Fujifilm', 'X-H2'),
    'x100v': ('Fujifilm', 'X100V'),
    'x100vi': ('Fujifilm', 'X100VI'),
    'gfx100s ii': ('Fujifilm', 'GFX100S II'),
    'iphone 15 pro max': ('Apple', 'iPhone 15 Pro Max'),
    'iphone 15 pro': ('Apple', 'iPhone 15 Pro'),
    'iphone 16 pro max': ('Apple', 'iPhone 16 Pro Max'),
    'iphone 16 pro': ('Apple', 'iPhone 16 Pro'),
}


def normalize_manufacturer(raw: str) -> str:
    """Resolve a raw manufacturer string to a canonical name."""
    cleaned = raw.strip()
    return MANUFACTURER_ALIASES.get(cleaned.lower(), cleaned)


def strip_manufacturer_prefix(manufacturer: str, model_raw: str) -> str:
    """
    Remove redundant manufacturer name from the model string.

    EXIF often gives us things like "NIKON CORPORATION NIKON D850" where
    the make is "NIKON CORPORATION" and the model is "NIKON D850".
    """
    cleaned = model_raw.strip()
    # Try stripping the canonical manufacturer name
    for prefix in [manufacturer, manufacturer.upper(), manufacturer.lower()]:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()
    return cleaned


def normalize_camera_string(make_raw: str, model_raw: str) -> tuple[str, str]:
    """
    Given raw EXIF Make and Model strings, return (manufacturer, model) canonical pair.

    Returns the normalized manufacturer display name and cleaned model name.
    """
    # First check if the full model string (lowered) has a known alias
    model_lower = model_raw.strip().lower()
    if model_lower in CAMERA_ALIASES:
        return CAMERA_ALIASES[model_lower]

    # Check make+model combo
    combo = f"{make_raw.strip()} {model_raw.strip()}".lower()
    if combo in CAMERA_ALIASES:
        return CAMERA_ALIASES[combo]

    # Fall back to heuristic normalization
    manufacturer = normalize_manufacturer(make_raw)
    model_name = strip_manufacturer_prefix(manufacturer, model_raw)

    # If stripping left us with nothing, use the raw model
    if not model_name:
        model_name = model_raw.strip()

    return manufacturer, model_name


def normalize_lens_string(lens_raw: str, make_raw: str = '') -> tuple[str, str]:
    """
    Given a raw EXIF LensModel string, return (manufacturer, model) canonical pair.

    Lens EXIF is even messier than camera EXIF — many lenses don't include
    the manufacturer in the lens string, and third-party lenses may report
    the camera manufacturer instead.
    """
    cleaned = lens_raw.strip()
    if not cleaned:
        return '', ''

    # Try to detect manufacturer from the lens string itself
    cleaned_lower = cleaned.lower()
    detected_manufacturer = ''

    for alias, canonical in MANUFACTURER_ALIASES.items():
        if cleaned_lower.startswith(alias):
            detected_manufacturer = canonical
            cleaned = cleaned[len(alias):].strip()
            break

    # If we didn't detect from lens string, use the camera make as a hint
    if not detected_manufacturer and make_raw:
        detected_manufacturer = normalize_manufacturer(make_raw)

    return detected_manufacturer, cleaned


def get_or_create_camera(make_raw: str, model_raw: str) -> 'Camera':
    """Normalize and get-or-create a canonical Camera record."""
    from core.models import Camera

    manufacturer, model_name = normalize_camera_string(make_raw, model_raw)
    slug = slugify(f"{manufacturer}-{model_name}")

    camera, _created = Camera.objects.get_or_create(
        manufacturer=manufacturer,
        model=model_name,
        defaults={
            'slug': slug,
            'display_name': f"{manufacturer} {model_name}",
        },
    )
    return camera


def get_or_create_lens(lens_raw: str, make_raw: str = '') -> 'Lens | None':
    """Normalize and get-or-create a canonical Lens record. Returns None if no lens data."""
    from core.models import Lens

    manufacturer, model_name = normalize_lens_string(lens_raw, make_raw)
    if not model_name:
        return None

    slug = slugify(f"{manufacturer}-{model_name}" if manufacturer else model_name)

    lens, _created = Lens.objects.get_or_create(
        manufacturer=manufacturer,
        model=model_name,
        defaults={
            'slug': slug,
            'display_name': f"{manufacturer} {model_name}".strip(),
        },
    )
    return lens
