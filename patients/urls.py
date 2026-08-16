from django.urls import path

from patients import views

app_name = "patients"

urlpatterns = [
    path("administracion/tienda/", views.shop_admin, name="shop_admin"),
    path("tienda/", views.shop, name="shop"),
    path("tienda/agregar-al-carrito/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("tienda/eliminar-del-carrito/<int:product_id>/", views.remove_from_cart, name="remove_from_cart"),
    path("tienda/carrito/", views.cart, name="cart"),
    path("tienda/pagar-mp/", views.checkout_mp, name="checkout_mp"),
    path("tienda/<slug:slug>/", views.product_detail, name="product_detail"),
    path("test-epigenetico/", views.test_epigenetico, name="test_epigenetico"),
    path("capture-lead/", views.capture_lead, name="capture_lead"),
    path("mp/connect/", views.mp_connect, name="mp_connect"),
    path("mp/callback/", views.mp_callback, name="mp_callback"),
    path("mp/guardar-token/", views.mp_save_token, name="mp_save_token"),
    path("mp/desconectar/", views.mp_disconnect, name="mp_disconnect"),
    path(
        "google-calendar/conectar/",
        views.connect_google_calendar,
        name="connect_google_calendar",
    ),
    path(
        "google-calendar/callback/",
        views.google_calendar_callback,
        name="google_calendar_callback",
    ),
    path(
        "google-calendar/desconectar/",
        views.disconnect_google_calendar,
        name="disconnect_google_calendar",
    ),
    path("debug-login/", views.debug_login, name="debug_login"),
    path("", views.home, name="home"),
    path("turnos/", views.calendar_view, name="calendar"),
    path("microbiota/", views.microbiota_quiz, name="microbiota_quiz"),
    path("microbiota/enviar-resultados/", views.submit_quiz_results, name="submit_quiz_results"),
    path("mi-panel/", views.dashboard, name="dashboard"),
    path("mi-panel/estadisticas/", views.doctor_dashboard, name="doctor_dashboard"),
    path("mi-panel/pendiente-aprobacion/", views.pending_approval, name="pending_approval"),
    path("administracion/microbiota/", views.microbiota_admin, name="microbiota_admin"),
    path("administracion/", views.admin_panel, name="admin_panel"),
    path("administracion/pacientes/", views.patients_admin_list, name="patients_admin_list"),
    path(
        "administracion/pacientes/<uuid:profile_id>/",
        views.patient_admin_detail,
        name="patient_admin_detail",
    ),
    path("consultas/", views.lead_inbox, name="lead_inbox"),
    path("consultas/marcar-todas-leidas/", views.lead_mark_all_read, name="lead_mark_all_read"),
    path("consultas/<int:pk>/", views.lead_detail, name="lead_detail"),
    path("consultas/<int:pk>/responder/", views.lead_reply, name="lead_reply"),
    path("consultas/<int:pk>/estado/", views.lead_update_status, name="lead_update_status"),
    path("consultas/<int:pk>/eliminar/", views.lead_delete, name="lead_delete"),
    path("notificaciones/datos/", views.notifications_data, name="notifications_data"),
    path("notificaciones/marcar-leidas/", views.notifications_mark_read, name="notifications_mark_read"),
    path("notificaciones/toggle/", views.notifications_toggle, name="notifications_toggle"),
]
