"""
ASGI config for exiftree project.

Bolt is the root server — Django is mounted into it for admin,
templates, and traditional views. The API is handled natively by Bolt.

Run with: python manage.py runbolt --dev
"""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "exiftree.settings")
django.setup()

from exiftree.api import api  # noqa: E402

# Mount Django's ASGI app for admin + template views
api.mount_django("/", clear_root_path=True)

application = api
