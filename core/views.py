from django.shortcuts import render


def home(request):
    return render(request, 'home.html')


def image_detail(request, image_id):
    return render(request, 'image_detail.html', {'image_id': image_id})


def dashboard(request):
    return render(request, 'dashboard.html')


def users_list(request):
    return render(request, 'users.html')


def register_view(request):
    return render(request, 'registration/register.html')


def login_view(request):
    return render(request, 'registration/login.html')
