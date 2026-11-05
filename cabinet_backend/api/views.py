import logging

from django.core.cache import cache
from django.db import transaction
from django.db.models.deletion import ProtectedError
from redis.exceptions import RedisError
from rest_framework import viewsets, mixins
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import api_view, permission_classes
from .permissions import DemoTenantPermission, LaboratoryResourcePermission
from .permissions import PrescriptionPermission, actor_role
from .case_serializers import CourierPrescriptionSerializer, actor_identity
from .business_views import BusinessPagination, translate_error
from .planning_views import ResourcePlanningMixin
from rest_framework.decorators import action
from django.core.exceptions import ValidationError as DjangoValidationError
from decimal import InvalidOperation
from django.http import HttpResponse, FileResponse
from rest_framework.response import Response
from .alerts import laboratory_alerts
from .models import Prescription, StaffMember, Equipment, StockItem, EmployeeProfile, Machine, Inventory, PartnerClinic, InventoryTransaction
from .serializers import (
    PrescriptionSerializer, StaffMemberSerializer, EquipmentSerializer, StockItemSerializer,
    EmployeeProfileSerializer, MachineSerializer, InventorySerializer, PartnerClinicSerializer, InventoryTransactionSerializer,
)

logger = logging.getLogger(__name__)


class EmployeeProfileViewSet(ResourcePlanningMixin, viewsets.ModelViewSet):
    permission_classes = [LaboratoryResourcePermission]
    queryset = EmployeeProfile.objects.select_related('user','platform_account').all()
    serializer_class = EmployeeProfileSerializer


class MachineViewSet(ResourcePlanningMixin, viewsets.ModelViewSet):
    write_roles = {'MANAGER', 'FAO'}
    permission_classes = [LaboratoryResourcePermission]
    queryset = Machine.objects.all()
    serializer_class = MachineSerializer


class InventoryViewSet(viewsets.ModelViewSet):
    write_roles = {'MANAGER', 'FAO'}
    permission_classes = [LaboratoryResourcePermission]
    queryset = Inventory.objects.all()
    serializer_class = InventorySerializer

    def perform_destroy(self, instance):
        raise ValidationError('Inventory with an immutable opening balance cannot be deleted.')


class LedgerPagination(PageNumberPagination):
    page_size = 50


class InventoryTransactionViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                                  mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [LaboratoryResourcePermission]
    write_roles = {'MANAGER', 'FAO', 'RECEPTION'}
    queryset = InventoryTransaction.objects.all()
    serializer_class = InventoryTransactionSerializer
    pagination_class = LedgerPagination
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        queryset = super().get_queryset()
        for param, field in [('inventory_item', 'inventory_item_id'), ('prescription', 'prescription_id')]:
            value = self.request.query_params.get(param)
            if value:
                try:
                    from django.core.exceptions import ValidationError as DjangoValidationError
                    value = InventoryTransaction._meta.get_field(field).target_field.to_python(value)
                except (ValueError, TypeError, DjangoValidationError) as exc:
                    raise ValidationError({param: 'Invalid identifier.'}) from exc
                queryset = queryset.filter(**{field: value})
        return queryset


class PartnerClinicViewSet(viewsets.ModelViewSet):
    write_roles = {'MANAGER', 'RECEPTION'}
    permission_classes = [LaboratoryResourcePermission]
    queryset = PartnerClinic.objects.all()
    serializer_class = PartnerClinicSerializer


@api_view(['GET'])
@permission_classes([DemoTenantPermission])
def alerts_view(request):
    return Response(laboratory_alerts())


class StaffMemberViewSet(viewsets.ModelViewSet):
    permission_classes = [DemoTenantPermission]
    queryset = StaffMember.objects.all()
    serializer_class = StaffMemberSerializer


class EquipmentViewSet(viewsets.ModelViewSet):
    permission_classes = [DemoTenantPermission]
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer


class StockItemViewSet(viewsets.ModelViewSet):
    permission_classes = [DemoTenantPermission]
    queryset = StockItem.objects.all()
    serializer_class = StockItemSerializer


class PrescriptionViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for Prescriptions (3-portal workflow).

    list:           GET    /api/prescriptions/       — all prescriptions (newest first)
    create:         POST   /api/prescriptions/       — dentist submits a new prescription
    retrieve:       GET    /api/prescriptions/{id}/  — single prescription detail
    partial_update: PATCH  /api/prescriptions/{id}/  — lab/courier updates status or delivery_date
    """
    queryset = Prescription.objects.select_related('partner_clinic', 'dentist_account').prefetch_related('clinical_items').all()
    permission_classes = [PrescriptionPermission]
    serializer_class = PrescriptionSerializer
    pagination_class = BusinessPagination

    def get_serializer_class(self):
        return CourierPrescriptionSerializer if actor_role(self.request) == 'COURIER' else PrescriptionSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, '_lock_prescription', False):
            queryset = queryset.select_for_update(of=('self',))
        return queryset

    def list(self, request, *args, **kwargs):
        from .models import TenantReadVersion
        role = actor_role(request)
        if role == 'COURIER' or request.query_params.get('scope') == 'archived' or request.query_params.get('include_completed', '').lower() == 'true':
            query = self.get_queryset()
            if role == 'COURIER':
                query = query.filter(status__in=['ATTENTE_RAMASSAGE', 'EN_ROUTE_LABO', 'PRET_EXPEDITION', 'EN_ROUTE_CABINET'])
            elif request.query_params.get('scope') == 'archived':
                query = query.filter(status__in=['LIVRE', 'ESSAYAGE', 'CLOTURE'])
            page = self.paginate_queryset(query)
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        generation = TenantReadVersion.objects.get_or_create(name='active_orders')[0].version
        try:
            envelope = cache.get('active_orders')
        except (RedisError, OSError):
            logger.warning('Active-order cache unavailable; reading PostgreSQL.', exc_info=True)
            envelope = None
        data = envelope.get('rows') if isinstance(envelope, dict) and envelope.get('version') == generation else None
        if data is None:
            queryset = self.filter_queryset(self.get_queryset()).exclude(status__in=['LIVRE', 'ESSAYAGE', 'CLOTURE'])
            data = list(PrescriptionSerializer(queryset, many=True).data)
            try:
                cache.set('active_orders', {'version': generation, 'rows': data}, timeout=3600)
            except (RedisError, OSError):
                logger.warning('Could not populate active-order cache.', exc_info=True)
        if request.query_params.get('status'):
            data = [row for row in data if row['status'] == request.query_params['status']]
        if role != 'MANAGER':
            data = [{**row, 'workstation_notes': {role: row['workstation_notes'][role]} if role in row.get('workstation_notes', {}) else {}} for row in data]
        page = self.paginate_queryset(data)
        return self.get_paginated_response(page)

    def update(self, request, *args, **kwargs):
        # Lock before serializer validation, preventing stale workflow checks.
        with transaction.atomic():
            self._lock_prescription = True
            return super().update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as exc:
            raise ValidationError('Audited prescriptions cannot be deleted.') from exc

    def perform_create(self, serializer):
        if actor_role(self.request) not in {'MANAGER', 'RECEPTION'}:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Reception access is required to create a case in this laboratory.')
        serializer.save()

    @action(detail=True, methods=['post'])
    def command(self, request, pk=None):
        from .case_commands import execute_case_command
        self.get_object()
        try:
            order, result = execute_case_command(pk, request.data.get('action'), request.data.get('data', {}),
                actor_identity(request), actor_role(request), request.headers.get('Idempotency-Key'))
        except (DjangoValidationError, ValueError, TypeError, InvalidOperation) as exc:
            raise translate_error(exc) from exc
        if result.get('error'):
            return Response({'detail': result['error']}, status=result.get('http_status', 400))
        return Response({'case': self.get_serializer(order).data, 'result': result})

    @action(detail=True, methods=['get', 'post'])
    def attachments(self, request, pk=None):
        if actor_role(request) == 'COURIER':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Clinical attachments are restricted to dental and laboratory staff.')
        order = self.get_object()
        if request.method == 'POST':
            from .documents import save_attachment
            try:
                with transaction.atomic():
                    record = save_attachment(order, request.FILES.get('file'), request.data.get('kind'), actor_identity(request))
            except DjangoValidationError as exc:
                raise translate_error(exc) from exc
            return Response({'id': str(record.pk), 'kind': record.kind, 'name': record.original_name}, status=201)
        return Response(list(order.attachments.values('id', 'kind', 'original_name', 'sha256', 'byte_size', 'created_at')))

    @action(detail=True, methods=['get'], url_path='attachment/(?P<attachment_id>[^/.]+)')
    def attachment(self, request, pk=None, attachment_id=None):
        if actor_role(request) == 'COURIER':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Clinical documents are restricted.')
        from .documents import private_open
        from django.shortcuts import get_object_or_404
        record = get_object_or_404(self.get_object().attachments, pk=attachment_id)
        return FileResponse(private_open(record.storage_name), content_type=record.content_type,
                            as_attachment=True, filename=record.original_name)

    @action(detail=True, methods=['get'])
    def evidence(self, request, pk=None):
        if actor_role(request) == 'COURIER':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Clinical evidence is restricted.')
        order = self.get_object()
        return Response({
            'inspections': list(order.inspections.values()), 'design_reviews': list(order.design_reviews.values()),
            'reworks': list(order.reworks.values()),
            'attachments': list(order.attachments.values('id', 'kind', 'original_name', 'created_at')),
            'events': list(order.events.order_by('-created_at').values()[:100]),
            'notifications': list(order.notifications.order_by('-created_at').values()[:100]),
        })

    @action(detail=True, methods=['get'])
    def qr(self, request, pk=None):
        if actor_role(request) not in {'MANAGER', 'RECEPTION'}:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Reception staff print case labels.')
        from .documents import qr_png
        return HttpResponse(qr_png(self.get_object()), content_type='image/png')

    @action(detail=True, methods=['get'], url_path='delivery-slip')
    def delivery_slip(self, request, pk=None):
        from .documents import delivery_slip
        order = self.get_object()
        if order.status not in {'CONDITIONNEMENT', 'PRET_EXPEDITION', 'EN_ROUTE_CABINET', 'LIVRE', 'ESSAYAGE', 'CLOTURE'}:
            raise ValidationError('Delivery slips are available after quality control.')
        response = HttpResponse(delivery_slip(order), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="delivery-{order.pk}.pdf"'
        return response
