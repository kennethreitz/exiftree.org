from django.db.models import Count
from django.shortcuts import get_object_or_404, render

from core.models import Image

from groups.models import Group


def group_list(request):
    """Browse all public groups."""
    groups = (
        Group.objects.filter(visibility=Group.Visibility.PUBLIC)
        .annotate(member_count=Count('memberships'))
        .order_by('-created_at')
    )
    return render(request, 'groups/group_list.html', {'groups': groups})


def group_detail(request, slug):
    """Group page with member images."""
    group = get_object_or_404(Group, slug=slug)
    images = (
        Image.objects.filter(
            group_entries__group=group,
            visibility=Image.Visibility.PUBLIC,
            is_processing=False,
        )
        .select_related('user')
        .order_by('-group_entries__submitted_at')
    )
    return render(request, 'groups/group_detail.html', {
        'group': group,
        'images': images,
    })


def group_members(request, slug):
    """Member list for a group."""
    group = get_object_or_404(Group, slug=slug)
    memberships = (
        group.memberships.select_related('user')
        .order_by('role', 'joined_at')
    )
    return render(request, 'groups/group_members.html', {
        'group': group,
        'memberships': memberships,
    })
