from datetime import date, timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.shortcuts import render

from appointments.models import Appointment
from files_manager.models import FilePermission, SharedFile
from patients.models import PatientProfile


def home(request):
    return render(request, "patients/home.html")


def microbiota_quiz(request):
    return render(request, "patients/microbiota_quiz.html")


def calendar_view(request):
    return render(request, "patients/calendar.html")


@login_required
def dashboard(request):
    today = date.today()
    user = request.user

    upcoming_appointments = (
        Appointment.objects.filter(
            patient=user,
            status=Appointment.Status.BOOKED,
            date__gte=today,
        )
        .order_by("date", "start_time")
    )

    past_count = Appointment.objects.filter(
        patient=user,
        status=Appointment.Status.COMPLETED,
    ).count()

    # Archivos: públicos + registrados + privados asignados al paciente
    private_ids = FilePermission.objects.filter(patient=user).values_list(
        "shared_file_id", flat=True
    )
    files = SharedFile.objects.filter(
        Q(visibility=SharedFile.Visibility.PUBLIC)
        | Q(visibility=SharedFile.Visibility.REGISTERED)
        | Q(visibility=SharedFile.Visibility.PRIVATE, id__in=private_ids)
    ).order_by("-created_at")

    context = {
        "upcoming_appointments": upcoming_appointments,
        "upcoming_count": upcoming_appointments.count(),
        "past_count": past_count,
        "files_count": files.count(),
        "files": files,
    }
    return render(request, "patients/dashboard.html", context)


@user_passes_test(lambda u: u.is_staff)
def admin_panel(request):
    today = date.today()
    week_end = today + timedelta(days=7)

    total_patients = PatientProfile.objects.count()

    today_appointments = Appointment.objects.filter(
        date=today,
        status__in=[Appointment.Status.BOOKED, Appointment.Status.AVAILABLE],
    ).count()

    week_booked = Appointment.objects.filter(
        date__gte=today,
        date__lte=week_end,
        status=Appointment.Status.BOOKED,
    ).count()

    upcoming_appointments = (
        Appointment.objects.filter(date__gte=today)
        .exclude(status=Appointment.Status.CANCELLED)
        .select_related("patient")
        .order_by("date", "start_time")[:15]
    )

    context = {
        "total_patients": total_patients,
        "today_appointments": today_appointments,
        "week_booked": week_booked,
        "upcoming_appointments": upcoming_appointments,
    }
    return render(request, "patients/admin_panel.html", context)
