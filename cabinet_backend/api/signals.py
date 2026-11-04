import logging
import uuid
from contextlib import contextmanager
from contextvars import ContextVar

from django.core.cache import cache
from django.db import connections, transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django_tenants.utils import schema_context
from redis.exceptions import RedisError

from .models import Prescription, PrescriptionHistory

logger = logging.getLogger(__name__)
_audit_details = ContextVar('prescription_audit_details', default=('system', ''))
_workflow_metadata = ContextVar('workflow_metadata', default={})


@contextmanager
def prescription_audit_context(changed_by='system', action_notes='', metadata=None):
    token = _audit_details.set((changed_by, action_notes))
    details_token = _workflow_metadata.set(dict(metadata or {}))
    try:
        yield
    finally:
        _audit_details.reset(token)
        _workflow_metadata.reset(details_token)


def invalidate_active_orders_after_commit(using):
    schema_name = connections[using].schema_name

    def invalidate():
        # An outer schema_context may have exited before the commit callback.
        with schema_context(schema_name, database=using):
            try:
                cache.delete('active_orders')
            except (RedisError, OSError):
                logger.exception('Active-order cache invalidation failed for schema %s', schema_name)

    transaction.on_commit(invalidate, using=using)


@receiver(pre_save, sender=Prescription, dispatch_uid='prescription_capture_previous_status')
def capture_previous_status(sender, instance, raw, using, **kwargs):
    if raw:
        return
    instance._previous_status = None
    if not instance._state.adding:
        # Prescription.save() opens the transaction before pre_save is emitted.
        instance._previous_status = (
            sender.objects.using(using).select_for_update()
            .filter(pk=instance.pk).values_list('status', flat=True).first()
        )
    instance._previous_invoice = None
    instance._previous_fast_track = None
    if not instance._state.adding:
        prior = sender.objects.using(using).filter(pk=instance.pk).values('invoiced_at', 'is_fast_track', 'delivery_service', 'deadline_suspended_seconds').first()
        if prior:
            instance._previous_invoice = prior['invoiced_at']
            instance._previous_fast_track = prior['is_fast_track']
            instance._previous_calendar_inputs = (prior['delivery_service'], prior['deadline_suspended_seconds'])


@receiver(post_save, sender=Prescription, dispatch_uid='prescription_append_history')
def record_prescription_change(sender, instance, created, raw, using, update_fields, **kwargs):
    if raw:
        return
    previous = getattr(instance, '_previous_status', None)
    status_written = update_fields is None or 'status' in update_fields
    if created or (status_written and previous != instance.status):
        changed_by, notes = _audit_details.get()
        history = PrescriptionHistory.objects.using(using).create(
            prescription_id=instance.pk,
            previous_status=previous or '',
            new_status=instance.status,
            action_notes=notes,
            changed_by=changed_by,
            source_version=instance.state_version,
            metadata=_workflow_metadata.get(),
        )
        if hasattr(history, '_new_production_attempt'):
            instance.production_attempt = history._new_production_attempt
            instance.quality_validated = False
    from .outbox import enqueue_event
    if created:
        enqueue_event(instance, 'CALENDAR', f'calendar:{instance.pk}', using=using)
    elif (update_fields is None or 'is_fast_track' in update_fields or 'delivery_service' in update_fields or 'deadline_suspended_seconds' in update_fields) and (
        instance.is_fast_track != instance._previous_fast_track or getattr(instance, '_previous_calendar_inputs', None) != (instance.delivery_service, instance.deadline_suspended_seconds)
    ):
        enqueue_event(instance, 'CALENDAR', f'calendar:{instance.pk}:{uuid.uuid4()}', using=using)
    if instance.invoiced_at and not getattr(instance, '_previous_invoice', None):
        enqueue_event(instance, 'INVOICE', f'invoice:{instance.pk}', using=using)
    enqueue_event(instance, 'CACHE', f'cache:{instance.pk}:{uuid.uuid4()}', using=using)
    from .models import WorkflowEvent
    changed_by, notes = _audit_details.get()
    WorkflowEvent.objects.using(using).create(
        prescription_id=instance.pk, kind='CREATED' if created else 'UPDATED', changed_by=changed_by,
        payload={'fields': sorted(update_fields) if update_fields else ['source'], 'notes': notes,
                 'state_version': instance.state_version, 'action': _workflow_metadata.get().get('action', 'SAVE')},
    )
    # Also refresh after non-status writes: billing, pause, acceptance, etc.
    invalidate_active_orders_after_commit(using)


@receiver(post_delete, sender=Prescription, dispatch_uid='prescription_delete_invalidate_cache')
def invalidate_deleted_prescription(sender, using, **kwargs):
    invalidate_active_orders_after_commit(using)


@receiver(post_save, sender=PrescriptionHistory, dispatch_uid='prescription_rework_material_loss')
def record_rework_loss(sender, instance, created, raw, using, **kwargs):
    if created and not raw and instance.new_status in {'A_REFAIRE', 'RECOULER', 'RESCANNER'}:
        from .inventory import classify_rework
        instance._new_production_attempt = classify_rework(instance, using=using)
