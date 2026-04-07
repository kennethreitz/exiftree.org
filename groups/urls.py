from django.urls import path

from groups import views

app_name = 'groups'

urlpatterns = [
    path('groups/', views.group_list, name='group-list'),
    path('groups/<slug:slug>/', views.group_detail, name='group-detail'),
    path('groups/<slug:slug>/members/', views.group_members, name='group-members'),
]
