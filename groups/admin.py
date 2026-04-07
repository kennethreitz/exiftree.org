from django.contrib import admin

from groups.models import Group, GroupImage, GroupMembership


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 1
    raw_id_fields = ['user']


class GroupImageInline(admin.TabularInline):
    model = GroupImage
    extra = 1
    raw_id_fields = ['image']


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'visibility', 'created_at']
    list_filter = ['visibility']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [GroupMembershipInline, GroupImageInline]
