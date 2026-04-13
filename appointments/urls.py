from django.urls import include, path
from rest_framework.routers import DefaultRouter

from appointments.views import AppointmentViewSet

app_name = "appointments"

router = DefaultRouter()
router.register("slots", AppointmentViewSet, basename="appointment")

urlpatterns = [
    path("", include(router.urls)),
]
