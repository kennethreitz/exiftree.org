from django.urls import path

from gallery import views

app_name = 'gallery'

urlpatterns = [
    path('@<str:username>/', views.profile, name='profile'),
    path('@<str:username>/collections/', views.collection_list, name='collection-list'),
    path('@<str:username>/collections/<slug:slug>/', views.collection_detail, name='collection-detail'),
]
