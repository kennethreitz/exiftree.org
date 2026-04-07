from django.contrib import admin
from django.urls import include, path

from core.views import home, image_detail, login_view, register_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("login/", login_view, name="login"),
    path("register/", register_view, name="register"),
    path("images/<uuid:image_id>/", image_detail, name="image-detail"),
    path("", include("tree.urls")),
    path("", include("gallery.urls")),
    path("", include("groups.urls")),
    path("", include("ingest.urls")),
    path("", include("search.urls")),
]
