import hashlib

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from core.models import Image
from gallery.models import Collection
from ingest.tasks import process_image_task


@login_required
def upload(request):
    collections = Collection.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'ingest/upload.html', {'collections': collections})


@login_required
@require_POST
def upload_image(request):
    """Handle image upload via XHR, return JSON."""
    image_file = request.FILES.get('image')
    if not image_file:
        return JsonResponse({'detail': "No image provided"}, status=400)

    from django.conf import settings
    if image_file.size > settings.MAX_UPLOAD_SIZE:
        return JsonResponse({'detail': "File too large"}, status=400)

    contents = image_file.read()
    content_hash = hashlib.sha256(contents).hexdigest()

    existing = Image.objects.filter(content_hash=content_hash).first()
    if existing:
        return JsonResponse({'detail': "Duplicate image", 'id': str(existing.id)}, status=409)

    title = request.POST.get('title', '')
    slug = slugify(title) if title else slugify(image_file.name.rsplit('.', 1)[0])

    from django.core.files.base import ContentFile
    img = Image.objects.create(
        user=request.user,
        title=title,
        slug=slug,
        original=ContentFile(contents, name=image_file.name),
        content_hash=content_hash,
        is_processing=True,
    )

    try:
        process_image_task.apply_async(args=[str(img.id)], ignore_result=True)
    except Exception:
        from ingest.pipeline import process_image
        process_image(img)

    return JsonResponse({'id': str(img.id), 'title': img.title}, status=201)
