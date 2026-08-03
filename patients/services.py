"""
Servicios de Mercado Pago: utilidades para cobrar con Checkout Pro usando las
credenciales OAuth del vendedor (ver models.MercadoPagoCredentials).
"""

import logging

from django.conf import settings
from mercadopago import SDK

from patients.models import MercadoPagoCredentials, MercadoPagoError

logger = logging.getLogger(__name__)


def get_active_credentials(user):
    """
    Devuelve las credenciales OAuth vigentes del vendedor para cobrar.

    Si el ``access_token`` expiró o está por expirar, las renueva primero.
    Levanta ``MercadoPagoError`` si el vendedor aún no conectó su cuenta de
    Mercado Pago (es requisito para cobrar).
    """
    credentials = MercadoPagoCredentials.objects.filter(user=user).first()
    if not credentials or not credentials.is_connected:
        raise MercadoPagoError(
            "El vendedor aún no conectó su cuenta de Mercado Pago. "
            "Conectala desde el panel de administración."
        )

    if credentials.is_token_expired():
        logger.info("Token de Mercado Pago de %s vencido: renovando…", user)
        credentials.refresh_credentials()

    return credentials


def get_connected_seller():
    """
    Devuelve el primer vendedor (staff) que tiene su cuenta de Mercado Pago
    conectada, o ``None`` si nadie la conectó todavía.
    """
    credentials = (
        MercadoPagoCredentials.objects.select_related("user")
        .filter(user__is_staff=True)
        .order_by("user_id")
        .first()
    )
    if credentials and credentials.is_connected:
        return credentials.user
    return None


def create_checkout_preference(user, items, external_reference=None, back_urls=None):
    """
    Crea una preferencia de pago de Checkout Pro con la SDK de Mercado Pago.

    Argumentos:
        user: vendedor (staff) con credenciales OAuth conectadas.
        items: lista de dicts con ``title``, ``quantity`` y ``unit_price``
            (float, en ARS).
        external_reference: referencia externa para identificar la operación
            (por ejemplo, el id de la orden).
        back_urls: dict opcional con ``success``/``pending``/``failure``.
            Por defecto usa ``settings.MP_BACK_URLS``.

    Devuelve el dict de la preferencia creada (incluye ``id`` e
    ``init_point``) o lanza ``MercadoPagoError`` ante cualquier fallo.
    """
    credentials = get_active_credentials(user)
    sdk = SDK(credentials.access_token)

    preference_data = {
        "items": items,
        "back_urls": back_urls or settings.MP_BACK_URLS,
        "auto_return": "approved",
        "external_reference": external_reference or "",
        "notification_url": settings.MP_NOTIFICATION_URL or "",
    }

    try:
        result = sdk.preference().create(preference_data)
    except Exception as exc:
        raise MercadoPagoError(
            f"No se pudo crear la preferencia de pago: {exc}"
        ) from exc

    if not isinstance(result, dict):
        raise MercadoPagoError("La SDK de Mercado Pago devolvió una respuesta inesperada.")

    status = result.get("status")
    response = result.get("response")
    if status not in (200, 201) or not isinstance(response, dict):
        raise MercadoPagoError(
            f"Mercado Pago devolvió HTTP {status}: {result}"
        )

    return response
