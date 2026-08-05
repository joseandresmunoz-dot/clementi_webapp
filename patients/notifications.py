"""
Servicio de notificaciones del sistema (campanita del panel).

Centraliza la creación de notificaciones en la base de datos. Cada usuario
puede activar/desactivar sus notificaciones; cuando están desactivadas, no se
le registran notificaciones nuevas.
"""

import logging

from django.contrib.auth import get_user_model

from patients.models import Notification, NotificationPreference

logger = logging.getLogger(__name__)

User = get_user_model()


def create_notification(user, title, message="", url=""):
    """Crea una notificación para un usuario si las tiene activadas."""
    pref = NotificationPreference.objects.filter(user=user).first()
    if pref is not None and not pref.enabled:
        return None
    return Notification.objects.create(
        user=user, title=title, message=message, url=url
    )


def notify_staff(title, message="", url=""):
    """Crea una notificación para todos los staff activos."""
    for user in User.objects.filter(is_staff=True, is_active=True):
        try:
            create_notification(user, title, message, url)
        except Exception:
            logger.warning("No se pudo notificar a %s", user.email, exc_info=True)


def notify_patient(patient, title, message="", url=""):
    """Crea una notificación para un paciente específico."""
    return create_notification(patient, title, message, url)
