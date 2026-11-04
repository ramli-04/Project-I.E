import logging
from datetime import timedelta

from celery import shared_task, Task
from django.db import DatabaseError, transaction
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, get_tenant_model, schema_context, tenant_context

from .analytics import refresh_billing_catalog
from .models import InvoiceArtifact, InvoiceDispatchLog, Prescription, TaskOutbox

logger = logging.getLogger(__name__)


class DurableTenantTask(Task):
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        if args and kwargs.get('outbox_id'):
            try:
                tenant = active_tenant(args[0])
                with tenant_context(tenant), transaction.atomic():
                    event = TaskOutbox.objects.select_for_update().filter(pk=kwargs['outbox_id'], processed_at__isnull=True).first()
                    if event:
                        event.last_error = f'{type(exc).__name__}: worker execution failed; inspect worker logs.'
                        if event.attempts >= 5:
                            event.failed_at = timezone.now()
                        event.save(update_fields=['last_error', 'failed_at'])
            except Exception:
                logger.exception('Could not persist failed event status')
        return super().on_failure(exc, task_id, args, kwargs, einfo)


@shared_task(bind=True, max_retries=3, soft_time_limit=270, time_limit=300)
def refresh_tenant_billing_catalog_task(self, schema_name):
    try:
        return refresh_billing_catalog(schema_name)
    except DatabaseError as exc:
        logger.exception('Billing catalog refresh failed for tenant %s', schema_name)
        raise self.retry(exc=exc, countdown=60)


@shared_task
def refresh_monthly_billing_catalog_task():
    with schema_context(get_public_schema_name()):
        schemas = list(get_tenant_model().objects.filter(is_active=True).exclude(
            schema_name=get_public_schema_name(),
        ).values_list('schema_name', flat=True))
    queued, failed = [], []
    for schema_name in schemas:
        try:
            refresh_tenant_billing_catalog_task.apply_async(args=[schema_name], expires=840)
            queued.append(schema_name)
        except Exception:
            logger.exception('Could not queue billing refresh for tenant %s', schema_name)
            failed.append(schema_name)
    return {'queued': queued, 'failed': failed}


def active_tenant(schema_name):
    if schema_name == get_public_schema_name():
        raise ValueError('Operational tasks cannot use the public schema.')
    with schema_context(get_public_schema_name()):
        tenant = get_tenant_model().objects.filter(schema_name=schema_name, is_active=True).first()
    if tenant is None:
        raise ValueError('Unknown or inactive laboratory.')
    return tenant


def locked_event(outbox_id, prescription_id, event_type):
    if outbox_id is None:
        return None
    return TaskOutbox.objects.select_for_update().get(
        pk=outbox_id, prescription_id=prescription_id, event_type=event_type,
    )


def complete_event(event):
    if event and not event.processed_at:
        event.processed_at = timezone.now()
        event.last_error = ''
        event.save(update_fields=['processed_at', 'last_error'])


@shared_task(base=DurableTenantTask, autoretry_for=(DatabaseError,), retry_backoff=True, max_retries=3,
             acks_late=True, reject_on_worker_lost=True, soft_time_limit=50, time_limit=60)
def calculate_automatic_calendar_task(tenant_schema_name, prescription_id, outbox_id=None):
    tenant = active_tenant(tenant_schema_name)
    with tenant_context(tenant), transaction.atomic():
        event = locked_event(outbox_id, prescription_id, 'CALENDAR')
        if event and event.processed_at:
            return {'status': 'already_processed'}
        order = Prescription.objects.select_for_update().get(pk=prescription_id)
        from zoneinfo import ZoneInfo
        days = {'STANDARD': 4, 'EXPRESS': 2, 'NEXT_DAY': 1}[order.delivery_service]
        if order.is_fast_track and order.delivery_service == 'STANDARD':
            days = 2
        deadline_at = timezone.localtime(order.created_at, ZoneInfo('Africa/Casablanca')) + timedelta(days=days)
        deadline_at += timedelta(seconds=order.deadline_suspended_seconds)
        deadline = timezone.localdate(deadline_at)
        if order.automatic_deadline != deadline or order.deadline_calculated_at is None or order.deadline_at != deadline_at:
            order.automatic_deadline = deadline
            order.deadline_calculated_at = timezone.now()
            order.deadline_at = deadline_at
            order.save(update_fields=['automatic_deadline', 'deadline_calculated_at', 'deadline_at', 'updated_at'])
        complete_event(event)
        return {'status': 'calculated', 'deadline': deadline.isoformat()}


