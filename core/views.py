from django.shortcuts import render


def home(request):
    return render(request, 'home.html')


def image_detail(request, image_id):
    return render(request, 'image_detail.html', {'image_id': image_id})


def register_view(request):
    return render(request, 'registration/register.html')


def login_view(request):
    return render(request, 'registration/login.html')
