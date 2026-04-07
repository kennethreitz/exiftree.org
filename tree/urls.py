from django.urls import path

from tree import views

app_name = 'tree'

urlpatterns = [
    path('cameras/', views.camera_list, name='camera-list'),
    path('cameras/<slug:manufacturer>/', views.camera_manufacturer, name='camera-manufacturer'),
    path('cameras/<slug:manufacturer>/<slug:model>/', views.camera_detail, name='camera-detail'),
    path('lenses/', views.lens_list, name='lens-list'),
    path('lenses/<slug:manufacturer>/<slug:model>/', views.lens_detail, name='lens-detail'),
]
