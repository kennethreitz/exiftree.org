from django.shortcuts import get_object_or_404, render

from groups.models import Group


def group_list(request):
    return render(request, 'groups/group_list.html')


def group_detail(request, slug):
    group = get_object_or_404(Group, slug=slug)
    return render(request, 'groups/group_detail.html', {'group': group})


def group_members(request, slug):
    group = get_object_or_404(Group, slug=slug)
    return render(request, 'groups/group_members.html', {'group': group})
