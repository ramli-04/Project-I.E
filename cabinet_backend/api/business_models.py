"""Tenant-owned workflow evidence and accounting documents."""
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class EvidenceQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('Evidence is append-only.')

    def delete(self):
        raise ValidationError('Evidence cannot be deleted.')

    def bulk_create(self, objs, **kwargs):
        raise ValidationError('Append evidence individually.')


class ImmutableEvidence(models.Model):
    objects = EvidenceQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Evidence is append-only.')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Evidence cannot be deleted.')


class WorkflowEvent(ImmutableEvidence):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription = models.ForeignKey('api.Prescription', on_delete=models.PROTECT, related_name='events')
    kind = models.CharField(max_length=50)
    payload = models.JSONField(default=dict)
    changed_by = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']


class CaseCommandReceipt(ImmutableEvidence):
    idempotency_key = models.UUIDField(primary_key=True)
    prescription = models.ForeignKey('api.Prescription', on_delete=models.PROTECT)
    command = models.CharField(max_length=40)
    payload_digest = models.CharField(max_length=64)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class BillingDispute(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription = models.ForeignKey('api.Prescription', on_delete=models.PROTECT, related_name='billing_disputes')
    invoice = models.ForeignKey('api.FinanceInvoice', null=True, blank=True, on_delete=models.PROTECT)
    reason = models.TextField()
    status = models.CharField(max_length=10, default='OPEN', choices=[('OPEN', 'Open'), ('ACCEPTED', 'Accepted'), ('REJECTED', 'Rejected')])
    raised_by = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)


class ClinicalItem(ImmutableEvidence):
    prescription = models.ForeignKey('api.Prescription', on_delete=models.PROTECT, related_name='clinical_items')
    tooth_number = models.PositiveSmallIntegerField()
    function = models.CharField(max_length=100)
    form = models.CharField(max_length=100)
    shade = models.CharField(max_length=10)
    material = models.CharField(max_length=50)
    base_amount = models.DecimalField(max_digits=12, decimal_places=2)


class CaseAttachment(ImmutableEvidence):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription = models.ForeignKey('api.Prescription', on_delete=models.PROTECT, related_name='attachments')
    kind = models.CharField(max_length=10, choices=[('STL', 'STL'), ('PHOTO', 'Photo'), ('DESIGN', 'Design')])
    storage_name = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    byte_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=80)
    uploaded_by = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


class CaseInspection(ImmutableEvidence):
    prescription = models.ForeignKey('api.Prescription', on_delete=models.PROTECT, related_name='inspections')
    stage = models.CharField(max_length=10, choices=[('PHYSICAL', 'Physical intake'), ('DIGITAL', 'STL control'), ('MODEL', 'Model and scan'), ('QUALITY', 'Quality control')])
    production_attempt = models.PositiveIntegerField(default=1)
    intake_revision = models.PositiveIntegerField(default=1)
    passed = models.BooleanField()
    checks = models.JSONField()
    notes = models.TextField(blank=True)
    photo = models.ForeignKey(CaseAttachment, null=True, blank=True, on_delete=models.PROTECT)
    checked_by = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


class DesignReview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription = models.ForeignKey('api.Prescription', on_delete=models.PROTECT, related_name='design_reviews')
    attachment = models.ForeignKey(CaseAttachment, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    production_attempt = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, default='PENDING', choices=[('PENDING', 'Pending'), ('APPROVED', 'Approved'), ('CHANGES_REQUESTED', 'Changes requested')])
    requested_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    response_notes = models.TextField(blank=True)
    responded_by = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['prescription', 'version'], name='case_design_version_unique')]


class ProductionLot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=80, unique=True)
    inventory_item = models.ForeignKey('api.Inventory', null=True, blank=True, on_delete=models.PROTECT)
    machine = models.ForeignKey('api.Machine', null=True, blank=True, on_delete=models.PROTECT)
    prescriptions = models.ManyToManyField('api.Prescription', related_name='production_lots')
    created_at = models.DateTimeField(auto_now_add=True)


class ReworkCase(ImmutableEvidence):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription = models.ForeignKey('api.Prescription', on_delete=models.PROTECT, related_name='reworks')
    history = models.OneToOneField('api.PrescriptionHistory', on_delete=models.PROTECT)
    attempt = models.PositiveIntegerField()
    origin = models.CharField(max_length=6, choices=[('LAB', 'Laboratory'), ('CLINIC', 'Clinic')])
    cause_step = models.CharField(max_length=20)
    restart_status = models.CharField(max_length=20)
    cause = models.TextField()
    action = models.TextField()
    losses = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['prescription', 'attempt'], name='one_rework_per_attempt')]


