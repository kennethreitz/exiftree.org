from django.shortcuts import get_object_or_404, render

from core.models import Camera, Lens


def camera_list(request):
    return render(request, 'tree/camera_list.html')


def camera_manufacturer(request, manufacturer):
    # Pass manufacturer to template for the page title
    cameras = Camera.objects.filter(slug__startswith=manufacturer)
    manufacturer_name = cameras.first().manufacturer if cameras.exists() else manufacturer
    return render(request, 'tree/camera_manufacturer.html', {
        'manufacturer': manufacturer_name,
        'cameras': cameras,
    })


def camera_detail(request, manufacturer, model):
    camera = get_object_or_404(Camera, slug=f"{manufacturer}-{model}")
    return render(request, 'tree/camera_detail.html', {'camera': camera})


def lens_list(request):
    return render(request, 'tree/lens_list.html')


def lens_detail(request, manufacturer, model):
    lens = get_object_or_404(Lens, slug=model)
    return render(request, 'tree/lens_detail.html', {'lens': lens})
