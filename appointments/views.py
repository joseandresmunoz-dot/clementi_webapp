import logging

from django.utils import timezone

from django.db import transaction
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from appointments.models import Appointment
from appointments.serializers import (
    AppointmentAdminSerializer,
    AppointmentPublicSerializer,
    BookAppointmentSerializer,
)
from appointments.services.google_calendar import (
    create_calendar_event,
    delete_calendar_event,
)

logger = logging.getLogger(__name__)


class IsStaffOrReadOnly(permissions.BasePermission):
    """Staff puede hacer CRUD completo; autenticados solo lectura + reservar."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.is_staff


class AppointmentViewSet(viewsets.ModelViewSet):
    """
    API del calendario de turnos.

    Endpoints:
    - GET  /api/appointments/slots/            → Lista slots (filtrable por mes)
    - GET  /api/appointments/slots/{id}/       → Detalle de un slot
    - POST /api/appointments/slots/            → Crear slot (solo Dra.)
    - POST /api/appointments/slots/book/       → Reservar turno (paciente auth)
    - POST /api/appointments/slots/{id}/cancel/ → Cancelar turno
    - PUT  /api/appointments/slots/{id}/       → Editar slot (solo Dra.)
    - DEL  /api/appointments/slots/{id}/       → Eliminar slot (solo Dra.)
    """

    permission_classes = [IsStaffOrReadOnly]
    lookup_field = "id"

    def get_queryset(self):
        qs = Appointment.objects.select_related("patient").all()

        # Filtros por query params (para FullCalendar.js)
        start = self.request.query_params.get("start")
        end = self.request.query_params.get("end")
        if start:
            qs = qs.filter(date__gte=start[:10])
        if end:
            qs = qs.filter(date__lte=end[:10])

        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs

    def get_serializer_class(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return AppointmentAdminSerializer
        return AppointmentPublicSerializer

    # ------------------------------------------------------------------
    # PACIENTE: Reservar turno
    # ------------------------------------------------------------------
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.AllowAny],
        url_path="book",
    )
    def book(self, request):
        """
        Reserva un turno disponible.
        - Autenticado: lo asocia a su cuenta.
        - Invitado (sin cuenta): requiere nombre, apellido, edad y email.
        Crea automáticamente un evento en Google Calendar con Meet link.
        """
        serializer = BookAppointmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        appointment_id = serializer.validated_data["appointment_id"]
        notes = serializer.validated_data.get("notes", "")

        guest = request.user.is_anonymous
        if guest:
            first_name = serializer.validated_data.get("first_name", "").strip()
            last_name = serializer.validated_data.get("last_name", "").strip()
            email = serializer.validated_data.get("email", "").strip()
            age = serializer.validated_data.get("age")
            if not first_name or not last_name or not email:
                return Response(
                    {"error": "Completá tu nombre, apellido y correo para reservar."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            guest_name = f"{first_name} {last_name}".strip()
        else:
            guest_name = ""
            email = ""
            age = None

        with transaction.atomic():
            try:
                appointment = (
                    Appointment.objects.select_for_update()
                    .get(id=appointment_id)
                )
            except Appointment.DoesNotExist:
                return Response(
                    {"error": "Turno no encontrado."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if appointment.status != Appointment.Status.AVAILABLE:
                return Response(
                    {"error": "Este turno ya no está disponible."},
                    status=status.HTTP_409_CONFLICT,
                )

            now = timezone.localtime()
            if appointment.date < now.date() or (
                appointment.date == now.date() and appointment.start_time <= now.time()
            ):
                return Response(
                    {"error": "No se puede reservar un turno en el pasado."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Reservar
            appointment.status = Appointment.Status.BOOKED
            appointment.notes = notes
            if guest:
                appointment.patient = None
                appointment.guest_name = guest_name
                appointment.guest_email = email
                appointment.guest_age = age
            else:
                appointment.patient = request.user
                appointment.guest_name = ""
                appointment.guest_email = ""
                appointment.guest_age = None
            appointment.save(update_fields=[
                "patient", "status", "notes", "guest_name",
                "guest_email", "guest_age", "updated_at",
            ])

        # Crear evento en Google Calendar (fuera del lock)
        event_id, meet_link = create_calendar_event(appointment)
        if event_id:
            appointment.google_event_id = event_id
            appointment.google_meet_link = meet_link or ""
            appointment.save(update_fields=["google_event_id", "google_meet_link", "updated_at"])

        from patients.notifications import notify_patient, notify_staff

        if appointment.patient:
            patient_name = (
                appointment.patient.get_full_name() or appointment.patient.email
            )
            notify_patient(
                appointment.patient,
                "Turno confirmado",
                f"Tu turno quedó reservado para el {appointment.date.strftime('%d/%m/%Y')} "
                f"a las {appointment.start_time.strftime('%H:%M')}.",
                "/mi-panel/",
            )
        else:
            patient_name = appointment.guest_name or appointment.guest_email
        notify_staff(
            "Nuevo turno reservado",
            f"{patient_name} reservó el {appointment.date.strftime('%d/%m/%Y')} "
            f"a las {appointment.start_time.strftime('%H:%M')}.",
            "/turnos/",
        )

        # Responder con el serializer adecuado
        out_serializer = AppointmentPublicSerializer(
            appointment, context={"request": request}
        )
        return Response(out_serializer.data, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # CANCELAR turno (paciente propio o Dra.)
    # ------------------------------------------------------------------
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="cancel",
    )
    def cancel(self, request, id=None):
        """
        Cancela un turno. El paciente solo puede cancelar el suyo.
        La Dra. (staff) puede cancelar cualquiera.
        """
        try:
            appointment = Appointment.objects.get(id=id)
        except Appointment.DoesNotExist:
            return Response(
                {"error": "Turno no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if appointment.status != Appointment.Status.BOOKED:
            return Response(
                {"error": "Solo se pueden cancelar turnos reservados."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verificar permisos
        is_own = appointment.patient_id == request.user.id
        is_staff = request.user.is_staff
        if not (is_own or is_staff):
            return Response(
                {"error": "No tenés permiso para cancelar este turno."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Eliminar evento de Google Calendar
        if appointment.google_event_id:
            delete_calendar_event(appointment.google_event_id)

        # Liberar el slot
        appointment.status = Appointment.Status.CANCELLED
        appointment.save(update_fields=["status", "updated_at"])

        return Response({"message": "Turno cancelado correctamente."})

    # ------------------------------------------------------------------
    # DRA: Crear slots disponibles en lote
    # ------------------------------------------------------------------
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAdminUser],
        url_path="bulk-create",
    )
    def bulk_create(self, request):
        """
        La Dra. crea múltiples slots a la vez.
        Body: { "slots": [{"date": "2026-04-10", "start_time": "09:00", "end_time": "09:30"}, ...] }
        """
        slots_data = request.data.get("slots", [])
        if not slots_data:
            return Response(
                {"error": "Enviá una lista de slots en el campo 'slots'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = []
        errors = []
        for i, slot in enumerate(slots_data):
            serializer = AppointmentAdminSerializer(data=slot)
            if serializer.is_valid():
                appointment = serializer.save(status=Appointment.Status.AVAILABLE)
                created.append(AppointmentAdminSerializer(appointment).data)
            else:
                errors.append({"index": i, "errors": serializer.errors})

        return Response(
            {
                "created_count": len(created),
                "created": created,
                "errors": errors,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST,
        )

    # ------------------------------------------------------------------
    # DRA: Eliminar slots disponibles de un día completo
    # ------------------------------------------------------------------
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAdminUser],
        url_path="bulk-delete",
    )
    def bulk_delete(self, request):
        """
        Elimina TODOS los slots AVAILABLE de una fecha (no toca reservados).
        Body: { "date": "2026-04-10" }
        """
        date_str = request.data.get("date", "").strip()
        if not date_str:
            return Response(
                {"error": "Enviá la fecha en el campo 'date'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted, _ = Appointment.objects.filter(
            date=date_str,
            status=Appointment.Status.AVAILABLE,
        ).delete()

        return Response(
            {"deleted_count": deleted},
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # ENDPOINT para FullCalendar.js (público, sin paginación)
    # ------------------------------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.AllowAny],
        url_path="calendar",
    )
    @method_decorator(never_cache)
    def calendar_events(self, request):
        """
        Devuelve slots en formato compatible con FullCalendar.js.
        Query params: ?start=2026-04-01&end=2026-04-30
        No muestra datos del paciente a usuarios no autorizados.
        """
        qs = self.get_queryset().exclude(status=Appointment.Status.CANCELLED)
        now = timezone.localtime()
        qs = qs.filter(
            Q(date__gt=now.date()) | Q(date=now.date(), end_time__gt=now.time())
        )

        events = []
        for apt in qs:
            event = {
                "id": str(apt.id),
                "start": f"{apt.date}T{apt.start_time}",
                "end": f"{apt.date}T{apt.end_time}",
                "allDay": False,
            }

            if apt.status == Appointment.Status.AVAILABLE:
                event["title"] = "Disponible"
                event["color"] = "#28a745"
                event["extendedProps"] = {"bookable": True}
            elif apt.status == Appointment.Status.BOOKED:
                is_own = (
                    request.user.is_authenticated
                    and apt.patient_id == request.user.id
                )
                if request.user.is_authenticated and request.user.is_staff:
                    if apt.patient:
                        name = apt.patient.get_full_name() or apt.patient.email
                    elif apt.guest_name:
                        name = f"{apt.guest_name} (invitado)"
                    else:
                        name = "?"
                    profile = apt.patient.patient_profile if apt.patient else None
                    event["title"] = f"Reservado — {name}"
                    event["color"] = "#dc3545"
                    event["extendedProps"] = {
                        "patient_name": name,
                        "patient_email": apt.patient.email if apt.patient else (apt.guest_email or ""),
                        "patient_phone": (profile.phone if profile else "") or "",
                        "patient_locality": (profile.locality if profile else "") or "",
                        "patient_age": (
                            apt.guest_age
                            if apt.guest_age
                            else (
                                None
                                if not (profile and profile.date_of_birth)
                                else (timezone.localdate() - profile.date_of_birth).days // 365
                            )
                        ),
                        "patient_notes": apt.notes,
                        "is_guest": apt.patient is None,
                        "meet_link": apt.google_meet_link,
                    }
                elif is_own:
                    event["title"] = "Tu turno"
                    event["color"] = "#007bff"
                    event["extendedProps"] = {
                        "meet_link": apt.google_meet_link,
                    }
                else:
                    event["title"] = "Reservado"
                    event["color"] = "#6c757d"
                    event["extendedProps"] = {"bookable": False}
            elif apt.status == Appointment.Status.COMPLETED:
                event["title"] = "Completado"
                event["color"] = "#6c757d"

            events.append(event)

        return Response(events)
