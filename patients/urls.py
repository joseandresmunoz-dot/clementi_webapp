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
    path("debug-login/", views.debug_login, name="debug_login"),
    path("", views.home, name="home"),
    path("turnos/", views.calendar_view, name="calendar"),
    path("microbiota/", views.microbiota_quiz, name="microbiota_quiz"),
    path("microbiota/enviar-resultados/", views.submit_quiz_results, name="submit_quiz_results"),
    path("mi-panel/", views.dashboard, name="dashboard"),
    path("mi-panel/pendiente-aprobacion/", views.pending_approval, name="pending_approval"),
    path("administracion/microbiota/", views.microbiota_admin, name="microbiota_admin"),
    path("administracion/", views.admin_panel, name="admin_panel"),
    path("administracion/pacientes/", views.patients_admin_list, name="patients_admin_list"),
    path(
        "administracion/pacientes/<uuid:profile_id>/",
        views.patient_admin_detail,
        name="patient_admin_detail",
    ),
]
