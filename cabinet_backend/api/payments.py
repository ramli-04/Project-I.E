"""Append-only payment evidence and one live invoice balance calculation."""
import hashlib
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from .billing import billing_lock
from .models import (CreditNote, FinanceInvoice, Payment, PaymentAllocation, PaymentReversal,
                     StatementLine, WorkflowEvent)
from .workflow_spec import Action

TZ = ZoneInfo('Africa/Casablanca')
ZERO = Decimal('0.00')


class PaymentConflict(ValidationError):
    pass


def invoice_balances(invoices, today=None):
    """Constant-query summaries; never rewrite an invoice, PDF or financial catalog."""
    invoices = list(invoices)
    if not invoices:
        return {}
    today = today or timezone.localdate(timezone.now(), TZ)
    ids = [invoice.pk for invoice in invoices]
    clinics = {row['id']: row for row in FinanceInvoice.objects.filter(pk__in=ids)
               .values('id', 'period__clinic_id', 'period__clinic__payment_terms_days')}
    credits = dict(CreditNote.objects.filter(invoice_id__in=ids).values('invoice_id')
                   .annotate(total=Sum('amount')).values_list('invoice_id', 'total'))
    paid = dict(PaymentAllocation.objects.filter(invoice_id__in=ids, payment__reversal__isnull=True)
                .values('invoice_id').annotate(total=Sum('amount')).values_list('invoice_id', 'total'))
    result = {}
    for invoice in invoices:
        details = clinics[invoice.pk]
        net = invoice.total_amount - credits.get(invoice.pk, ZERO)
        allocated = paid.get(invoice.pk, ZERO)
        balance = net - allocated
        status = 'TROP_PERCU' if balance < ZERO else 'PAYEE' if balance == ZERO else 'PARTIELLE' if allocated > ZERO else 'IMPAYEE'
        terms = details['period__clinic__payment_terms_days']
        due = invoice.issued_at.astimezone(TZ).date() + timedelta(days=terms)
        result[invoice.pk] = {'clinic': details['period__clinic_id'], 'terms_days': terms,
            'paid_amount': allocated, 'credited_amount': credits.get(invoice.pk, ZERO), 'balance': balance,
            'payment_status': status, 'due_date': due, 'days_overdue': max(0, (today-due).days)}
    return result


def receivables(today=None):
    today = today or timezone.localdate(timezone.now(), TZ)
    invoices = list(FinanceInvoice.objects.all())
    summaries = invoice_balances(invoices, today)
    rows = {}
    for invoice in invoices:
        data = summaries[invoice.pk]
        row = rows.setdefault(data['clinic'], {'clinic': data['clinic'], 'terms_days': data['terms_days'],
            'total_due': ZERO, 'not_due': ZERO, 'overpaid_amount': ZERO,
            'buckets': {key: ZERO for key in ['0_30', '31_60', '61_90', '90_plus']}, 'oldest_overdue_days': 0})
        balance = data['balance']
        if balance < ZERO:
            row['overpaid_amount'] -= balance
        elif balance > ZERO:
            row['total_due'] += balance
            if data['due_date'] >= today:
                row['not_due'] += balance
            else:
                days = data['days_overdue']
                bucket = '0_30' if days <= 30 else '31_60' if days <= 60 else '61_90' if days <= 90 else '90_plus'
                row['buckets'][bucket] += balance
                row['oldest_overdue_days'] = max(row['oldest_overdue_days'], days)
    return sorted(rows.values(), key=lambda row: (-row['oldest_overdue_days'], row['clinic']))


def _key(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError('A UUID Idempotency-Key is required.') from exc


def _replay(key, digest):
    existing = Payment.objects.filter(idempotency_key=key).first()
    if existing and existing.payload_digest != digest:
        raise PaymentConflict('Payment idempotency key belongs to a different submission.')
    return existing


def _audit(payment, invoices, actor, action):
    # Immutable financial annotations only; source versions and clinical state stay unchanged.
    case_ids = {line['case_id'] for invoice in invoices for line in invoice.lines}
    for source_id in sorted(case_ids):
        WorkflowEvent.objects.create(prescription_id=source_id, changed_by=actor, kind=action,
            payload={'action': action, 'payment_id': str(payment.pk), 'amount': str(payment.amount),
                     'invoice_ids': [str(invoice.pk) for invoice in invoices]})


def record_payment(payload, actor, idempotency_key):
    from .payment_serializers import PaymentInput
    key = _key(idempotency_key)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, separators=(',', ':')).encode()).hexdigest()
    existing = _replay(key, digest)
    if existing:
        return existing
    serializer = PaymentInput(data=payload)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data.copy()
    allocations = values.pop('allocations')
    if len({item['invoice'].pk for item in allocations}) != len(allocations):
        raise ValidationError('Choose distinct invoices for the payment.')
    if sum((item['amount'] for item in allocations), ZERO) != values['amount']:
        raise ValidationError('Payment allocations must equal the payment amount.')
    with transaction.atomic():
        billing_lock(values['clinic'].pk)
        invoices = list(FinanceInvoice.objects.select_for_update(of=('self',))
            .select_related('period').filter(pk__in=[item['invoice'].pk for item in allocations]).order_by('pk'))
        existing = _replay(key, digest)
        if existing:
            return existing
        if len(invoices) != len(allocations) or any(invoice.period.clinic_id != values['clinic'].pk for invoice in invoices):
            raise ValidationError('Allocate only invoices belonging to this clinic.')
        balances = invoice_balances(invoices)
        for item in allocations:
            if item['amount'] > balances[item['invoice'].pk]['balance']:
                raise ValidationError('Payment allocation exceeds the invoice balance.')
        try:
            with transaction.atomic():
                payment = Payment.objects.create(**values, recorded_by=actor, idempotency_key=key, payload_digest=digest)
                for item in allocations:
                    PaymentAllocation.objects.create(payment=payment, **item)
                _audit(payment, invoices, actor, Action.RECORD_PAYMENT)
        except IntegrityError:
            # A different clinic may race on the tenant-wide unique request key.
            existing = _replay(key, digest)
            if existing:
                return existing
            raise
        return payment


def reverse_payment(payment_id, reason, notes, actor):
    initial = Payment.objects.get(pk=payment_id)
    if not isinstance(reason, str) or reason not in {'IMPAYE', 'ANNULE'}:
        raise ValidationError('Choose a payment reversal reason.')
    if reason == 'IMPAYE' and initial.method not in {'CHEQUE', 'LCN'}:
        raise ValidationError('Only cheque or LCN payments can be marked unpaid.')
    with transaction.atomic():
        billing_lock(initial.clinic_id)
        invoices = list(FinanceInvoice.objects.select_for_update(of=('self',))
            .filter(allocations__payment_id=payment_id).order_by('pk'))
        payment = Payment.objects.select_for_update().get(pk=payment_id)
        if PaymentReversal.objects.filter(payment=payment).exists():
            raise ValidationError('Payment has already been reversed.')
        reversal = PaymentReversal.objects.create(payment=payment, reason=reason, notes=notes, reversed_by=actor)
        _audit(payment, invoices, actor, Action.REVERSE_PAYMENT)
        return reversal