@shared_task(base=DurableTenantTask, autoretry_for=(DatabaseError,), retry_backoff=True, max_retries=3,
             acks_late=True, reject_on_worker_lost=True, soft_time_limit=50, time_limit=60)
def generate_invoice_pdf_task(tenant_schema_name, prescription_id, outbox_id=None):
    """Generate a real immutable monthly PDF; queue configured external delivery separately."""
    tenant = active_tenant(tenant_schema_name)
    with tenant_context(tenant), transaction.atomic():
        event = locked_event(outbox_id, prescription_id, 'INVOICE')
        order = Prescription.objects.select_for_update().get(pk=prescription_id)
        if order.invoiced_at is None or order.invoiced_amount is None:
            raise ValueError('A confirmed invoice snapshot is required.')
        from .models import FinanceInvoice, InvoiceDocument
        from .documents import pdf_document, save_bytes
        line = getattr(order, 'statement_line', None)
        if line is None:
            raise ValueError('Reconcile the legacy invoice with a verified monthly statement before PDF generation.')
        invoice = FinanceInvoice.objects.select_for_update().get(period=line.period)
        document = InvoiceDocument.objects.filter(invoice=invoice).first()
        if document is None:
            rows = [['Cas', 'Base MAD', 'Urgence MAD', 'Total MAD']] + [
                [row['patient_ref'], row['base_amount'], row['express_surcharge'], row['total_amount']] for row in invoice.lines]
            content = pdf_document('Facture ' + invoice.number, [invoice.clinic_name,
                f'Periode de livraison: {invoice.period.month:%Y-%m}', rows, f'Total: {invoice.total_amount} MAD'])
            stored, digest = save_bytes('invoices', invoice.pk.hex + '.pdf', content)
            document = InvoiceDocument.objects.create(invoice=invoice, storage_name=stored, sha256=digest)
        artifact, _ = InvoiceArtifact.objects.get_or_create(prescription=order, defaults={
            'status': 'PDF_READY', 'mock_reference': '', 'storage_name': document.storage_name, 'sha256': document.sha256,
            'snapshot': {'prescription_id': str(order.pk), 'amount': str(order.invoiced_amount),
                         'clinic': order.invoiced_clinic_name, 'currency': 'MAD',
                         'invoiced_at': order.invoiced_at.isoformat()},
        })
        from .case_commands import notify
        notify(order, 'INVOICE_READY', {'invoice_id': str(invoice.pk), 'number': invoice.number}, key=f'invoice-ready:{invoice.pk}')
        for channel in ('EMAIL', 'WHATSAPP'):
            InvoiceDispatchLog.objects.get_or_create(artifact=artifact, channel=channel, defaults={'status': 'QUEUED'})
        complete_event(event)
        return {'status': 'PDF_READY', 'invoice_id': str(invoice.pk), 'dispatch': 'QUEUED'}


@shared_task(soft_time_limit=50, time_limit=60)
def publish_tenant_outbox_task(schema_name):
    tenant = active_tenant(schema_name)
    from .outbox import publish_event
    with tenant_context(tenant):
        ids = list(TaskOutbox.objects.filter(processed_at__isnull=True, failed_at__isnull=True, next_attempt_at__lte=timezone.now())
                   .order_by('next_attempt_at', 'pk').values_list('pk', flat=True)[:100])
    return {'published': sum(publish_event(schema_name, event_id) for event_id in ids)}


