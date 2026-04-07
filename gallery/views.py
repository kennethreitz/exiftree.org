from django.shortcuts import get_object_or_404, render

from core.models import Image, User

from gallery.models import Collection


def profile(request, username):
    """User profile — shows their public uploads."""
    user = get_object_or_404(User, username=username)
    images = (
        Image.objects.filter(user=user, is_processing=False)
        .order_by('-upload_date')
    )
    # Hide private images from other users
    if request.user != user:
        images = images.filter(visibility=Image.Visibility.PUBLIC)

    return render(request, 'gallery/profile.html', {
        'profile_user': user,
        'images': images,
    })


def collection_list(request, username):
    """All collections for a user."""
    user = get_object_or_404(User, username=username)
    collections = Collection.objects.filter(user=user)
    if request.user != user:
        collections = collections.filter(visibility=Image.Visibility.PUBLIC)

    return render(request, 'gallery/collection_list.html', {
        'profile_user': user,
        'collections': collections,
    })


def collection_detail(request, username, slug):
    """Single collection view."""
    user = get_object_or_404(User, username=username)
    collection = get_object_or_404(Collection, user=user, slug=slug)

    # Visibility check
    if collection.visibility != Image.Visibility.PUBLIC and request.user != user:
        from django.http import Http404
        raise Http404

    images = (
        Image.objects.filter(
            collection_entries__collection=collection,
            is_processing=False,
        )
        .order_by('collection_entries__sort_order')
    )

    return render(request, 'gallery/collection_detail.html', {
        'profile_user': user,
        'collection': collection,
        'images': images,
    })
