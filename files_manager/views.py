from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from files_manager.models import FilePermission, SharedFile
from files_manager.serializers import (
    FilePermissionSerializer,
    SharedFileDetailSerializer,
    SharedFileListSerializer,
    SharedFileUploadSerializer,
)
from patients.models import PatientProfile

User = get_user_model()


class IsStaffPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff


class SharedFileViewSet(viewsets.ModelViewSet):
    """
    Endpoints de gestión de archivos.

    Staff:  CRUD completo + asignar permisos privados.
    Pacientes: solo listar y descargar los que les corresponden.
    """

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy",
                           "assign_permission", "remove_permission"):
            return [IsStaffPermission()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "create":
            return SharedFileUploadSerializer
        if self.action in ("retrieve", "update", "partial_update"):
            return SharedFileDetailSerializer
        return SharedFileListSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return SharedFile.objects.all()

        profile = PatientProfile.objects.filter(user=user).first()
        if not profile or not profile.is_approved:
            return SharedFile.objects.none()

        # Pacientes: PUBLIC + REGISTERED + PRIVATE con permiso
        private_ids = FilePermission.objects.filter(
            patient=user
        ).values_list("shared_file_id", flat=True)

        return SharedFile.objects.filter(
            Q(visibility=SharedFile.Visibility.PUBLIC)
            | Q(visibility=SharedFile.Visibility.REGISTERED)
            | Q(visibility=SharedFile.Visibility.PRIVATE, id__in=private_ids)
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        visibility = request.query_params.get("visibility")
        if visibility:
            queryset = queryset.filter(visibility=visibility)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def paginated_response(self, data):
        return self.get_paginated_response(data)

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    # ── Asignar permiso a paciente (archivo PRIVATE) ─────────────
    @action(detail=True, methods=["post"], url_path="assign")
    def assign_permission(self, request, pk=None):
        shared_file = self.get_object()
        patient_id = request.data.get("patient_id")

        if not patient_id:
            return Response(
                {"error": "Se requiere patient_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            patient = User.objects.get(pk=patient_id)
        except User.DoesNotExist:
            return Response(
                {"error": "Paciente no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        perm, created = FilePermission.objects.get_or_create(
            shared_file=shared_file, patient=patient
        )

        if not created:
            return Response(
                {"message": "El paciente ya tiene acceso a este archivo."},
                status=status.HTTP_200_OK,
            )

        return Response(
            FilePermissionSerializer(perm).data,
            status=status.HTTP_201_CREATED,
        )

    # ── Quitar permiso ───────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="revoke")
    def remove_permission(self, request, pk=None):
        shared_file = self.get_object()
        patient_id = request.data.get("patient_id")

        if not patient_id:
            return Response(
                {"error": "Se requiere patient_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted, _ = FilePermission.objects.filter(
            shared_file=shared_file, patient_id=patient_id
        ).delete()

        if not deleted:
            return Response(
                {"error": "No existía permiso para este paciente."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Listar pacientes para select (staff) ─────────────────────
    @action(detail=False, methods=["get"], url_path="patients")
    def list_patients(self, request):
        if not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)

        patients = User.objects.filter(
            is_staff=False,
            patient_profile__is_approved=True,
        ).values(
            "id", "email", "first_name", "last_name"
        )
        return Response(list(patients))
