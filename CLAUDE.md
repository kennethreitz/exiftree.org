# CLAUDE.md

## Project

ExifTree — a personal photography portfolio organized by the gear, places, and subjects that define it. AI-powered metadata, EXIF-based discovery, infinite scroll.

**Live:** photos.kennethreitz.org
**Stack:** Django 6.x · Python 3.14 · PostgreSQL · Celery · django-bolt · Tigris (S3) · OpenAI

## Architecture

Single-tenant. One owner account. No public registration, no multi-user features.

### Apps

- `core` — Models (User, Image, ExifData, Camera, Lens, Tag, City, SiteConfig). Other apps import from here.
- `tree` — Browse pages: cameras, lenses, tags, cities. No models.
- `gallery` — Collections for organizing photos.
- `ingest` — Upload pipeline, EXIF extraction, thumbnail generation, AI description, geocoding.
- `search` — EXIF-powered search across all metadata including AI fields.

### Key Models

- **Image** — photos with thumbnails, AI title/description, tags (M2M), city (FK), visibility
- **ExifData** — parsed EXIF + raw JSON blob, linked to Camera/Lens
- **Tag** — AI-generated, used for word cloud browsing
- **City** — reverse-geocoded from GPS, grouped by continent/country/state
- **SiteConfig** — singleton for site title, tagline, analytics code, OpenAI key, AI prompt

### Image Pipeline (ingest)

1. Validate → 2. Extract EXIF → 3. Normalize camera/lens → 4. Perceptual hash → 5. Generate thumbnails → 6. Create ExifData → 7. Reverse geocode to city → 8. Apply cleanup rules → 9. Mark processed

AI description happens async after processing via Celery task.

### Cleanup Rules

Defined in `core/management/commands/cleanup.py` and `ingest/pipeline.py`:
- Delete: 2008, 2019, 2020, Dec 26 2014, Dec 22 2017
- Fix: clear dates before 2008 and 2021+
- Cities: block CN, JP, KG, MN, RU. India only allows Bangalore/Mysore.

## Code Style

- Python: PEP 8, type hints on function signatures
- Django: fat models, thin views
- Imports: stdlib → third-party → django → local apps
- Strings: double quotes for user-facing, single quotes for identifiers
- Templates: HTMX for interactivity, vanilla JS only where required (upload, manage multi-select)

## Models

- UUIDField primary keys everywhere
- created_at/updated_at timestamps on every model
- SlugField on anything in a URL
- ExifData keeps raw JSON — never discard it

## Frontend

Django templates + HTMX. No frontend framework. Minimal JS. Session auth (not JWT).

## URLs

- `/cameras/`, `/cameras/<slug>/`
- `/lenses/`, `/lenses/<slug>/`
- `/tags/`, `/tags/<slug>/`
- `/cities/`, `/cities/<slug>/`
- `/collections/`, `/collections/<slug>/`
- `/images/<uuid>/`
- `/manage/`, `/upload/`, `/dashboard/`, `/search/`

## Infrastructure

- **Fly.io**: web (runbolt) + worker (celery) processes
- **PostgreSQL**: Fly Postgres, also Celery broker via SQLAlchemy transport
- **Tigris**: S3-compatible object storage for images (used locally and in prod)
- **Redis**: local Celery broker (brew service)
- **python-dotenv**: .env loaded automatically via manage.py

## When Working on This

- Don't add dependencies without discussing tradeoffs
- Write reversible migrations
- Keep cleanup rules in the cleanup command, mirrored in pipeline.py
- Invalid GPS countries are blocked in City.from_coordinates, pipeline, geocode command, AND cleanup
- The `ai_describe --tail` command watches for new images continuously
- Restart Celery workers after code changes (`kill` + re-launch)
