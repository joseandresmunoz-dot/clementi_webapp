from django.urls import include, path
from rest_framework.routers import DefaultRouter

from files_manager.views import SharedFileViewSet

app_name = "files_manager"

router = DefaultRouter()
router.register("", SharedFileViewSet, basename="files")

urlpatterns = [
    path("", include(router.urls)),
]