class BillingPeriod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.ForeignKey('api.PartnerClinic', on_delete=models.PROTECT, related_name='billing_periods')
    month = models.DateField()
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['clinic', 'month'], name='one_clinic_month_period')]


class StatementLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period = models.ForeignKey(BillingPeriod, on_delete=models.PROTECT, related_name='lines')
    prescription = models.OneToOneField('api.Prescription', on_delete=models.PROTECT, related_name='statement_line')
    base_amount = models.DecimalField(max_digits=12, decimal_places=2)
    express_surcharge = models.DecimalField(max_digits=12, decimal_places=2)
    contested = models.BooleanField(default=False)
    excluded = models.BooleanField(default=False)
    dispute_reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict)


class FinanceInvoice(ImmutableEvidence):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period = models.OneToOneField(BillingPeriod, on_delete=models.PROTECT, related_name='invoice')
    number = models.CharField(max_length=80, unique=True)
    clinic_name = models.CharField(max_length=120)
    lines = models.JSONField()
    base_amount = models.DecimalField(max_digits=16, decimal_places=2)
    express_surcharge = models.DecimalField(max_digits=16, decimal_places=2)
    total_amount = models.DecimalField(max_digits=16, decimal_places=2)
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.CharField(max_length=255)


class InvoiceDocument(ImmutableEvidence):
    invoice = models.OneToOneField(FinanceInvoice, on_delete=models.PROTECT, related_name='document')
    storage_name = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class CreditNote(ImmutableEvidence):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(FinanceInvoice, on_delete=models.PROTECT, related_name='credit_notes')
    prescription = models.ForeignKey('api.Prescription', on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    reason = models.TextField()
    issued_by = models.CharField(max_length=255)
    idempotency_key = models.UUIDField(unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)


class CreditDocument(ImmutableEvidence):
    credit_note = models.OneToOneField(CreditNote, on_delete=models.PROTECT, related_name='document')
    storage_name = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class CaseNotification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription = models.ForeignKey('api.Prescription', on_delete=models.PROTECT, related_name='notifications')
    event_key = models.CharField(max_length=255, unique=True)
    kind = models.CharField(max_length=40)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)


class MessageDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(CaseNotification, on_delete=models.PROTECT, related_name='deliveries')
    channel = models.CharField(max_length=10, choices=[('EMAIL', 'Email'), ('WHATSAPP', 'WhatsApp')])
    destination = models.CharField(max_length=255)
    status = models.CharField(max_length=24, default='PENDING')
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    last_error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    provider_reference = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['notification', 'channel', 'destination'], name='one_notification_delivery')]


class TenantReadVersion(models.Model):
    name = models.CharField(primary_key=True, max_length=40, default='active_orders')
    version = models.PositiveBigIntegerField(default=0)


class MonthlyStatementCatalog(models.Model):
    prescription_id = models.UUIDField(primary_key=True)
    clinic_id = models.BigIntegerField()
    closing_month = models.DateField()
    patient_ref = models.CharField(max_length=50)
    delivered_at = models.DateTimeField()
    base_amount = models.DecimalField(max_digits=12, decimal_places=2)
    express_surcharge = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    contested = models.BooleanField()
    excluded = models.BooleanField()
    billed = models.BooleanField()
    refreshed_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'monthly_statement_catalog'
        ordering = ['-closing_month', 'prescription_id']


class MonthlyFinancialCatalog(models.Model):
    invoice_id = models.UUIDField(primary_key=True)
    number = models.CharField(max_length=80)
    clinic_id = models.BigIntegerField()
    clinic_name = models.CharField(max_length=120)
    closing_month = models.DateField()
    base_amount = models.DecimalField(max_digits=16, decimal_places=2)
    express_surcharge = models.DecimalField(max_digits=16, decimal_places=2)
    gross_amount = models.DecimalField(max_digits=16, decimal_places=2)
    credited_amount = models.DecimalField(max_digits=16, decimal_places=2)
    net_amount = models.DecimalField(max_digits=16, decimal_places=2)
    refreshed_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'monthly_financial_catalog'
        ordering = ['-closing_month', 'invoice_id']
