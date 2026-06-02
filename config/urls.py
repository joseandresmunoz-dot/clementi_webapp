from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
import private_storage.urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api/appointments/", include("appointments.urls")),
    path("api/files/", include("files_manager.urls")),
    path("private-media/", include(private_storage.urls)),
    path("", include("patients.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
