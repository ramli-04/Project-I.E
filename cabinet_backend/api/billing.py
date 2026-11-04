"""Delivery-month statements, immutable closing and compensating credit notes."""
from decimal import Decimal
import uuid

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (BillingPeriod, StatementLine, FinanceInvoice, CreditNote, Prescription,
                     WorkflowEvent, BillingDispute)
from .signals import prescription_audit_context
from .outbox import enqueue_event


def billing_lock(clinic_id):
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                       [f'billing:{connection.schema_name}:{clinic_id}'])


def add_delivered_case(order):
    if order.delivered_at is None or order.partner_clinic_id is None or order.total_price is None:
        raise ValidationError('A delivered case requires a clinic and confirmed pricing.')
    month = timezone.localdate(order.delivered_at).replace(day=1)
    billing_lock(order.partner_clinic_id)
    period, _ = BillingPeriod.objects.get_or_create(clinic_id=order.partner_clinic_id, month=month)
    period = BillingPeriod.objects.select_for_update().get(pk=period.pk)
    if period.closed_at:
        raise ValidationError('The delivery period is closed. Use an explicit accounting adjustment.')
    line, _ = StatementLine.objects.get_or_create(prescription=order, defaults={
        'period': period, 'base_amount': order.base_amount, 'express_surcharge': order.express_surcharge,
        'snapshot': {'case_id': str(order.pk), 'patient_ref': order.patient_ref,
                     'delivery_service': order.delivery_service, 'delivered_at': order.delivered_at.isoformat(),
                     'items': list(order.clinical_items.values('tooth_number', 'function', 'form', 'shade', 'material'))},
    })
    enqueue_event(order, 'CATALOG', f'statement:{line.pk}')
    return line


def close_period(period_id, actor):
    initial = BillingPeriod.objects.get(pk=period_id)
    with transaction.atomic():
        billing_lock(initial.clinic_id)
        period = BillingPeriod.objects.select_for_update().select_related('clinic').get(pk=period_id)
        if period.closed_at:
            return period.invoice
        if period.month >= timezone.localdate().replace(day=1):
            raise ValidationError('Close a monthly statement only after the delivery month has ended.')
        lines = list(period.lines.select_related('prescription').order_by('prescription_id'))
        included = [line for line in lines if not line.contested and not line.excluded]
        if not included:
            raise ValidationError('No uncontested, included cases remain to invoice.')
        snapshots = []
        for line in included:
            source = Prescription.objects.select_for_update().get(pk=line.prescription_id)
            if source.invoiced_at or source.total_price is None:
                raise ValidationError('A statement case is already invoiced or still awaits a quote.')
            snapshots.append({**line.snapshot, 'case_id': str(source.pk), 'base_amount': str(line.base_amount),
                              'express_surcharge': str(line.express_surcharge),
                              'total_amount': str(line.base_amount + line.express_surcharge)})
        base = sum((line.base_amount for line in included), Decimal('0'))
        extra = sum((line.express_surcharge for line in included), Decimal('0'))
        invoice = FinanceInvoice.objects.create(period=period,
            number=f'INV-{period.month:%Y%m}-{connection.schema_name}-{period.pk.hex[:12]}',
            clinic_name=period.clinic.name, lines=snapshots, base_amount=base,
            express_surcharge=extra, total_amount=base + extra, issued_by=actor)
        with prescription_audit_context(actor, 'Monthly closing', {'role': 'COMPTABILITE', 'action': 'ISSUE_INVOICE'}):
            for line in included:
                source = Prescription.objects.select_for_update().get(pk=line.prescription_id)
                source.billing_stage = 'FACTURE'
                source.save(update_fields=['billing_stage', 'updated_at'])
                WorkflowEvent.objects.create(prescription=source, kind='INVOICE_ISSUED', changed_by=actor,
                    payload={'invoice_id': str(invoice.pk), 'number': invoice.number, 'period': period.month.isoformat()})
        period.closed_at, period.closed_by = timezone.now(), actor
        period.save(update_fields=['closed_at', 'closed_by'])
        enqueue_event(included[0].prescription, 'CATALOG', f'closed:{period.pk}')
        return invoice


def adjust_statement_line(line_id, *, contested, excluded, reason, actor):
    initial = StatementLine.objects.select_related('period').get(pk=line_id)
    with transaction.atomic():
        billing_lock(initial.period.clinic_id)
        line = StatementLine.objects.select_for_update().select_related('period', 'prescription').get(pk=line_id)
        if line.period.closed_at:
            raise ValidationError('Issued statements require a credit note, not a line edit.')
        if type(contested) is not bool or type(excluded) is not bool or not reason.strip():
            raise ValidationError('Supply explicit contested/excluded flags and an adjustment reason.')
        line.contested, line.excluded, line.dispute_reason = contested, excluded, reason
        line.save(update_fields=['contested', 'excluded', 'dispute_reason'])
        WorkflowEvent.objects.create(prescription=line.prescription, kind='STATEMENT_ADJUSTED', changed_by=actor,
            payload={'line_id': str(line.pk), 'contested': contested, 'excluded': excluded, 'reason': reason})
        enqueue_event(line.prescription, 'CATALOG', f'adjusted:{line.pk}:{uuid.uuid4()}')
        return line


def issue_credit(invoice_id, prescription_id, amount, reason, actor, idempotency_key):
    with transaction.atomic():
        invoice = FinanceInvoice.objects.select_for_update().get(pk=invoice_id)
        existing = CreditNote.objects.filter(idempotency_key=idempotency_key).first()
        amount = Decimal(str(amount))
        if existing:
            if existing.invoice_id != invoice.pk or str(existing.prescription_id) != str(prescription_id) or existing.amount != amount or existing.reason != reason:
                raise ValidationError('Credit idempotency key belongs to another adjustment.')
            return existing
        line = next((row for row in invoice.lines if row['case_id'] == str(prescription_id)), None)
        if line is None or not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal('0.01')) or not reason.strip():
            raise ValidationError('Choose an invoiced case, positive cent-precise amount and reason.')
        previous = CreditNote.objects.filter(invoice=invoice, prescription_id=prescription_id).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        if previous + amount > Decimal(line['total_amount']):
            raise ValidationError('Credits cannot exceed the original invoiced case amount.')
        credit = CreditNote.objects.create(invoice=invoice, prescription_id=prescription_id, amount=amount,
                                           reason=reason, issued_by=actor, idempotency_key=idempotency_key)
        source = Prescription.objects.get(pk=prescription_id)
        event = enqueue_event(source, 'CREDIT', f'credit:{credit.pk}')
        event.payload = {'credit_id': str(credit.pk)}
        event.save(update_fields=['payload'])
        enqueue_event(source, 'CATALOG', f'credit-catalog:{credit.pk}')
        WorkflowEvent.objects.create(prescription=source, kind='CREDIT_ISSUED', changed_by=actor,
                                     payload={'credit_id': str(credit.pk), 'amount': str(amount), 'reason': reason})
        from .case_commands import notify
        notify(source, 'CREDIT_ISSUED', {'credit_id': str(credit.pk), 'amount': str(amount)})
        return credit