@shared_task
def recover_pending_outbox_task():
    with schema_context(get_public_schema_name()):
        schemas = list(get_tenant_model().objects.filter(is_active=True)
                       .exclude(schema_name=get_public_schema_name()).values_list('schema_name', flat=True))
    for schema_name in schemas:
        try:
            publish_tenant_outbox_task.apply_async(args=[schema_name], expires=55, retry=False)
            deliver_pending_messages_task.apply_async(args=[schema_name], expires=55, retry=False)
        except Exception:
            logger.exception('Could not queue outbox recovery for schema %s', schema_name)
    return {'tenants': len(schemas)}


@shared_task(autoretry_for=(DatabaseError,), retry_backoff=True, max_retries=3, acks_late=True)
def invalidate_active_orders_task(tenant_schema_name, prescription_id, outbox_id=None):
    from django.core.cache import cache
    from redis.exceptions import RedisError
    tenant = active_tenant(tenant_schema_name)
    with tenant_context(tenant), transaction.atomic():
        event = locked_event(outbox_id, prescription_id, 'CACHE')
        try:
            cache.delete('active_orders')
        except (RedisError, OSError):
            if event:
                event.last_error = 'Redis invalidation unavailable; version checks still prevent stale reads.'
                event.save(update_fields=['last_error'])
            return {'status': 'pending'}
        complete_event(event)
        return {'status': 'invalidated'}


@shared_task(base=DurableTenantTask, autoretry_for=(DatabaseError,), retry_backoff=True, max_retries=3, acks_late=True)
def refresh_case_catalog_task(tenant_schema_name, prescription_id, outbox_id=None):
    tenant = active_tenant(tenant_schema_name)
    with tenant_context(tenant), transaction.atomic():
        event = locked_event(outbox_id, prescription_id, 'CATALOG')
        result = refresh_billing_catalog(tenant_schema_name)
        if result.get('status') == 'refreshed':
            complete_event(event)
        return result


@shared_task(base=DurableTenantTask, autoretry_for=(DatabaseError,), retry_backoff=True, max_retries=3, acks_late=True)
def generate_credit_note_pdf_task(tenant_schema_name, prescription_id, outbox_id=None):
    tenant = active_tenant(tenant_schema_name)
    from .models import CreditNote, CreditDocument
    from .documents import pdf_document, save_bytes
    with tenant_context(tenant), transaction.atomic():
        event = locked_event(outbox_id, prescription_id, 'CREDIT')
        if event is None:
            raise ValueError('A durable credit event is required.')
        credit = CreditNote.objects.select_for_update().get(pk=event.payload['credit_id'], prescription_id=prescription_id)
        document = CreditDocument.objects.filter(credit_note=credit).first()
        if document is None:
            content = pdf_document('Avoir ' + credit.pk.hex[:12], [f'Facture: {credit.invoice.number}',
                f'Cas: {credit.prescription.patient_ref}', credit.reason, f'Montant credite: {credit.amount} MAD'])
            stored, digest = save_bytes('credits', credit.pk.hex + '.pdf', content)
            document = CreditDocument.objects.create(credit_note=credit, storage_name=stored, sha256=digest)
        from .case_commands import notify
        notify(credit.prescription, 'CREDIT_READY', {'credit_id': str(credit.pk)}, key=f'credit-ready:{credit.pk}')
        complete_event(event)
        return {'status': 'PDF_READY', 'credit_id': str(credit.pk)}


@shared_task(soft_time_limit=50, time_limit=60)
def deliver_pending_messages_task(tenant_schema_name):
    tenant = active_tenant(tenant_schema_name)
    with tenant_context(tenant):
        from .messaging import deliver_pending
        return deliver_pending()
