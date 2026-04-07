"""
ExifTree API — powered by django-bolt.

Run with: python manage.py runbolt --dev
OpenAPI docs available at /api/docs/
"""

from django_bolt import BoltAPI

from core.models import Camera, ExifData, Image, Lens, User
from gallery.models import Collection, CollectionImage
from groups.models import Group, GroupMembership

import msgspec


# --- Schemas ---

class UserSchema(msgspec.Struct):
    id: str
    username: str
    bio: str
    website: str


class CameraSchema(msgspec.Struct):
    id: str
    manufacturer: str
    model: str
    slug: str
    display_name: str


class LensSchema(msgspec.Struct):
    id: str
    manufacturer: str
    model: str
    slug: str
    display_name: str
    max_aperture: float | None = None


class ExifSchema(msgspec.Struct):
    camera: CameraSchema | None = None
    lens: LensSchema | None = None
    focal_length: float | None = None
    aperture: float | None = None
    shutter_speed: str = ''
    iso: int | None = None
    date_taken: str | None = None


class ImageSchema(msgspec.Struct):
    id: str
    title: str
    slug: str
    description: str
    user: UserSchema
    visibility: str
    upload_date: str
    view_count: int
    exif: ExifSchema | None = None


class ImageListSchema(msgspec.Struct):
    id: str
    title: str
    slug: str
    user: str
    upload_date: str
    thumbnail_small: str


class CollectionSchema(msgspec.Struct):
    id: str
    title: str
    slug: str
    description: str
    visibility: str
    image_count: int


class GroupSchema(msgspec.Struct):
    id: str
    name: str
    slug: str
    description: str
    visibility: str
    member_count: int


# --- Helpers ---

def _camera_to_schema(c: Camera) -> CameraSchema:
    return CameraSchema(
        id=str(c.id), manufacturer=c.manufacturer, model=c.model,
        slug=c.slug, display_name=c.display_name,
    )


def _lens_to_schema(l: Lens) -> LensSchema:
    return LensSchema(
        id=str(l.id), manufacturer=l.manufacturer, model=l.model,
        slug=l.slug, display_name=l.display_name,
        max_aperture=float(l.max_aperture) if l.max_aperture else None,
    )


def _user_to_schema(u: User) -> UserSchema:
    return UserSchema(id=str(u.id), username=u.username, bio=u.bio, website=u.website)


def _image_to_list_schema(img: Image) -> ImageListSchema:
    return ImageListSchema(
        id=str(img.id), title=img.title, slug=img.slug,
        user=img.user.username, upload_date=img.upload_date.isoformat(),
        thumbnail_small=img.thumbnail_small.url if img.thumbnail_small else '',
    )


def _image_to_schema(img: Image) -> ImageSchema:
    exif_data = None
    try:
        exif = img.exif
        exif_data = ExifSchema(
            camera=_camera_to_schema(exif.camera) if exif.camera else None,
            lens=_lens_to_schema(exif.lens) if exif.lens else None,
            focal_length=float(exif.focal_length) if exif.focal_length else None,
            aperture=float(exif.aperture) if exif.aperture else None,
            shutter_speed=exif.shutter_speed,
            iso=exif.iso,
            date_taken=exif.date_taken.isoformat() if exif.date_taken else None,
        )
    except ExifData.DoesNotExist:
        pass

    return ImageSchema(
        id=str(img.id), title=img.title, slug=img.slug,
        description=img.description, user=_user_to_schema(img.user),
        visibility=img.visibility, upload_date=img.upload_date.isoformat(),
        view_count=img.view_count, exif=exif_data,
    )


# --- API ---

api = BoltAPI(prefix="/api")


@api.get("/cameras")
async def list_cameras() -> list[CameraSchema]:
    cameras = []
    async for c in Camera.objects.order_by('manufacturer', 'model'):
        cameras.append(_camera_to_schema(c))
    return cameras


@api.get("/cameras/{camera_id}")
async def get_camera(camera_id: str) -> CameraSchema:
    c = await Camera.objects.aget(id=camera_id)
    return _camera_to_schema(c)


@api.get("/cameras/{camera_id}/images")
async def camera_images(camera_id: str) -> list[ImageListSchema]:
    images = []
    qs = (
        Image.objects.filter(
            exif__camera_id=camera_id,
            visibility=Image.Visibility.PUBLIC,
            is_processing=False,
        )
        .select_related('user')
        .order_by('-upload_date')[:50]
    )
    async for img in qs:
        images.append(_image_to_list_schema(img))
    return images


@api.get("/lenses")
async def list_lenses() -> list[LensSchema]:
    lenses = []
    async for l in Lens.objects.order_by('manufacturer', 'model'):
        lenses.append(_lens_to_schema(l))
    return lenses


@api.get("/lenses/{lens_id}")
async def get_lens(lens_id: str) -> LensSchema:
    l = await Lens.objects.aget(id=lens_id)
    return _lens_to_schema(l)


@api.get("/lenses/{lens_id}/images")
async def lens_images(lens_id: str) -> list[ImageListSchema]:
    images = []
    qs = (
        Image.objects.filter(
            exif__lens_id=lens_id,
            visibility=Image.Visibility.PUBLIC,
            is_processing=False,
        )
        .select_related('user')
        .order_by('-upload_date')[:50]
    )
    async for img in qs:
        images.append(_image_to_list_schema(img))
    return images


@api.get("/images/{image_id}")
async def get_image(image_id: str) -> ImageSchema:
    img = await (
        Image.objects.select_related('user', 'exif', 'exif__camera', 'exif__lens')
        .aget(id=image_id, visibility=Image.Visibility.PUBLIC, is_processing=False)
    )
    return _image_to_schema(img)


@api.get("/users/{username}")
async def get_user(username: str) -> UserSchema:
    u = await User.objects.aget(username=username)
    return _user_to_schema(u)


@api.get("/users/{username}/images")
async def user_images(username: str) -> list[ImageListSchema]:
    images = []
    qs = (
        Image.objects.filter(
            user__username=username,
            visibility=Image.Visibility.PUBLIC,
            is_processing=False,
        )
        .select_related('user')
        .order_by('-upload_date')[:50]
    )
    async for img in qs:
        images.append(_image_to_list_schema(img))
    return images


@api.get("/users/{username}/collections")
async def user_collections(username: str) -> list[CollectionSchema]:
    collections = []
    qs = (
        Collection.objects.filter(
            user__username=username,
            visibility=Image.Visibility.PUBLIC,
        )
        .order_by('-created_at')
    )
    async for c in qs:
        count = await CollectionImage.objects.filter(collection=c).acount()
        collections.append(CollectionSchema(
            id=str(c.id), title=c.title, slug=c.slug,
            description=c.description, visibility=c.visibility,
            image_count=count,
        ))
    return collections


@api.get("/groups")
async def list_groups() -> list[GroupSchema]:
    groups = []
    qs = Group.objects.filter(visibility=Group.Visibility.PUBLIC).order_by('-created_at')
    async for g in qs:
        count = await GroupMembership.objects.filter(group=g).acount()
        groups.append(GroupSchema(
            id=str(g.id), name=g.name, slug=g.slug,
            description=g.description, visibility=g.visibility,
            member_count=count,
        ))
    return groups


@api.get("/groups/{slug}")
async def get_group(slug: str) -> GroupSchema:
    g = await Group.objects.aget(slug=slug)
    count = await GroupMembership.objects.filter(group=g).acount()
    return GroupSchema(
        id=str(g.id), name=g.name, slug=g.slug,
        description=g.description, visibility=g.visibility,
        member_count=count,
    )
