from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from patients.models import PatientProfile


@receiver(pre_save, sender=settings.AUTH_USER_MODEL)
def promote_doctor_to_staff(sender, instance, **kwargs):
    """
    El correo de la Dra. siempre es staff/admin. Se aplica antes de guardar,
    así nunca se le crea un PatientProfile de paciente.
    """
    if instance.email and instance.email.lower() == settings.DOCTOR_EMAIL:
        instance.is_staff = True
        instance.is_active = True


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
