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
        PatientProfile.objects.get_or_create(user=instance)
