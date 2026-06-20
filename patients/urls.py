from django.urls import path

from patients import views

app_name = "patients"

urlpatterns = [
    path("test-epigenetico/", views.test_epigenetico, name="test_epigenetico"),
    path("capture-lead/", views.capture_lead, name="capture_lead"),
    path("debug-login/", views.debug_login, name="debug_login"),
    path("", views.home, name="home"),
    path("turnos/", views.calendar_view, name="calendar"),
    path("microbiota/", views.microbiota_quiz, name="microbiota_quiz"),
    path("mi-panel/", views.dashboard, name="dashboard"),
    path("mi-panel/pendiente-aprobacion/", views.pending_approval, name="pending_approval"),
    path("administracion/", views.admin_panel, name="admin_panel"),
    path("administracion/pacientes/", views.patients_admin_list, name="patients_admin_list"),
    path(
        "administracion/pacientes/<uuid:profile_id>/",
        views.patient_admin_detail,
        name="patient_admin_detail",
    ),
]
