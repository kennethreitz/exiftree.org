from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("tree.urls")),
    path("", include("gallery.urls")),
    path("", include("groups.urls")),
    path("", include("ingest.urls")),
    path("", include("search.urls")),
]
