import uuid

from django.conf import settings
from django.db import models


class PatientProfile(models.Model):
    """
    Perfil extendido del paciente. Se vincula 1:1 con el User de Django
    (creado automáticamente por django-allauth tras el login con Google).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_profile",
    )
    phone = models.CharField("Teléfono", max_length=20, blank=True)
    date_of_birth = models.DateField("Fecha de nacimiento", null=True, blank=True)
    locality = models.CharField("Localidad", max_length=120, blank=True)
    notes = models.TextField("Notas clínicas (solo visibles para la Dra.)", blank=True)
    is_approved = models.BooleanField("Aprobado por administración", default=False)
    approved_at = models.DateTimeField("Fecha de aprobación", null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_patient_profiles",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Perfil de Paciente"
        verbose_name_plural = "Perfiles de Pacientes"
        ordering = ["user__last_name", "user__first_name"]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email}"


class ClinicalTimelineEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clinical_timeline_entries",
    )
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clinical_timeline_entries",
    )
    subject = models.CharField("Asunto", max_length=200)
    details = models.TextField("Detalle clínico")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_clinical_timeline_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Entrada de historial clínico"
        verbose_name_plural = "Entradas de historial clínico"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.patient.email} — {self.subject}"


class Lead(models.Model):
    """Lead capturado desde el formulario de la landing page (embudo de ventas)."""
    name = models.CharField("Nombre", max_length=200)
    email = models.EmailField("Email")
    phone = models.CharField("Teléfono", max_length=20, blank=True)
    message = models.TextField("Mensaje", blank=True)
    source = models.CharField("Origen", max_length=100, default="landing")
    is_subscribed = models.BooleanField("Suscrito a newsletter", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Leads"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} — {self.email}"
