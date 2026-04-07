from django.urls import path

from ingest import views

app_name = 'ingest'

urlpatterns = [
    path('upload/', views.upload, name='upload'),
    path('upload/submit/', views.upload_image, name='upload-image'),
]
