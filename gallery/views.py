from django.shortcuts import get_object_or_404, render

from core.models import User
from gallery.models import Collection


def profile(request, username):
    user = get_object_or_404(User, username=username)
    return render(request, 'gallery/profile.html', {'profile_user': user})


def collection_list(request, username):
    user = get_object_or_404(User, username=username)
    return render(request, 'gallery/collection_list.html', {'profile_user': user})


def collection_detail(request, username, slug):
    user = get_object_or_404(User, username=username)
    collection = get_object_or_404(Collection, user=user, slug=slug)
    return render(request, 'gallery/collection_detail.html', {
        'profile_user': user,
        'collection': collection,
    })
