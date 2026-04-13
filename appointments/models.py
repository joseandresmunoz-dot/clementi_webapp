import uuid

from django.conf import settings
from django.db import models


class Appointment(models.Model):
    """
    Cita / turno en el calendario de la Dra.

    Flujo:
    1. La Dra. crea slots con status=AVAILABLE.
    2. Un paciente reserva → status pasa a BOOKED.
    3. Se genera automáticamente un Google Meet link.
    4. Pacientes no autenticados o distintos ven "Reservado" sin detalles.
    """

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Disponible"
        BOOKED = "BOOKED", "Reservado"
        COMPLETED = "COMPLETED", "Completado"
        CANCELLED = "CANCELLED", "Cancelado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
        verbose_name="Paciente",
    )
    date = models.DateField("Fecha")
    start_time = models.TimeField("Hora de inicio")
    end_time = models.TimeField("Hora de fin")
    status = models.CharField(
        "Estado",
        max_length=12,
        choices=Status.choices,
        default=Status.AVAILABLE,
        db_index=True,
    )
    google_event_id = models.CharField(
        "ID evento Google Calendar",
        max_length=255,
        blank=True,
    )
    google_meet_link = models.URLField(
        "Enlace Google Meet",
        blank=True,
    )
    notes = models.TextField("Notas de la cita", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas"
        ordering = ["date", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["date", "start_time"],
                name="unique_slot_per_datetime",
            ),
        ]

    def __str__(self):
        patient_name = "Libre"
        if self.patient:
            patient_name = self.patient.get_full_name() or self.patient.email
        return f"{self.date} {self.start_time}-{self.end_time} | {patient_name}"

    @property
    def is_available(self):
        return self.status == self.Status.AVAILABLE
