"""
Servicios de Mercado Pago: utilidades para cobrar con Checkout Pro usando las
credenciales OAuth del vendedor (ver models.MercadoPagoCredentials).
"""

import logging
from types import SimpleNamespace

from django.conf import settings
from mercadopago import SDK

from patients.models import MercadoPagoCredentials, MercadoPagoError

logger = logging.getLogger(__name__)


def get_active_credentials(user):
    """
    Devuelve las credenciales vigentes para cobrar.

    Prioridad:
    1. Credenciales OAuth del vendedor (``MercadoPagoCredentials``). Si el
       ``access_token`` expiró o está por expirar, las renueva primero.
    2. Fallback: token directo de la aplicación configurado en settings
       (``MP_ACCESS_TOKEN``), útil mientras el vendedor no conecta su cuenta
       vía el flujo OAuth.

    Levanta ``MercadoPagoError`` si no hay ninguna credencial disponible.
    """
    credentials = MercadoPagoCredentials.objects.filter(user=user).first()
    if credentials and credentials.is_connected:
        if credentials.is_token_expired():
            logger.info("Token de Mercado Pago de %s vencido: renovando…", user)
            credentials.refresh_credentials()
        return credentials

    if settings.MP_ACCESS_TOKEN:
        logger.info("Usando access token de MP configurado en settings (usuario %s).", user)
        return SimpleNamespace(access_token=settings.MP_ACCESS_TOKEN)

    raise MercadoPagoError(
        "El vendedor aún no conectó su cuenta de Mercado Pago."
    )


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
