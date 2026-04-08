from django.shortcuts import get_object_or_404, render

from core.models import Camera, Lens


def camera_list(request):
    return render(request, 'tree/camera_list.html')


def camera_detail(request, slug):
    camera = get_object_or_404(Camera, slug=slug)
    return render(request, 'tree/camera_detail.html', {'camera': camera})


def lens_list(request):
    return render(request, 'tree/lens_list.html')


def lens_detail(request, slug):
    lens = get_object_or_404(Lens, slug=slug)
    return render(request, 'tree/lens_detail.html', {'lens': lens})
