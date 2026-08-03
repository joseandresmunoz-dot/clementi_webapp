"""
Fija la vinculación de Google (Calendar) de la cuenta de la Dra.

Uso:
    python manage.py fix_doctor_google

- Asocia el email romina.c.clementi@gmail.com a la cuenta staff (dra.clementi).
- Mueve la SocialAccount de Google recién creada (si existe) a esa cuenta staff.
- Elimina conexiones Google viejas (client bloqueado) en la cuenta staff.
- Elimina el usuario duplicado recién creado por el signup social, si solo existe
  para la conexión Google.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from allauth.socialaccount.models import SocialAccount, SocialToken

DOCTOR_EMAIL = "romina.c.clementi@gmail.com"
DOCTOR_USERNAME = "dra.clementi"


class Command(BaseCommand):
    help = "Re-vincula la cuenta de Google de la Dra. a su usuario staff."

    def handle(self, *args, **options):
        User = get_user_model()

        staff = User.objects.filter(username=DOCTOR_USERNAME).first()
        if not staff:
            staff = User.objects.filter(is_staff=True).order_by("id").first()
        if not staff:
            self.stderr.write("No se encontró un usuario staff. Abortando.")
            return

        changed = []

        # 1) email de la cuenta staff
        if staff.email != DOCTOR_EMAIL:
            staff.email = DOCTOR_EMAIL
            staff.save(update_fields=["email"])
            changed.append(f"email de staff actualizado a {DOCTOR_EMAIL}")

        # 2) mover la SocialAccount de Google del usuario nuevo al staff
        new_account = SocialAccount.objects.filter(
            provider="google",
            user__email__iexact=DOCTOR_EMAIL,
        ).exclude(user=staff).first()
        if new_account:
            old_user = new_account.user
            new_account.user = staff
            new_account.save(update_fields=["user"])
            changed.append(f"SocialAccount {new_account.uid} movida a {staff.username}")
            # si el usuario que quedó huérfano es solo el del signup social, borrarlo
            if not SocialAccount.objects.filter(user=old_user).exists():
                old_user.delete()
                changed.append(f"usuario duplicado {old_user.username} eliminado")

        # 3) eliminar conexiones Google viejas (client bloqueado) del staff
        stale = SocialAccount.objects.filter(provider="google", user=staff).exclude(
            user__email__iexact=DOCTOR_EMAIL
        )
        for acc in stale:
            SocialToken.objects.filter(account=acc).delete()
            acc.delete()
            changed.append(f"conexión Google vieja {acc.uid} eliminada")

        if not changed:
            self.stdout.write("Todo ya estaba correcto, no se modificó nada.")
            return

        for msg in changed:
            self.stdout.write(msg)

        accounts = SocialAccount.objects.filter(provider="google", user=staff)
        self.stdout.write(
            f"Cuenta Google activa de la Dra.: "
            f"{list(accounts.values_list('uid', flat=True))}"
        )
