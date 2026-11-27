"""Read without creating defaults; manager-only tenant identity updates."""
from django.db import transaction
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from customers.models import Client
from .models import LaboratoryProfile
from .permissions import TenantMemberPermission, actor_role
from .case_serializers import actor_identity


class LaboratoryProfilePermission(TenantMemberPermission):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return actor_role(request) in ({'MANAGER', 'COMPTABILITE'} if request.method in {'GET', 'HEAD', 'OPTIONS'} else {'MANAGER'})


class LaboratoryProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = LaboratoryProfile
        fields = ['id', 'legal_name', 'address', 'city', 'phone', 'email', 'ice',
                  'identifiant_fiscal', 'registre_commerce', 'patente', 'updated_at', 'updated_by']
        read_only_fields = ['id', 'updated_at', 'updated_by']
        extra_kwargs = {'ice': {'trim_whitespace': False}}


@api_view(['GET', 'PUT'])
@permission_classes([LaboratoryProfilePermission])
def laboratory_profile(request):
    if request.method == 'PUT':
        with transaction.atomic():
            # Lock the owning tenant even before the singleton exists, serializing first creation.
            Client.objects.select_for_update().get(pk=request.tenant.pk)
            profile = LaboratoryProfile.objects.filter(pk=1).first()
            serializer = LaboratoryProfileSerializer(profile, data=request.data)
            serializer.is_valid(raise_exception=True)
            profile = serializer.save(updated_by=actor_identity(request))
    else:
        profile = LaboratoryProfile.objects.filter(pk=1).first() or LaboratoryProfile()
    response = Response(LaboratoryProfileSerializer(profile).data)
    response['Cache-Control'] = 'no-store'
    return response
