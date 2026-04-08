from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path

from core.views import (
    dashboard,
    dashboard_create_collection,
    dashboard_delete_collection,
    dashboard_delete_image,
    flickr_import,
    home,
    image_detail,
    manage,
    manage_add_to_collection,
    manage_delete_images,
    manage_set_visibility,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("login/", LoginView.as_view(template_name='registration/login.html'), name="login"),
    path("logout/", LogoutView.as_view(next_page='/'), name="logout"),
    path("dashboard/", dashboard, name="dashboard"),
    path("dashboard/collections/create/", dashboard_create_collection, name="dashboard-create-collection"),
    path("dashboard/collections/<uuid:collection_id>/delete/", dashboard_delete_collection, name="dashboard-delete-collection"),
    path("dashboard/images/<uuid:image_id>/delete/", dashboard_delete_image, name="dashboard-delete-image"),
    path("manage/", manage, name="manage"),
    path("manage/visibility/", manage_set_visibility, name="manage-set-visibility"),
    path("manage/delete/", manage_delete_images, name="manage-delete-images"),
    path("manage/add-to-collection/", manage_add_to_collection, name="manage-add-to-collection"),
    path("import/flickr/", flickr_import, name="flickr-import"),
    path("images/<uuid:image_id>/", image_detail, name="image-detail"),
    path("", include("tree.urls")),
    path("", include("gallery.urls")),
    path("", include("ingest.urls")),
    path("", include("search.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
