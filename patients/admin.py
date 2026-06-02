from django.contrib import admin

from patients.models import ClinicalTimelineEntry, PatientProfile


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "is_approved",
        "approved_at",
        "approved_by",
        "phone",
        "locality",
        "date_of_birth",
        "created_at",
    )
    search_fields = ("user__first_name", "user__last_name", "user__email", "phone")
    list_filter = ("is_approved", "created_at", "approved_at")
    readonly_fields = ("id", "created_at", "updated_at", "approved_at", "approved_by")


@admin.register(ClinicalTimelineEntry)
class ClinicalTimelineEntryAdmin(admin.ModelAdmin):
    list_display = ("patient", "subject", "appointment", "created_by", "created_at")
    search_fields = ("patient__email", "patient__first_name", "patient__last_name", "subject")
    list_filter = ("created_at",)
    readonly_fields = ("id", "created_at")
