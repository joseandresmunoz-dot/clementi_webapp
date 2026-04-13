from django.contrib.auth import get_user_model
from rest_framework import serializers

from files_manager.models import FilePermission, SharedFile

User = get_user_model()


class FilePermissionSerializer(serializers.ModelSerializer):
    patient_email = serializers.EmailField(source="patient.email", read_only=True)
    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)

    class Meta:
        model = FilePermission
        fields = ["id", "patient", "patient_email", "patient_name", "granted_at"]
        read_only_fields = ["id", "granted_at"]


class SharedFileListSerializer(serializers.ModelSerializer):
    """Serializer liviano para listados."""

    download_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.CharField(
        source="uploaded_by.get_full_name", read_only=True, default=""
    )

    class Meta:
        model = SharedFile
        fields = [
            "id",
            "title",
            "description",
            "file_type",
            "visibility",
            "download_url",
            "uploaded_by_name",
            "created_at",
        ]

    def get_download_url(self, obj):
        request = self.context.get("request")
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        return None


class SharedFileDetailSerializer(serializers.ModelSerializer):
    """Serializer completo con permisos (solo staff)."""

    permissions = FilePermissionSerializer(many=True, read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = SharedFile
        fields = [
            "id",
            "title",
            "description",
            "file",
            "file_type",
            "visibility",
            "uploaded_by",
            "download_url",
            "permissions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "uploaded_by", "created_at", "updated_at"]

    def get_download_url(self, obj):
        request = self.context.get("request")
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        return None


class SharedFileUploadSerializer(serializers.ModelSerializer):
    """Serializer para subida de archivos (staff)."""

    class Meta:
        model = SharedFile
        fields = ["id", "title", "description", "file", "file_type", "visibility"]
        read_only_fields = ["id"]
