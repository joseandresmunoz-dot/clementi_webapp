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
            "extendedProps",
        ]
        read_only_fields = fields
    def get_past(self, obj):
        from datetime import date, datetime
        today = date.today()
        if obj.date < today:
            return True
        if obj.date == today and obj.end_time:
            now = datetime.now().time()
            return obj.end_time < now
        return False

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
    patient_email = serializers.CharField(source="patient.email", read_only=True, default="")

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
        return ""


class BookAppointmentSerializer(serializers.Serializer):
    """Serializer para que un paciente reserve un turno disponible."""

    appointment_id = serializers.UUIDField()
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)
