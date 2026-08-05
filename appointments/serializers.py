from django.utils import timezone
from rest_framework import serializers

from appointments.models import Appointment


class AppointmentPublicSerializer(serializers.ModelSerializer):
    """
    Serializer para pacientes y visitantes.
    - Slots AVAILABLE: muestra fecha/hora para reservar.
    - Slots BOOKED: muestra "Reservado" SIN revelar quién lo tomó.
    - Slots del propio paciente: muestra su Meet link.
    """

    is_own = serializers.SerializerMethodField()
    display_status = serializers.SerializerMethodField()
    meet_link = serializers.SerializerMethodField()
    past = serializers.SerializerMethodField()
    extendedProps = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id",
            "date",
            "start_time",
            "end_time",
            "status",
            "display_status",
            "is_own",
            "meet_link",
            "past",
            "extendedProps",
        ]
        read_only_fields = fields
    def get_past(self, obj):
        now = timezone.localtime()
        if obj.date < now.date():
            return True
        if obj.date > now.date():
            return False
        end_time = obj.end_time or obj.start_time
        if not end_time:
            return False
        return end_time <= now.time()

    def get_extendedProps(self, obj):
        # Devuelve todos los props extra que FullCalendar necesita
        return {
            'bookable': obj.status == obj.Status.AVAILABLE,
            'meet_link': self.get_meet_link(obj),
            'is_own': self.get_is_own(obj),
            'past': self.get_past(obj),
        }

    def get_is_own(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated and obj.patient_id:
            return obj.patient_id == request.user.id
        return False

    def get_display_status(self, obj):
        if obj.status == Appointment.Status.AVAILABLE:
            return "Disponible"
        if obj.status == Appointment.Status.BOOKED:
            return "Reservado"
        if obj.status == Appointment.Status.COMPLETED:
            return "Completado"
        return "Cancelado"

    def get_meet_link(self, obj):
        """Solo muestra el link de Meet al paciente que reservó."""
        request = self.context.get("request")
        if (
            request
            and request.user.is_authenticated
            and obj.patient_id == request.user.id
            and obj.status == Appointment.Status.BOOKED
        ):
            return obj.google_meet_link
        return ""


class AppointmentAdminSerializer(serializers.ModelSerializer):
    """
    Serializer completo para la Dra. (staff).
    Ve todos los detalles: paciente, meet link, notas.
    """

    patient_name = serializers.SerializerMethodField()
    patient_email = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id",
            "date",
            "start_time",
            "end_time",
            "status",
            "patient",
            "patient_name",
            "patient_email",
            "guest_name",
            "guest_email",
            "guest_age",
            "google_event_id",
            "google_meet_link",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "google_event_id",
            "google_meet_link",
            "created_at",
            "updated_at",
        ]

    def get_patient_name(self, obj):
        if obj.patient:
            return obj.patient.get_full_name() or obj.patient.email
        return obj.guest_name or ""

    def get_patient_email(self, obj):
        if obj.patient:
            return obj.patient.email
        return obj.guest_email or ""


class BookAppointmentSerializer(serializers.Serializer):
    """Serializer para reservar un turno disponible (paciente autenticado o invitado)."""

    appointment_id = serializers.UUIDField()
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    email = serializers.EmailField(required=False, allow_blank=True)
    age = serializers.IntegerField(required=False, min_value=1, max_value=130)
