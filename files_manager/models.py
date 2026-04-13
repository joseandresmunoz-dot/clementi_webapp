import uuid

from django.conf import settings
from django.db import models
from private_storage.fields import PrivateFileField


def shared_file_upload_path(instance, filename):
    """Genera ruta segura: private_files/<visibility>/<uuid>/<filename>"""
    return f"private_files/{instance.visibility}/{instance.id}/{filename}"


class SharedFile(models.Model):
    """
    Archivo subido por la Dra. con tres niveles de visibilidad:
    - PUBLIC:     Cualquier visitante puede acceder.
    - REGISTERED: Solo pacientes autenticados.
    - PRIVATE:    Solo pacientes específicos asignados via FilePermission.
    """

    class Visibility(models.TextChoices):
        PUBLIC = "PUBLIC", "Público"
        REGISTERED = "REGISTERED", "Pacientes registrados"
        PRIVATE = "PRIVATE", "Paciente específico"

    class FileType(models.TextChoices):
        PDF = "PDF", "Documento PDF"
        VIDEO = "VIDEO", "Video"
        IMAGE = "IMAGE", "Imagen"
        OTHER = "OTHER", "Otro"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField("Título", max_length=255)
    description = models.TextField("Descripción", blank=True)
    file = PrivateFileField(
        "Archivo",
        upload_to=shared_file_upload_path,
    )
    file_type = models.CharField(
        "Tipo de archivo",
        max_length=10,
        choices=FileType.choices,
        default=FileType.PDF,
    )
    visibility = models.CharField(
        "Visibilidad",
        max_length=12,
        choices=Visibility.choices,
        default=Visibility.REGISTERED,
        db_index=True,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_files",
        verbose_name="Subido por",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Archivo compartido"
        verbose_name_plural = "Archivos compartidos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.get_visibility_display()})"


class FilePermission(models.Model):
    """
    Relación M:N entre SharedFile (PRIVATE) y pacientes autorizados.
    Solo se usa cuando visibility == PRIVATE.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shared_file = models.ForeignKey(
        SharedFile,
        on_delete=models.CASCADE,
        related_name="permissions",
        verbose_name="Archivo",
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="file_permissions",
        verbose_name="Paciente",
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Permiso de archivo"
        verbose_name_plural = "Permisos de archivo"
        constraints = [
            models.UniqueConstraint(
                fields=["shared_file", "patient"],
                name="unique_file_patient_permission",
            ),
        ]

    def __str__(self):
        return f"{self.patient} → {self.shared_file.title}"
