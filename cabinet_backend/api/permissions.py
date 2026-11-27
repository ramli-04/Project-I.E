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


def can_operate_task(task, request, role=None):
    """Assignment permission only; task readiness is checked separately."""
    role = role or actor_role(request)
    if role == 'MANAGER':
        return True
    employee = task.assigned_employee
    if not employee or role != task.required_role:
        return False
    return (employee.platform_account_id == request.user.pk
            if isinstance(request.user, PlatformAccount) else employee.user_id == request.user.pk)

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


class CapacityPreviewPermission(TenantMemberPermission):
    """Same creation scope, including linked dentists, with no list access."""
    def has_permission(self, request, view):
        tenant, user = getattr(request, 'tenant', None), request.user
        if not tenant or tenant.schema_name == 'public' or not tenant.is_active or not user.is_authenticated:
            return False
        if isinstance(user, PlatformAccount) and user.role == 'DENTIST':
            from .models import PartnerClinic
            return user.is_active and PartnerClinic.objects.filter(platform_dentist=user).exists()
        return super().has_permission(request, view) and actor_role(request) in {'MANAGER', 'RECEPTION'}
