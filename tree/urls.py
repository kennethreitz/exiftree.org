from django.urls import path

from tree import views

app_name = 'tree'

urlpatterns = [
    path('cameras/', views.camera_list, name='camera-list'),
    path('cameras/<slug:slug>/', views.camera_detail, name='camera-detail'),
    path('lenses/', views.lens_list, name='lens-list'),
    path('lenses/<slug:slug>/', views.lens_detail, name='lens-detail'),
]
