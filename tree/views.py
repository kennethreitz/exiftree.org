from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify

from core.models import Camera, ExifData, Image, Lens


def camera_list(request):
    """Grid of all cameras with image counts."""
    cameras = (
        Camera.objects.annotate(image_count=Count('images'))
        .filter(image_count__gt=0)
        .order_by('manufacturer', 'model')
    )
    return render(request, 'tree/camera_list.html', {'cameras': cameras})


def camera_manufacturer(request, manufacturer):
    """All camera models from one manufacturer."""
    cameras = (
        Camera.objects.filter(manufacturer__iexact=manufacturer)
        .annotate(image_count=Count('images'))
        .order_by('model')
    )
    if not cameras.exists():
        # Try slug-based lookup
        cameras = (
            Camera.objects.filter(slug__startswith=manufacturer)
            .annotate(image_count=Count('images'))
            .order_by('model')
        )
    manufacturer_name = cameras.first().manufacturer if cameras.exists() else manufacturer
    return render(request, 'tree/camera_manufacturer.html', {
        'cameras': cameras,
        'manufacturer': manufacturer_name,
    })


def camera_detail(request, manufacturer, model):
    """Gallery of all images shot on a specific camera."""
    camera = get_object_or_404(Camera, slug=f"{manufacturer}-{model}")
    images = (
        Image.objects.filter(
            exif__camera=camera,
            visibility=Image.Visibility.PUBLIC,
            is_processing=False,
        )
        .select_related('user')
        .order_by('-upload_date')
    )
    return render(request, 'tree/camera_detail.html', {
        'camera': camera,
        'images': images,
    })


def lens_list(request):
    """Grid of all lenses with image counts."""
    lenses = (
        Lens.objects.annotate(image_count=Count('images'))
        .filter(image_count__gt=0)
        .order_by('manufacturer', 'model')
    )
    return render(request, 'tree/lens_list.html', {'lenses': lenses})


def lens_detail(request, manufacturer, model):
    """Gallery of all images shot with a specific lens."""
    lens = get_object_or_404(Lens, slug=f"{manufacturer}-{model}")
    images = (
        Image.objects.filter(
            exif__lens=lens,
            visibility=Image.Visibility.PUBLIC,
            is_processing=False,
        )
        .select_related('user')
        .order_by('-upload_date')
    )
    return render(request, 'tree/lens_detail.html', {
        'lens': lens,
        'images': images,
    })
