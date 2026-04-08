from django.db.models import Count
from django.shortcuts import get_object_or_404, render

from core.models import Image
from gallery.models import Collection


def collection_list(request):
    collections = (
        Collection.objects.filter(visibility=Image.Visibility.PUBLIC)
        .annotate(image_count=Count('collection_images'))
        .order_by('-created_at')
    )
    return render(request, 'gallery/collection_list.html', {
        'collections': collections,
    })


def collection_detail(request, slug):
    collection = get_object_or_404(Collection, slug=slug)
    images = (
        Image.objects.filter(
            collection_entries__collection=collection, is_processing=False
        )
        .select_related('exif', 'exif__camera', 'exif__lens')
        .order_by('collection_entries__sort_order')
    )
    return render(request, 'gallery/collection_detail.html', {
        'collection': collection,
        'images': images,
    })
