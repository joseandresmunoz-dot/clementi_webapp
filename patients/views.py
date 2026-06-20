from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from appointments.models import Appointment
from files_manager.models import FilePermission, SharedFile
from patients.models import ClinicalTimelineEntry, PatientProfile


from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseRedirect
from patients.models import Lead


@require_POST
def capture_lead(request):
    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()
    phone = request.POST.get("phone", "").strip()
    message = request.POST.get("message", "").strip()
    source = request.POST.get("source", "landing")
    is_subscribed = request.POST.get("is_subscribed", "1") == "1"

    if not name or not email:
        messages.error(request, "Nombre y email son obligatorios.")
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/") + "#contacto")

    Lead.objects.create(
        name=name,
        email=email,
        phone=phone,
        message=message,
        source=source,
        is_subscribed=is_subscribed,
    )
    messages.success(request, "¡Gracias! Te contactaremos pronto.")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/") + "#contacto")


@csrf_exempt
def debug_login(request):
    import traceback
    from django.conf import settings as dj_settings
    from django.contrib.auth import authenticate, login
    from django.http import JsonResponse, HttpResponse
    from allauth import app_settings as allauth_settings

    if request.method == "POST":
        data = {}
        data["method"] = request.method
        data["is_secure"] = request.is_secure()
        data["scheme"] = request.scheme
        data["META_HTTP_REFERER"] = request.META.get("HTTP_REFERER", "")
        data["META_HTTP_ORIGIN"] = request.META.get("HTTP_ORIGIN", "")
        data["META_HTTP_HOST"] = request.META.get("HTTP_HOST", "")
        data["META_CSRF_COOKIE_USED"] = request.META.get("CSRF_COOKIE_USED", False)
        data["META_CSRF_COOKIE_NEEDS_UPDATE"] = request.META.get("CSRF_COOKIE_NEEDS_UPDATE", False)
        data["META_CSRF_COOKIE"] = request.META.get("CSRF_COOKIE", "NOT SET")
        data["COOKIES"] = dict(request.COOKIES)
        data["POST_keys"] = list(request.POST.keys())
        data["login"] = request.POST.get("login", "")
        data["has_pw"] = bool(request.POST.get("password", ""))
        data["ALLOWED_HOSTS"] = dj_settings.ALLOWED_HOSTS
        data["CSRF_TRUSTED_ORIGINS"] = dj_settings.CSRF_TRUSTED_ORIGINS
        data["CSRF_COOKIE_DOMAIN"] = dj_settings.CSRF_COOKIE_DOMAIN
        data["CSRF_COOKIE_NAME"] = dj_settings.CSRF_COOKIE_NAME
        data["SESSION_COOKIE_DOMAIN"] = dj_settings.SESSION_COOKIE_DOMAIN
        data["DJANGO_ALLOWED_HOSTS"] = dj_settings.ALLOWED_HOSTS
        data["SOCIALACCOUNT_ONLY"] = getattr(dj_settings, "SOCIALACCOUNT_ONLY", "NOT SET")
        data["ALLAUTH_SOCIALACCOUNT_ONLY"] = allauth_settings.SOCIALACCOUNT_ONLY

        email = request.POST.get("login", "")
        password = request.POST.get("password", "")
        try:
            user = authenticate(request, email=email, password=password)
            data["authenticate_result"] = str(user) if user else "None"
            if user:
                data["user_active"] = user.is_active
                data["user_staff"] = user.is_staff
                data["user_backend"] = getattr(user, "backend", "NO BACKEND")
                try:
                    login(request, user)
                    data["login_success"] = True
                except Exception as e:
                    data["login_error"] = str(e)
                    data["login_traceback"] = traceback.format_exc()
            else:
                data["auth_failed"] = True
        except Exception as e:
            data["exception"] = str(e)
            data["traceback"] = traceback.format_exc()

        return JsonResponse(data)

    return HttpResponse("Use POST with login=email&password=xxx")


def home(request):
    if request.user.is_authenticated:
        if not _is_patient_approved(request.user) and not request.user.is_staff:
            return redirect("patients:pending_approval")
    return render(request, "landing.html")


@login_required
def microbiota_quiz(request):
    if request.user.is_authenticated and not _is_patient_approved(request.user):
        messages.warning(
            request,
            "Tu cuenta aún no fue aprobada por administración."
            " Te avisaremos cuando se habilite.",
        )
        return redirect("patients:pending_approval")
    return render(request, "patients/microbiota_quiz.html")


@login_required
def calendar_view(request):
    if request.user.is_authenticated and not _is_patient_approved(request.user):
        messages.warning(
            request,
            "Tu cuenta aún no fue aprobada por administración."
            " Te avisaremos cuando se habilite.",
        )
        return redirect("patients:pending_approval")
    return render(request, "patients/calendar.html")


def _is_patient_approved(user):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    profile = getattr(user, "patient_profile", None)
    return bool(profile and profile.is_approved)


def _calculate_age(date_of_birth):
    if not date_of_birth:
        return None
    today = date.today()
    years = today.year - date_of_birth.year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        years -= 1
    return years


