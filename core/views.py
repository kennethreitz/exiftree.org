from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models.functions import ExtractYear
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import ExifData, Image
from gallery.models import Collection


def home(request):
    year = request.GET.get('year')
    qs = Image.objects.filter(
        visibility=Image.Visibility.PUBLIC, is_processing=False,
    ).select_related('user', 'exif', 'exif__camera', 'exif__lens')

    if year:
        qs = qs.filter(exif__date_taken__year=year)

    import random
    ids = list(qs.values_list('id', flat=True))
    if len(ids) > 48:
        ids = random.sample(ids, 48)
    images = qs.filter(id__in=ids)

    years = (
        ExifData.objects.filter(date_taken__isnull=False)
        .annotate(year=ExtractYear('date_taken'))
        .values_list('year', flat=True)
        .distinct()
        .order_by('-year')
    )

    return render(request, 'home.html', {
        'images': images,
        'years': list(years),
        'selected_year': year,
    })


def image_detail(request, image_id):
    image = get_object_or_404(
        Image.objects.select_related('user', 'exif', 'exif__camera', 'exif__lens'),
        id=image_id, visibility=Image.Visibility.PUBLIC,
    )
    from django.db import models as m
    Image.objects.filter(id=image_id).update(view_count=m.F('view_count') + 1)
    image.view_count += 1

    return render(request, 'image_detail.html', {'image': image})


@login_required
def dashboard(request):
    user = request.user
    images = (
        Image.objects.filter(user=user, is_processing=False)
        .select_related('exif', 'exif__camera', 'exif__lens')
        .order_by('-upload_date')
    )
    collections = (
        Collection.objects.filter(user=user)
        .annotate(image_count=Count('collection_images'))
        .order_by('-created_at')
    )
    return render(request, 'dashboard.html', {
        'images': images,
        'collections': collections,
    })


@login_required
@require_POST
def dashboard_create_collection(request):
    title = request.POST.get('title', '').strip()
    if title:
        from django.utils.text import slugify
        import uuid
        base_slug = slugify(title) or 'collection'
        slug = base_slug
        while Collection.objects.filter(user=request.user, slug=slug).exists():
            slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"
        Collection.objects.create(
            user=request.user,
            title=title,
            slug=slug,
            description=request.POST.get('description', ''),
        )
    return redirect('dashboard')


@login_required
@require_POST
def dashboard_delete_collection(request, collection_id):
    Collection.objects.filter(id=collection_id, user=request.user).delete()
    return redirect('dashboard')


@login_required
@require_POST
def dashboard_delete_image(request, image_id):
    Image.objects.filter(id=image_id, user=request.user).delete()
    return redirect('dashboard')


@login_required
def manage(request):
    images = (
        Image.objects.filter(user=request.user, is_processing=False)
        .select_related('exif', 'exif__camera', 'exif__lens')
        .order_by('-upload_date')
    )
    collections = (
        Collection.objects.filter(user=request.user)
        .annotate(image_count=Count('collection_images'))
        .order_by('-created_at')
    )
    return render(request, 'manage.html', {
        'images': images,
        'collections': collections,
    })


@login_required
@require_POST
def manage_set_visibility(request):
    image_ids = request.POST.getlist('image_ids')
    visibility = request.POST.get('visibility', 'public')
    if visibility in ('public', 'private', 'unlisted') and image_ids:
        Image.objects.filter(id__in=image_ids, user=request.user).update(visibility=visibility)
    return redirect('manage')


@login_required
@require_POST
def manage_delete_images(request):
    image_ids = request.POST.getlist('image_ids')
    if image_ids:
        Image.objects.filter(id__in=image_ids, user=request.user).delete()
    return redirect('manage')


@login_required
@require_POST
def manage_add_to_collection(request):
    from gallery.models import CollectionImage
    image_ids = request.POST.getlist('image_ids')
    collection_id = request.POST.get('collection_id')
    if image_ids and collection_id:
        collection = Collection.objects.filter(id=collection_id, user=request.user).first()
        if collection:
            existing = set(
                CollectionImage.objects.filter(collection=collection, image_id__in=image_ids)
                .values_list('image_id', flat=True)
            )
            count = CollectionImage.objects.filter(collection=collection).count()
            new_entries = []
            for img_id in image_ids:
                import uuid as _uuid
                parsed = _uuid.UUID(img_id)
                if parsed not in existing:
                    new_entries.append(CollectionImage(
                        collection=collection, image_id=parsed, sort_order=count,
                    ))
                    count += 1
            if new_entries:
                CollectionImage.objects.bulk_create(new_entries)
    return redirect('manage')


@login_required
def flickr_import(request):
    return render(request, 'flickr_import.html')
