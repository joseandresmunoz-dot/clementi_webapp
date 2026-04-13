from django.contrib import admin

from files_manager.models import FilePermission, SharedFile


class FilePermissionInline(admin.TabularInline):
    model = FilePermission
    extra = 1
    autocomplete_fields = ("patient",)


@admin.register(SharedFile)
class SharedFileAdmin(admin.ModelAdmin):
    list_display = ("title", "file_type", "visibility", "uploaded_by", "created_at")
    list_filter = ("visibility", "file_type", "created_at")
    search_fields = ("title", "description")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [FilePermissionInline]


@admin.register(FilePermission)
class FilePermissionAdmin(admin.ModelAdmin):
    list_display = ("shared_file", "patient", "granted_at")
    list_filter = ("granted_at",)
    autocomplete_fields = ("shared_file", "patient")
