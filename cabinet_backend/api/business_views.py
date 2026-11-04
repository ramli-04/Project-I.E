import uuid
from decimal import InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import FileResponse, HttpResponse
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import (ProductionLot, BillingPeriod, StatementLine, FinanceInvoice, CreditNote, BillingDispute,
                     TaskOutbox, CaseNotification, WorkflowEvent, MessageDelivery)
from .permissions import LaboratoryResourcePermission, actor_role
from .case_serializers import actor_identity


def translate_error(exc):
    return ValidationError(getattr(exc, 'message_dict', getattr(exc, 'messages', ['Invalid command payload.'])))


class BusinessPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class LotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionLot
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class ProductionLotViewSet(viewsets.ModelViewSet):
    permission_classes = [LaboratoryResourcePermission]
    write_roles = {'MANAGER', 'FAO'}
    queryset = ProductionLot.objects.prefetch_related('prescriptions').all().order_by('-created_at')
    serializer_class = LotSerializer
    pagination_class = BusinessPagination
    http_method_names = ['get', 'post', 'head', 'options']  # Preserve case/lot traceability.


class PeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPeriod
        fields = '__all__'


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceInvoice
        fields = '__all__'


class LineSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatementLine
        fields = '__all__'


class FinanceReadViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [LaboratoryResourcePermission]
    read_roles = write_roles = {'MANAGER', 'COMPTABILITE'}
    pagination_class = BusinessPagination


class BillingPeriodViewSet(FinanceReadViewSet):
    queryset = BillingPeriod.objects.select_related('clinic').all().order_by('-month', 'pk')
    serializer_class = PeriodSerializer

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        from .billing import close_period
        try:
            invoice = close_period(self.get_object().pk, actor_identity(request))
        except DjangoValidationError as exc:
            raise translate_error(exc) from exc
        return Response(InvoiceSerializer(invoice).data)


class StatementLineViewSet(FinanceReadViewSet):
    queryset = StatementLine.objects.all().order_by('period_id', 'prescription_id')
    serializer_class = LineSerializer

    def get_queryset(self):
        query = super().get_queryset()
        if self.request.query_params.get('period'):
            try:
                query = query.filter(period_id=uuid.UUID(self.request.query_params['period']))
            except ValueError as exc:
                raise ValidationError('Invalid period UUID.') from exc
        return query

    @action(detail=True, methods=['post'])
    def adjust(self, request, pk=None):
        from .billing import adjust_statement_line
        try:
            line = adjust_statement_line(self.get_object().pk, contested=request.data.get('contested'),
                excluded=request.data.get('excluded'), reason=str(request.data.get('reason', '')), actor=actor_identity(request))
        except DjangoValidationError as exc:
            raise translate_error(exc) from exc
        return Response(LineSerializer(line).data)


class FinanceInvoiceViewSet(FinanceReadViewSet):
    queryset = FinanceInvoice.objects.all().order_by('-issued_at', 'pk')
    serializer_class = InvoiceSerializer

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        from .documents import private_open
        invoice = self.get_object()
        if not hasattr(invoice, 'document'):
            return Response({'status': 'PDF_PENDING'}, status=202)
        return FileResponse(private_open(invoice.document.storage_name), content_type='application/pdf',
                            as_attachment=True, filename=invoice.number + '.pdf')

    @action(detail=True, methods=['post'])
    def credit(self, request, pk=None):
        from .billing import issue_credit
        try:
            credit = issue_credit(self.get_object().pk, request.data.get('prescription'), request.data.get('amount'),
                str(request.data.get('reason', '')), actor_identity(request), uuid.UUID(request.headers.get('Idempotency-Key', '')))
        except (DjangoValidationError, ValueError, TypeError, InvalidOperation) as exc:
            raise translate_error(exc) from exc
        return Response({'id': str(credit.pk), 'amount': str(credit.amount), 'status': 'PDF_PENDING'}, status=201)


class DisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingDispute
        fields = '__all__'


