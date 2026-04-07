from django.urls import path

from search import views

app_name = 'search'

urlpatterns = [
    path('search/', views.search, name='search'),
]
