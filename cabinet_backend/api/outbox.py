"""Durable source events; Redis outages cannot lose committed business work."""
import logging
from datetime import timedelta

from celery import current_app
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from django_tenants.utils import schema_context

from .models import TaskOutbox

logger = logging.getLogger(__name__)
TASKS = {
    'CALENDAR': 'api.tasks.calculate_automatic_calendar_task',
    'INVOICE': 'api.tasks.generate_invoice_pdf_task',
    'CACHE': 'api.tasks.invalidate_active_orders_task',
    'CREDIT': 'api.tasks.generate_credit_note_pdf_task',
    'CATALOG': 'api.tasks.refresh_case_catalog_task',
}


def enqueue_event(order, event_type, event_key, using='default'):
    event, created = TaskOutbox.objects.using(using).get_or_create(
        event_key=event_key, defaults={'event_type': event_type, 'prescription': order},
    )
    if created and getattr(settings, 'OUTBOX_PUBLISH_ON_COMMIT', True):
        schema = connection.schema_name
        transaction.on_commit(lambda: publish_event(schema, event.pk), using=using)
    return event


def publish_event(schema, event_id):
    try:
        with schema_context(schema), transaction.atomic():
            event = TaskOutbox.objects.select_for_update().get(pk=event_id)
            now = timezone.now()
            if event.processed_at or event.failed_at or event.next_attempt_at > now:
                return False
            event.attempts += 1
            try:
                current_app.send_task(
                    TASKS[event.event_type], args=[schema, str(event.prescription_id)],
                    kwargs={'outbox_id': str(event.pk)}, task_id=str(event.pk), retry=False, ignore_result=True,
                )
            except Exception as exc:
                event.last_error = f'{type(exc).__name__}: broker publication failed'
                event.next_attempt_at = now + timedelta(seconds=min(300, 15 * event.attempts))
                logger.exception('Outbox publication failed: schema=%s event=%s', schema, event_id)
            else:
                event.published_at = now
                event.next_attempt_at = now + timedelta(minutes=5)
                event.last_error = ''
            event.save(update_fields=['attempts', 'last_error', 'published_at', 'next_attempt_at'])
            return not event.last_error
    except Exception:
        # Commit already succeeded; periodic recovery will retry the durable event.
        logger.exception('Outbox callback failed: schema=%s event=%s', schema, event_id)
        return False
