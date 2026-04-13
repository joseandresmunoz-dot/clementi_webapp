from django.contrib import admin

from appointments.models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("date", "start_time", "end_time", "status", "patient", "google_meet_link")
    list_filter = ("status", "date")
    search_fields = ("patient__first_name", "patient__last_name", "patient__email")
    readonly_fields = ("id", "google_event_id", "google_meet_link", "created_at", "updated_at")
    date_hierarchy = "date"
