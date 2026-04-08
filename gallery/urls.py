from django.urls import path

from gallery import views

app_name = 'gallery'

urlpatterns = [
    path('collections/', views.collection_list, name='collection-list'),
    path('collections/<slug:slug>/', views.collection_detail, name='collection-detail'),
]