@login_required
def dashboard(request):
    if not _is_patient_approved(request.user):
        messages.warning(
            request,
            "Tu cuenta aún no fue aprobada por administración."
            " Te avisaremos cuando se habilite.",
        )
        return redirect("patients:pending_approval")

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

    timeline_entries = ClinicalTimelineEntry.objects.filter(patient=user).select_related("created_by", "appointment")

    context = {
        "upcoming_appointments": upcoming_appointments,
        "upcoming_count": upcoming_appointments.count(),
        "past_count": past_count,
        "files_count": files.count(),
        "files": files,
        "timeline_entries": timeline_entries,
    }
    return render(request, "patients/dashboard.html", context)


@login_required
def pending_approval(request):
    if request.user.is_staff:
        return redirect("patients:admin_panel")
    if _is_patient_approved(request.user):
        return redirect("patients:dashboard")
    return render(request, "patients/pending_approval.html")


@user_passes_test(lambda u: u.is_staff)
def patients_admin_list(request):
    patients_qs = PatientProfile.objects.select_related("user").filter(user__is_staff=False)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_patient":
            email = (request.POST.get("email") or "").strip().lower()
            first_name = (request.POST.get("first_name") or "").strip()
            last_name = (request.POST.get("last_name") or "").strip()
            password = request.POST.get("password")

            errors = []
            if not email:
                errors.append("El correo electrónico es obligatorio.")
            if User.objects.filter(email=email).exists():
                errors.append("Ya existe un usuario con ese correo electrónico.")
            if not password or len(password) < 6:
                errors.append("La contraseña debe tener al menos 6 caracteres.")

            if errors:
                for error in errors:
                    messages.error(request, error)
            else:
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=password,
                )
                profile, created = PatientProfile.objects.get_or_create(user=user)
                profile.is_approved = True
                profile.approved_at = timezone.now()
                profile.approved_by = request.user
                profile.save(update_fields=["is_approved", "approved_at", "approved_by", "updated_at"])
                messages.success(
                    request,
                    f"Paciente {first_name or last_name or email} creado y aprobado correctamente.",
                )

            return redirect("patients:patients_admin_list")

        profile_id = request.POST.get("profile_id")
        profile = get_object_or_404(patients_qs, id=profile_id)

        if action == "approve":
            profile.is_approved = True
            profile.approved_at = timezone.now()
            profile.approved_by = request.user
            profile.save(update_fields=["is_approved", "approved_at", "approved_by", "updated_at"])
            messages.success(request, "Paciente aprobado correctamente.")
        elif action == "revoke":
            profile.is_approved = False
            profile.approved_at = None
            profile.approved_by = None
            profile.save(update_fields=["is_approved", "approved_at", "approved_by", "updated_at"])
            messages.warning(request, "Aprobación del paciente revocada.")
        elif action == "reject":
            user_email = profile.user.email
            profile.user.delete()
            messages.warning(request, f"Paciente rechazado y eliminado: {user_email}")

        return redirect("patients:patients_admin_list")

    context = {
        "pending_profiles": patients_qs.filter(is_approved=False).order_by("created_at"),
        "approved_profiles": patients_qs.filter(is_approved=True).order_by("user__last_name", "user__first_name"),
    }
    return render(request, "patients/patients_admin_list.html", context)


@user_passes_test(lambda u: u.is_staff)
def patient_admin_detail(request, profile_id):
    profile = get_object_or_404(
        PatientProfile.objects.select_related("user", "approved_by"),
        id=profile_id,
        user__is_staff=False,
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_profile_note":
            profile.phone = (request.POST.get("phone") or "").strip()
            profile.locality = (request.POST.get("locality") or "").strip()
            dob_raw = (request.POST.get("date_of_birth") or "").strip()
            profile.date_of_birth = parse_date(dob_raw) if dob_raw else None
            profile.notes = request.POST.get("profile_note", "")
            profile.save(update_fields=["phone", "locality", "date_of_birth", "notes", "updated_at"])
            messages.success(request, "Historia clínica general actualizada.")
            return redirect("patients:patient_admin_detail", profile_id=profile.id)

        subject = (request.POST.get("subject") or "").strip()
        details = (request.POST.get("details") or "").strip()
        appointment_id = request.POST.get("appointment_id") or ""

        if not subject or not details:
            messages.error(request, "Completá asunto y detalle para guardar la entrada clínica.")
        else:
            appointment = None
            if appointment_id:
                appointment = Appointment.objects.filter(
                    id=appointment_id,
                    patient=profile.user,
                ).first()
            ClinicalTimelineEntry.objects.create(
                patient=profile.user,
                subject=subject,
                details=details,
                appointment=appointment,
                created_by=request.user,
            )
            messages.success(request, "Entrada clínica guardada.")
            return redirect("patients:patient_admin_detail", profile_id=profile.id)

    appointments = Appointment.objects.filter(patient=profile.user).order_by("-date", "-start_time")
    timeline_entries = ClinicalTimelineEntry.objects.filter(patient=profile.user).select_related("created_by", "appointment")

    context = {
        "profile": profile,
        "appointments": appointments,
        "timeline_entries": timeline_entries,
        "patient_age": _calculate_age(profile.date_of_birth),
    }
    return render(request, "patients/patient_admin_detail.html", context)


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
