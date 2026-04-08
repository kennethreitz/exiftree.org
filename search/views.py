from django.shortcuts import render

from core.models import Camera, Image, Lens


def search(request):
    cameras = Camera.objects.order_by('manufacturer', 'model')
    lenses = Lens.objects.order_by('manufacturer', 'model')

    qs = Image.objects.filter(
        visibility=Image.Visibility.PUBLIC, is_processing=False,
    ).select_related('user', 'exif', 'exif__camera', 'exif__lens')

    q = request.GET.get('q', '')
    camera = request.GET.get('camera', '')
    lens = request.GET.get('lens', '')
    focal_min = request.GET.get('focal_min', '')
    focal_max = request.GET.get('focal_max', '')
    aperture_min = request.GET.get('aperture_min', '')
    aperture_max = request.GET.get('aperture_max', '')
    iso_min = request.GET.get('iso_min', '')
    iso_max = request.GET.get('iso_max', '')

    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(ai_title__icontains=q) |
            Q(ai_description__icontains=q) |
            Q(tags__name__icontains=q)
        ).distinct()
    if camera:
        qs = qs.filter(exif__camera_id=camera)
    if lens:
        qs = qs.filter(exif__lens_id=lens)
    if focal_min:
        qs = qs.filter(exif__focal_length__gte=float(focal_min))
    if focal_max:
        qs = qs.filter(exif__focal_length__lte=float(focal_max))
    if aperture_min:
        qs = qs.filter(exif__aperture__gte=float(aperture_min))
    if aperture_max:
        qs = qs.filter(exif__aperture__lte=float(aperture_max))
    if iso_min:
        qs = qs.filter(exif__iso__gte=int(iso_min))
    if iso_max:
        qs = qs.filter(exif__iso__lte=int(iso_max))

    images = qs.order_by('-upload_date')[:50]
    total = qs.count()

    return render(request, 'search/search.html', {
        'cameras': cameras,
        'lenses': lenses,
        'images': images,
        'total': total,
        'q': q,
        'camera': camera,
        'lens': lens,
        'focal_min': focal_min,
        'focal_max': focal_max,
        'aperture_min': aperture_min,
        'aperture_max': aperture_max,
        'iso_min': iso_min,
        'iso_max': iso_max,
    })
