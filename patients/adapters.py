from django.conf import settings
from django.urls import reverse
from allauth.account.adapter import DefaultAccountAdapter


class CustomAccountAdapter(DefaultAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        user = sociallogin.user
        if user.email and user.email.lower() == settings.DOCTOR_EMAIL:
            user.is_staff = True
            user.is_active = True
            user.save()
        return super().pre_social_login(request, sociallogin)

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
