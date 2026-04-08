from django.shortcuts import render


def upload(request):
    """Upload page — auth is handled client-side via JWT."""
    return render(request, 'ingest/upload.html')
