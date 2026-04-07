from django.contrib import admin

from gallery.models import Collection, CollectionImage


class CollectionImageInline(admin.TabularInline):
    model = CollectionImage
    extra = 1
    raw_id_fields = ['image']


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'visibility', 'created_at']
    list_filter = ['visibility']
    search_fields = ['title', 'user__username']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [CollectionImageInline]
