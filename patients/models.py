import uuid
from datetime import timedelta

import requests
from django.conf import settings
from django.db import models
from django.utils import timezone


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
    details_html = models.TextField("Detalle clínico HTML", blank=True)
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


class Category(models.Model):
    name = models.CharField("Nombre", max_length=200)
    slug = models.SlugField("Slug", max_length=200, unique=True)
    description = models.TextField("Descripción", blank=True)
    order = models.PositiveIntegerField("Orden", default=0)
    is_active = models.BooleanField("Activa", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="products", verbose_name="Categoría"
    )
    name = models.CharField("Nombre", max_length=300)
    slug = models.SlugField("Slug", max_length=300, unique=True)
    description = models.TextField("Descripción", blank=True)
    details = models.TextField("Detalles", blank=True, help_text="Descripción más detallada del producto")
    price = models.DecimalField("Precio", max_digits=10, decimal_places=2)
    discount_price = models.DecimalField("Precio con descuento", max_digits=10, decimal_places=2, null=True, blank=True)
    promo_label = models.CharField("Etiqueta promoción", max_length=100, blank=True, help_text="Ej: 2x1, 30% OFF, Envío gratis")
    is_on_sale = models.BooleanField("En oferta", default=False)
    image = models.ImageField("Imagen", upload_to="shop/", blank=True)
    is_active = models.BooleanField("Activo", default=True)
    is_curso = models.BooleanField("Es curso", default=False, help_text="Marca si es un curso en lugar de medicación")
    is_featured = models.BooleanField("Destacado", default=False, help_text="Aparece en la sección destacada de la tienda")
    order = models.PositiveIntegerField("Orden", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["category__order", "order", "name"]

    def __str__(self):
        return f"{self.name} — ${self.price}"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images", verbose_name="Producto")
    image = models.ImageField("Imagen", upload_to="shop/")
    is_cover = models.BooleanField("Foto de portada", default=False, help_text="Marcar con estrella para seleccionar como portada")
    order = models.PositiveIntegerField("Orden", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Imagen de producto"
        verbose_name_plural = "Imágenes de producto"
        ordering = ["-is_cover", "order"]

    def __str__(self):
        return f"Imagen de {self.product.name}"


class Order(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="orders", verbose_name="Producto")
    quantity = models.PositiveIntegerField("Cantidad", default=1)
    unit_price = models.DecimalField("Precio unitario", max_digits=10, decimal_places=2)
    total_price = models.DecimalField("Precio total", max_digits=10, decimal_places=2)
    customer_name = models.CharField("Cliente", max_length=300, blank=True)
    customer_email = models.EmailField("Email cliente", blank=True)
    customer_phone = models.CharField("Teléfono", max_length=20, blank=True)
    notes = models.TextField("Notas", blank=True)
    status = models.CharField(
        "Estado", max_length=20,
        choices=[("pending", "Pendiente"), ("completed", "Completado"), ("cancelled", "Cancelado")],
        default="completed",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.name} x{self.quantity} — ${self.total_price}"


class QuizSection(models.Model):
    name = models.CharField("Nombre", max_length=200)
    slug = models.SlugField("Slug", max_length=200, unique=True)
    description = models.TextField("Descripción", blank=True)
    order = models.PositiveIntegerField("Orden", default=0)
    is_active = models.BooleanField("Activa", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sección del cuestionario"
        verbose_name_plural = "Secciones del cuestionario"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Question(models.Model):
    section = models.ForeignKey(
        QuizSection, on_delete=models.CASCADE, related_name="questions", verbose_name="Sección"
    )
    text = models.TextField("Pregunta")
    order = models.PositiveIntegerField("Orden", default=0)
    is_active = models.BooleanField("Activa", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pregunta"
        verbose_name_plural = "Preguntas"
        ordering = ["section__order", "order"]

    def __str__(self):
        return f"{self.section.name} - {self.text[:60]}"


class AnswerOption(models.Model):
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="answer_options", verbose_name="Pregunta"
    )
    text = models.CharField("Texto", max_length=200)
    points = models.IntegerField("Puntos", default=0)
    order = models.PositiveIntegerField("Orden", default=0)

    class Meta:
        verbose_name = "Opción de respuesta"
        verbose_name_plural = "Opciones de respuesta"
        ordering = ["order"]

    def __str__(self):
        return f"{self.text} ({self.points} pts)"


class ScoreRange(models.Model):
    name = models.CharField("Nombre", max_length=100, help_text="Ej: Bajo, Moderado, Alto")
    min_score = models.IntegerField("Puntaje mínimo (Femenino)", default=0)
    max_score = models.IntegerField("Puntaje máximo (Femenino)", default=0)
    min_score_male = models.IntegerField("Puntaje mínimo (Masculino)", default=0)
    max_score_male = models.IntegerField("Puntaje máximo (Masculino)", default=0)
    color = models.CharField("Color", max_length=20, choices=[
        ("green", "Verde"),
        ("yellow", "Amarillo"),
        ("red", "Rojo"),
    ])
    message_female = models.TextField("Mensaje (Femenino)", help_text="Mensaje que se muestra para pacientes femeninas")
    message_male = models.TextField("Mensaje (Masculino)", help_text="Mensaje que se muestra para pacientes masculinos")
    order = models.PositiveIntegerField("Orden", default=0)

    class Meta:
        verbose_name = "Rango de puntuación"
        verbose_name_plural = "Rangos de puntuación"
        ordering = ["min_score"]

    def __str__(self):
        return f"{self.name} (F:{self.min_score}-{self.max_score} / M:{self.min_score_male}-{self.max_score_male})"


class Lead(models.Model):
    """Lead capturado desde el formulario de la landing page (embudo de ventas)."""

    class Status(models.TextChoices):
        NEW = "NEW", "Nuevo"
        READ = "READ", "Leído"
        REPLIED = "REPLIED", "Respondido"
        ARCHIVED = "ARCHIVED", "Archivado"

    name = models.CharField("Nombre", max_length=200)
    email = models.EmailField("Email")
    phone = models.CharField("Teléfono", max_length=20, blank=True)
    message = models.TextField("Mensaje", blank=True)
    message_html = models.TextField("Mensaje HTML", blank=True)
    source = models.CharField("Origen", max_length=100, default="landing")
    is_subscribed = models.BooleanField("Suscrito a newsletter", default=True)
    status = models.CharField(
        "Estado", max_length=10, choices=Status.choices, default=Status.NEW, db_index=True
    )
    is_read = models.BooleanField("Leído", default=False, db_index=True)
    reply_count = models.PositiveIntegerField("Cantidad de respuestas", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Leads"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} — {self.email}"


class LeadReply(models.Model):
    """Respuesta del staff a una consulta (Lead)."""

    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name="replies", verbose_name="Consulta"
    )
    message = models.TextField("Respuesta")
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Respondido por",
    )
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Respuesta a consulta"
        verbose_name_plural = "Respuestas a consultas"
        ordering = ["sent_at"]

    def __str__(self):
        return f"Respuesta de {self.sent_by} a {self.lead.name}"


class Notification(models.Model):
    """Notificación del sistema (campanita del panel)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Usuario",
    )
    title = models.CharField("Título", max_length=200)
    message = models.TextField("Mensaje", blank=True)
    url = models.CharField("URL", max_length=500, blank=True)
    is_read = models.BooleanField("Leído", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} — {self.title}"


class NotificationPreference(models.Model):
    """Preferencia de activar/desactivar notificaciones por usuario."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_pref",
        verbose_name="Usuario",
    )
    enabled = models.BooleanField("Notificaciones activadas", default=True)

    class Meta:
        verbose_name = "Preferencia de notificación"
        verbose_name_plural = "Preferencias de notificación"

    def __str__(self):
        return f"{self.user.email} — {'activadas' if self.enabled else 'desactivadas'}"


class MercadoPagoError(Exception):
    """Error de la integración con Mercado Pago (OAuth / Checkout Pro)."""


class MercadoPagoCredentials(models.Model):
    """
    Credenciales OAuth 2.0 del vendedor (staff), obtenidas tras el flujo de
    autorización (`mp_connect` → `mp_callback`). Se usan para cobrar con
    Checkout Pro con el token de la cuenta real del vendedor.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mp_credentials",
        verbose_name="Vendedor",
    )
    access_token = models.CharField("Access token", max_length=512, blank=True)
    refresh_token = models.CharField("Refresh token", max_length=512, blank=True)
    public_key = models.CharField("Public key", max_length=256, blank=True)
    mp_user_id = models.BigIntegerField("ID de usuario (MP)", null=True, blank=True)
    token_type = models.CharField("Tipo de token", max_length=64, blank=True)
    expires_in = models.PositiveIntegerField(
        "Duración del token (segundos)", null=True, blank=True
    )
    token_expires_at = models.DateTimeField("El token expira en", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Credencial de Mercado Pago"
        verbose_name_plural = "Credenciales de Mercado Pago"

    def __str__(self):
        return f"Credenciales MP de {self.user}"

    @property
    def is_connected(self):
        """True si hay un token de acceso disponible (OAuth o pegado a mano)."""
        return bool(self.access_token)

    def update_from_token(self, payload):
        """Persiste el payload devuelto por ``/oauth/token``."""
        mapping = {
            "access_token": "access_token",
            "refresh_token": "refresh_token",
            "public_key": "public_key",
            "user_id": "mp_user_id",
            "token_type": "token_type",
        }
        update_fields = ["updated_at"]
        for key, field in mapping.items():
            if key in payload and payload[key] is not None:
                setattr(self, field, payload[key])
                update_fields.append(field)

        expires_in = payload.get("expires_in")
        if expires_in:
            self.expires_in = int(expires_in)
            self.token_expires_at = timezone.now() + timedelta(seconds=int(expires_in))
            update_fields += ["expires_in", "token_expires_at"]
        else:
            self.token_expires_at = None
            update_fields.append("token_expires_at")

        self.save(update_fields=update_fields)
        return self

    def is_token_expired(self, buffer_seconds=300):
        """
        Devuelve ``True`` si el token ya expiró o va a expirar dentro de
        ``buffer_seconds`` (margen de seguridad). Un token pegado a mano
        (sin ``token_expires_at``) se considera siempre vigente.
        """
        if not self.access_token:
            return True
        if not self.token_expires_at:
            return False
        return timezone.now() >= self.token_expires_at - timedelta(
            seconds=buffer_seconds
        )

    def refresh_credentials(self):
        """
        Renueva el ``access_token`` con ``grant_type=refresh_token`` y
        actualiza la base automáticamente. Levanta ``MercadoPagoError`` si la
        renovación falla (p. ej. refresh_token vencido o no autorizado).
        """
        if not self.refresh_token:
            raise MercadoPagoError(
                "No hay refresh_token para renovar las credenciales."
            )

        data = {
            "grant_type": "refresh_token",
            "client_id": settings.MP_CLIENT_ID,
            "client_secret": settings.MP_CLIENT_SECRET,
            "refresh_token": self.refresh_token,
        }

        try:
            response = requests.post(settings.MP_TOKEN_URL, data=data, timeout=30)
        except requests.RequestException as exc:
            raise MercadoPagoError(
                f"No se pudo contactar a Mercado Pago: {exc}"
            ) from exc

        if response.status_code != 200:
            raise MercadoPagoError(
                f"Error al renovar el token (HTTP {response.status_code}): "
                f"{response.text[:300]}"
            )

        return self.update_from_token(response.json())


class GoogleCalendarCredentials(models.Model):
    """
    Credenciales OAuth 2.0 de la Dra. para Google Calendar.

    Se obtienen con el botón "Conectar Google Calendar" (flujo de
    autorización separado del login de Google), así el login de pacientes
    no pide scopes sensibles y no aparece el aviso de "app no verificada".
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="google_calendar_credentials",
        verbose_name="Dra.",
    )
    access_token = models.TextField("Access token")
    refresh_token = models.TextField("Refresh token")
    token_type = models.CharField("Tipo de token", max_length=64, default="Bearer")
    expires_at = models.DateTimeField("El token expira en")
    google_email = models.EmailField("Email de Google", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Credencial de Google Calendar"
        verbose_name_plural = "Credenciales de Google Calendar"

    def __str__(self):
        return f"Google Calendar de {self.user}"

    @property
    def is_connected(self):
        """True si hay token de acceso y refresh token disponibles."""
        return bool(self.access_token and self.refresh_token)

    def is_token_expired(self, buffer_seconds=300):
        """True si el token no existe, expiró, o expira dentro del margen."""
        if not self.access_token or not self.expires_at:
            return True
        return timezone.now() >= self.expires_at - timedelta(seconds=buffer_seconds)
