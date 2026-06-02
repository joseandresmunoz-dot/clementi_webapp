def check_file_access(private_file):
    """
    Función de autorización para django-private-storage.
    Recibe un PrivateFile con .request y .relative_name.
    """
    from files_manager.models import FilePermission, SharedFile
    from patients.models import PatientProfile

    request = private_file.request
    user = request.user

    # Staff siempre tiene acceso
    if user.is_authenticated and user.is_staff:
        return True

    if user.is_authenticated:
        profile = PatientProfile.objects.filter(user=user).first()
        if not profile or not profile.is_approved:
            return False

    # Obtener el SharedFile asociado al PrivateFile
    relative_name = private_file.relative_name
    try:
        shared_file = SharedFile.objects.get(file=relative_name)
    except SharedFile.DoesNotExist:
        return False

    if shared_file.visibility == SharedFile.Visibility.PUBLIC:
        return True

    if not user.is_authenticated:
        return False

    if shared_file.visibility == SharedFile.Visibility.REGISTERED:
        return True

    if shared_file.visibility == SharedFile.Visibility.PRIVATE:
        return FilePermission.objects.filter(
            shared_file=shared_file,
            patient=user,
        ).exists()

    return False
