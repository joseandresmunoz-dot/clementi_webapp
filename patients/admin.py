from django.contrib import admin

from patients.models import PatientProfile


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "date_of_birth", "created_at")
    search_fields = ("user__first_name", "user__last_name", "user__email", "phone")
    list_filter = ("created_at",)
    readonly_fields = ("id", "created_at", "updated_at")
