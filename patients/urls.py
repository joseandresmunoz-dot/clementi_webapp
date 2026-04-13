from django.urls import path

from patients import views

app_name = "patients"

urlpatterns = [
    path("", views.home, name="home"),
    path("turnos/", views.calendar_view, name="calendar"),
    path("microbiota/", views.microbiota_quiz, name="microbiota_quiz"),
    path("mi-panel/", views.dashboard, name="dashboard"),
    path("administracion/", views.admin_panel, name="admin_panel"),
]
