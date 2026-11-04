from rest_framework.permissions import BasePermission, SAFE_METHODS
from customers.models import PlatformAccount


def actor_role(request):
    user = request.user
    if not user or not user.is_authenticated:
        return None
    if isinstance(user, PlatformAccount):
        return user.workstation_role if user.role == 'LAB' else user.role
    if user.is_superuser:
        return 'MANAGER'
    from .models import EmployeeProfile
    role = EmployeeProfile.objects.filter(user_id=user.pk).values_list('role', flat=True).first()
    return 'COURIER' if role == 'COURSIER' else role

class TenantMemberPermission(BasePermission):
    message = 'Authenticated membership of this laboratory is required.'

    def has_permission(self, request, view):
        tenant = getattr(request, 'tenant', None)
        user = request.user
        if tenant is None or tenant.schema_name == 'public' or not tenant.is_active or not user.is_authenticated:
            return False
        if isinstance(user, PlatformAccount):
            return user.is_active and user.role in {'LAB', 'COURIER'} and user.laboratory_id == tenant.pk
        return actor_role(request) is not None


class LaboratoryResourcePermission(TenantMemberPermission):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        role = actor_role(request)
        if role == 'COURIER':
            return False
        if request.method in SAFE_METHODS:
            return role in getattr(view, 'read_roles', {'MANAGER', 'RECEPTION', 'CAO', 'FAO', 'QUALITE', 'COMPTABILITE'})
        return role in getattr(view, 'write_roles', {'MANAGER'})

class PrescriptionPermission(TenantMemberPermission):
    pass


DemoTenantPermission = LaboratoryResourcePermission
