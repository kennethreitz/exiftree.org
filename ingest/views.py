from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from core.models import Image

from ingest.tasks import process_image_task


@login_required
def upload(request):
    """Upload page — renders the form on GET."""
    return render(request, 'ingest/upload.html')


@login_required
@require_POST
def upload_image(request):
    """Handle image upload. Validates, saves, kicks off async processing."""
    file = request.FILES.get('image')
    if not file:
        return JsonResponse({'error': "No image provided"}, status=400)

    if file.size > settings.MAX_UPLOAD_SIZE:
        return JsonResponse({'error': "File too large"}, status=400)

    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()

    image = Image.objects.create(
        user=request.user,
        title=title,
        description=description,
        slug=slugify(title) if title else slugify(str(file.name).rsplit('.', 1)[0]),
        original=file,
        is_processing=True,
    )

    process_image_task.delay(str(image.id))

    return JsonResponse({
        'id': str(image.id),
        'status': 'processing',
    }, status=201)