class BillingDisputeViewSet(FinanceReadViewSet):
    queryset = BillingDispute.objects.all().order_by('-created_at', 'pk')
    serializer_class = DisputeSerializer

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        decision, notes = request.data.get('decision'), str(request.data.get('notes', '')).strip()
        if decision not in {'ACCEPTED', 'REJECTED'} or not notes:
            raise ValidationError('Supply ACCEPTED/REJECTED and resolution notes.')
        from django.utils import timezone
        with transaction.atomic():
            dispute = self.get_queryset().select_for_update().get(pk=self.get_object().pk)
            if dispute.status != 'OPEN':
                raise ValidationError('This dispute is already resolved.')
            if decision == 'ACCEPTED':
                if dispute.invoice_id:
                    from .billing import issue_credit
                    try:
                        issue_credit(dispute.invoice_id, dispute.prescription_id, request.data.get('amount'), notes,
                                     actor_identity(request), uuid.uuid5(uuid.NAMESPACE_URL, f'dispute:{dispute.pk}'))
                    except (DjangoValidationError, InvalidOperation, TypeError) as exc:
                        raise translate_error(exc) from exc
                else:
                    from .billing import adjust_statement_line
                    line = StatementLine.objects.filter(prescription=dispute.prescription).first()
                    if line:
                        adjust_statement_line(line.pk, contested=True, excluded=True, reason=notes, actor=actor_identity(request))
            else:
                line = StatementLine.objects.filter(prescription=dispute.prescription, period__closed_at__isnull=True).first()
                if line:
                    from .billing import adjust_statement_line
                    adjust_statement_line(line.pk, contested=False, excluded=False, reason=notes, actor=actor_identity(request))
            dispute.status, dispute.resolved_at, dispute.resolution_notes = decision, timezone.now(), notes
            dispute.save(update_fields=['status', 'resolved_at', 'resolution_notes'])
            WorkflowEvent.objects.create(prescription=dispute.prescription, kind='DISPUTE_RESOLVED', changed_by=actor_identity(request),
                                         payload={'dispute_id': str(dispute.pk), 'decision': decision, 'notes': notes})
        return Response(DisputeSerializer(dispute).data)


class OutboxSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskOutbox
        fields = '__all__'


class OutboxViewSet(FinanceReadViewSet):
    queryset = TaskOutbox.objects.all().order_by('-created_at', 'pk')
    serializer_class = OutboxSerializer
    read_roles = write_roles = {'MANAGER'}

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        from django.utils import timezone
        with transaction.atomic():
            event = self.get_queryset().select_for_update().get(pk=self.get_object().pk)
            if event.processed_at:
                raise ValidationError('Completed events cannot be retried.')
            event.failed_at, event.attempts, event.last_error, event.next_attempt_at = None, 0, '', timezone.now()
            event.save(update_fields=['failed_at', 'attempts', 'last_error', 'next_attempt_at'])
            WorkflowEvent.objects.create(prescription=event.prescription, kind='OUTBOX_RETRY', changed_by=actor_identity(request),
                                         payload={'event_id': str(event.pk)})
        return Response({'status': 'RETRY_SCHEDULED'})


class DeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageDelivery
        fields = '__all__'


class MessageDeliveryViewSet(FinanceReadViewSet):
    queryset = MessageDelivery.objects.all().order_by('-notification__created_at', 'pk')
    serializer_class = DeliverySerializer

    @action(detail=True, methods=['post'])
    def reconcile(self, request, pk=None):
        from django.utils import timezone
        sent, notes = request.data.get('sent'), str(request.data.get('notes', '')).strip()
        if type(sent) is not bool or not notes:
            raise ValidationError('Confirm provider outcome with sent=true/false and reconciliation notes.')
        with transaction.atomic():
            delivery = self.get_queryset().select_for_update().get(pk=self.get_object().pk)
            if delivery.status not in {'UNKNOWN', 'SENDING'}:
                raise ValidationError('Only ambiguous or interrupted sends require reconciliation.')
            delivery.status = 'SENT' if sent else 'PENDING'
            delivery.sent_at = timezone.now() if sent else None
            delivery.last_error = ''
            delivery.save(update_fields=['status', 'sent_at', 'last_error'])
            WorkflowEvent.objects.create(prescription=delivery.notification.prescription, kind='DELIVERY_RECONCILED',
                changed_by=actor_identity(request), payload={'delivery_id': str(delivery.pk), 'sent': sent, 'notes': notes})
        return Response({'status': delivery.status})


class CreditSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditNote
        fields = '__all__'


class CreditNoteViewSet(FinanceReadViewSet):
    queryset = CreditNote.objects.all().order_by('-issued_at', 'pk')
    serializer_class = CreditSerializer

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        from .documents import private_open
        credit = self.get_object()
        if not hasattr(credit, 'document'):
            return Response({'status': 'PDF_PENDING'}, status=202)
        return FileResponse(private_open(credit.document.storage_name), content_type='application/pdf', as_attachment=True,
                            filename=f'avoir-{credit.pk}.pdf')
