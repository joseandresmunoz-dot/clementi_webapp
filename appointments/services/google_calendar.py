"""
Servicio de integración con Google Calendar API.

Flujo:
1. La Dra. conecta Google Calendar una vez con el botón del panel
   (``patients:connect_google_calendar``), que guarda sus credenciales
   OAuth2 en ``GoogleCalendarCredentials``.
2. Cuando un paciente reserva un turno, usamos esas credenciales para
   crear un evento en su Google Calendar con enlace de Meet.
3. Si se cancela, se elimina el evento del calendario.

Requerimiento: la Dra. (staff) debe tener credenciales de Google Calendar
conectadas desde el panel. El login normal de pacientes no pide scope de
calendar (así no aparece el aviso de "app no verificada").
"""

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from patients.models import GoogleCalendarCredentials

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_doctor_credentials():
    """
    Obtiene las credenciales OAuth2 de la Dra. (primer staff con Google
    Calendar conectado). Refresca el token si está vencido.
    """
    creds = (
        GoogleCalendarCredentials.objects.select_related("user")
        .filter(user__is_staff=True)
        .order_by("user_id")
        .first()
    )
    if not creds or not creds.is_connected:
        logger.error(
            "La Dra. aún no conectó Google Calendar (botón en el panel)."
        )
        return None

    # Obtener client_id y secret desde la config de allauth
    google_config = settings.SOCIALACCOUNT_PROVIDERS.get("google", {})
    app_config = google_config.get("APP", {})
    client_id = app_config.get("client_id", "")
    client_secret = app_config.get("secret", "")

    credentials = Credentials(
        token=creds.access_token,
        refresh_token=creds.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )

    # Refrescar si está vencido
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            # Actualizar token en DB
            creds.access_token = credentials.token
            creds.expires_at = timezone.now() + timedelta(seconds=3600)
            creds.save(update_fields=["access_token", "expires_at", "updated_at"])
            logger.info("Token de Google Calendar refrescado exitosamente.")
        except Exception:
            logger.exception("Error al refrescar el token de Google Calendar.")
            return None

    return credentials


def _get_calendar_service():
    """Construye el servicio de Google Calendar API v3."""
    credentials = _get_doctor_credentials()
    if not credentials:
        return None
    return build("calendar", "v3", credentials=credentials)


def create_calendar_event(appointment):
    """
    Crea un evento en Google Calendar con Google Meet automático.

    Args:
        appointment: instancia de Appointment (ya con patient asignado).

    Returns:
        tuple: (google_event_id, google_meet_link) o (None, None) si falla.
    """
    service = _get_calendar_service()
    if not service:
        logger.warning("No se pudo crear el servicio de Calendar. Evento no creado.")
        return None, None

    tz = settings.TIME_ZONE
    start_dt = datetime.combine(appointment.date, appointment.start_time)
    end_dt = datetime.combine(appointment.date, appointment.end_time)

    patient_name = ""
    patient_email = ""
    if appointment.patient:
        patient_name = appointment.patient.get_full_name() or appointment.patient.email
        patient_email = appointment.patient.email

    event_body = {
        "summary": f"Consulta — {patient_name}",
        "description": (
            f"Turno reservado por {patient_name}.\n"
            f"Notas: {appointment.notes or 'Sin notas.'}"
        ),
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": tz,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": tz,
        },
        "attendees": [],
        "conferenceData": {
            "createRequest": {
                "requestId": str(appointment.id),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            },
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 60},
                {"method": "popup", "minutes": 30},
            ],
        },
    }

    # Agregar al paciente como asistente si tiene email
    if patient_email:
        event_body["attendees"].append({"email": patient_email})

    try:
        event = (
            service.events()
            .insert(
                calendarId="primary",
                body=event_body,
                conferenceDataVersion=1,
                sendUpdates="all",
            )
            .execute()
        )

        event_id = event.get("id", "")
        meet_link = ""
        conference_data = event.get("conferenceData")
        if conference_data:
            entry_points = conference_data.get("entryPoints", [])
            for ep in entry_points:
                if ep.get("entryPointType") == "video":
                    meet_link = ep.get("uri", "")
                    break

        logger.info(
            "Evento creado en Google Calendar: %s (Meet: %s)",
            event_id,
            meet_link,
        )
        return event_id, meet_link

    except HttpError:
        logger.exception("Error HTTP al crear evento en Google Calendar.")
        return None, None
    except Exception:
        logger.exception("Error inesperado al crear evento en Google Calendar.")
        return None, None


def delete_calendar_event(google_event_id):
    """
    Elimina un evento de Google Calendar.

    Args:
        google_event_id: ID del evento a eliminar.

    Returns:
        bool: True si se eliminó correctamente.
    """
    if not google_event_id:
        return False

    service = _get_calendar_service()
    if not service:
        return False

    try:
        service.events().delete(
            calendarId="primary",
            eventId=google_event_id,
            sendUpdates="all",
        ).execute()
        logger.info("Evento %s eliminado de Google Calendar.", google_event_id)
        return True
    except HttpError as e:
        if e.resp.status == 404:
            logger.warning("Evento %s no encontrado en Calendar (ya eliminado?).", google_event_id)
            return True
        logger.exception("Error al eliminar evento %s de Calendar.", google_event_id)
        return False


def update_calendar_event(appointment):
    """
    Actualiza un evento existente en Google Calendar.

    Args:
        appointment: instancia de Appointment con google_event_id.

    Returns:
        bool: True si se actualizó correctamente.
    """
    if not appointment.google_event_id:
        return False

    service = _get_calendar_service()
    if not service:
        return False

    tz = settings.TIME_ZONE
    start_dt = datetime.combine(appointment.date, appointment.start_time)
    end_dt = datetime.combine(appointment.date, appointment.end_time)

    patient_name = ""
    if appointment.patient:
        patient_name = appointment.patient.get_full_name() or appointment.patient.email

    event_body = {
        "summary": f"Consulta — {patient_name}" if patient_name else "Turno disponible",
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": tz,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": tz,
        },
    }

    try:
        service.events().patch(
            calendarId="primary",
            eventId=appointment.google_event_id,
            body=event_body,
            sendUpdates="all",
        ).execute()
        logger.info("Evento %s actualizado en Google Calendar.", appointment.google_event_id)
        return True
    except HttpError:
        logger.exception("Error al actualizar evento en Calendar.")
        return False
