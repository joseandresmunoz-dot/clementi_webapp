from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.http import HttpResponse
import private_storage.urls


def handler403(request, exception=None):
    import traceback
    body = f"403 Forbidden\npath: {request.path}\nmethod: {request.method}\nuser: {request.user}\n"
    if exception:
        body += f"exception: {exception}\n{traceback.format_exc()}"
    return HttpResponse(body, content_type="text/plain", status=403)


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
