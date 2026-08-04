from django.conf import settings
from django.urls import reverse
from allauth.account.adapter import DefaultAccountAdapter


class CustomAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        user = request.user
        if (
            user.is_authenticated
            and user.is_staff
            and user.email
            and user.email.lower() == settings.DOCTOR_EMAIL
        ):
            return reverse("patients:doctor_dashboard")
        return super().get_login_redirect_url(request)
