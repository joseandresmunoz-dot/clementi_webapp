from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from patients.models import PatientProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_patient_profile(sender, instance, created, **kwargs):
    """
    Crea automáticamente un PatientProfile cuando se registra un usuario nuevo.
    Solo para usuarios NO staff (pacientes).
    """
    if created and not instance.is_staff:
        profile, profile_created = PatientProfile.objects.get_or_create(user=instance)
        if profile_created:
            from patients.notifications import notify_staff

            name = instance.get_full_name() or instance.email
            notify_staff(
                "Nuevo paciente registrado",
                f"{name} se registró en la web.",
                "/administracion/pacientes/",
            )
