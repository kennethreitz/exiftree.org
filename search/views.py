from django.shortcuts import render

from core.models import Camera, Image, Lens


def search(request):
    """EXIF-powered search and filtering."""
    images = Image.objects.filter(
        visibility=Image.Visibility.PUBLIC,
        is_processing=False,
    ).select_related('user', 'exif', 'exif__camera', 'exif__lens')

    q = request.GET.get('q', '').strip()
    camera_id = request.GET.get('camera')
    lens_id = request.GET.get('lens')
    focal_min = request.GET.get('focal_min')
    focal_max = request.GET.get('focal_max')
    aperture_min = request.GET.get('aperture_min')
    aperture_max = request.GET.get('aperture_max')
    iso_min = request.GET.get('iso_min')
    iso_max = request.GET.get('iso_max')

    if q:
        images = images.filter(title__icontains=q) | images.filter(description__icontains=q)
    if camera_id:
        images = images.filter(exif__camera_id=camera_id)
    if lens_id:
        images = images.filter(exif__lens_id=lens_id)
    if focal_min:
        images = images.filter(exif__focal_length__gte=focal_min)
    if focal_max:
        images = images.filter(exif__focal_length__lte=focal_max)
    if aperture_min:
        images = images.filter(exif__aperture__gte=aperture_min)
    if aperture_max:
        images = images.filter(exif__aperture__lte=aperture_max)
    if iso_min:
        images = images.filter(exif__iso__gte=iso_min)
    if iso_max:
        images = images.filter(exif__iso__lte=iso_max)

    images = images.order_by('-upload_date')

    cameras = Camera.objects.order_by('manufacturer', 'model')
    lenses = Lens.objects.order_by('manufacturer', 'model')

    return render(request, 'search/search.html', {
        'images': images,
        'cameras': cameras,
        'lenses': lenses,
        'query': q,
    })
