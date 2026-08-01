import logging

from django.utils import timezone

from django.db import transaction
from django.db.models import Q
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
        permission_classes=[permissions.IsAuthenticated],
        url_path="book",
    )
    def book(self, request):
        """
        Un paciente autenticado reserva un turno disponible.
        Crea automáticamente un evento en Google Calendar con Meet link.
        """
        serializer = BookAppointmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        appointment_id = serializer.validated_data["appointment_id"]
        notes = serializer.validated_data.get("notes", "")

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
            appointment.patient = request.user
            appointment.status = Appointment.Status.BOOKED
            appointment.notes = notes
            appointment.save(update_fields=["patient", "status", "notes", "updated_at"])

        # Crear evento en Google Calendar (fuera del lock)
        event_id, meet_link = create_calendar_event(appointment)
        if event_id:
            appointment.google_event_id = event_id
            appointment.google_meet_link = meet_link or ""
            appointment.save(update_fields=["google_event_id", "google_meet_link", "updated_at"])

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
    # ENDPOINT para FullCalendar.js (público, sin paginación)
    # ------------------------------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.IsAuthenticated],
        url_path="calendar",
    )
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
                    name = apt.patient.get_full_name() if apt.patient else "?"
                    event["title"] = f"Reservado — {name}"
                    event["color"] = "#dc3545"
                    event["extendedProps"] = {
                        "patient_email": apt.patient.email if apt.patient else "",
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
