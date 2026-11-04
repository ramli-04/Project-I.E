from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.test import APIClient

from .models import Prescription, PrescriptionHistory
from .signals import prescription_audit_context


@override_settings(OUTBOX_PUBLISH_ON_COMMIT=False, CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'cqrs-test-cache',
        'KEY_PREFIX': 'cabinet',
        'KEY_FUNCTION': 'django_tenants.cache.make_key',
    },
})
class PrescriptionCQRSTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = 'CQRS laboratory'

    def setUp(self):
        connection.set_tenant(self.tenant)
        cache.clear()
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())

    def create_order(self, **changes):
        return Prescription.objects.create(
            patient_ref='CQRS-001', dentist_name='Clinic', tooth_number=11,
            shade='A2', material='Zircone', disinfected=True, **changes,
        )

    def test_creation_and_real_transitions_append_audit_records(self):
        with prescription_audit_context('user:42:Mohamed', 'Initial case'):
            order = self.create_order()
        initial = order.audit_history.get()
        self.assertEqual(initial.previous_status, '')
        self.assertEqual(initial.new_status, 'DEMANDE_RECUE')
        self.assertEqual(initial.changed_by, 'user:42:Mohamed')
        self.assertEqual(initial.action_notes, 'Initial case')
        with prescription_audit_context('user:42:Mohamed', 'Review started'):
            order.status = 'ANALYSE_DEMANDE'
            order.save(update_fields=['status'])
        event = order.audit_history.last()
        self.assertEqual(event.previous_status, 'DEMANDE_RECUE')
        self.assertEqual(event.new_status, 'ANALYSE_DEMANDE')
        self.assertEqual(event.action_notes, 'Review started')
        order.save()
        self.assertEqual(order.audit_history.count(), 2)

    def test_unsaved_status_is_not_logged_with_unrelated_update_fields(self):
        order = self.create_order()
        order.status = 'ANALYSE_DEMANDE'
        order.technical_notes = 'Only notes are persisted'
        order.save(update_fields=['technical_notes'])
        order.refresh_from_db()
        self.assertEqual(order.status, 'DEMANDE_RECUE')
        self.assertEqual(order.audit_history.count(), 1)

    def test_failed_audit_insert_rolls_back_status_write(self):
        order = self.create_order()
        order.status = 'ANALYSE_DEMANDE'
        with patch('api.signals.PrescriptionHistory.objects.using') as manager:
            manager.return_value.create.side_effect = IntegrityError('Audit unavailable')
            with self.assertRaises(IntegrityError):
                order.save()
        order.refresh_from_db()
        self.assertEqual(order.status, 'DEMANDE_RECUE')
        self.assertEqual(order.audit_history.count(), 1)

    def test_cache_invalidation_waits_for_commit_and_restores_tenant(self):
        cache.set('active_orders', ['tenant snapshot'])
        with schema_context('public'):
            cache.set('active_orders', ['public snapshot'])
        with self.captureOnCommitCallbacks(execute=True):
            self.create_order()
            self.assertEqual(cache.get('active_orders'), ['tenant snapshot'])
            connection.set_schema_to_public()
        self.assertEqual(cache.get('active_orders'), ['public snapshot'])
        connection.set_tenant(self.tenant)
        self.assertIsNone(cache.get('active_orders'))

    def test_rollback_preserves_cache_and_history(self):
        order = self.create_order()
        cache.set('active_orders', ['old snapshot'])
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    order.status = 'ANALYSE_DEMANDE'
                    order.save()
                    raise RuntimeError('Rollback')
        self.assertEqual(callbacks, [])
        self.assertEqual(cache.get('active_orders'), ['old snapshot'])
        order.refresh_from_db()
        self.assertEqual(order.status, 'DEMANDE_RECUE')
        self.assertEqual(order.audit_history.count(), 1)

    def test_list_caches_active_orders_and_retains_optional_completed_orders(self):
        active = self.create_order()
        completed = self.create_order()
        completed.status = 'LIVRE'
        completed.save()
        first = self.client.get('/api/prescriptions/')
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual([str(row['id']) for row in first.data], [str(active.pk)])
        with CaptureQueriesContext(connection) as queries:
            second = self.client.get('/api/prescriptions/')
        self.assertEqual(second.data, first.data)
        self.assertFalse(any('FROM "api_prescription"' in query['sql'] for query in queries))
        all_orders = self.client.get('/api/prescriptions/?include_completed=true')
        self.assertEqual(len(all_orders.data), 2)
        with self.captureOnCommitCallbacks(execute=True):
            active.status = 'LIVRE'
            active.save()
        self.assertEqual(self.client.get('/api/prescriptions/').data, [])
        self.assertEqual(cache.get('active_orders'), [])

    def test_non_status_writes_refresh_serialized_cache(self):
        order = self.create_order()
        self.client.get('/api/prescriptions/')
        with self.captureOnCommitCallbacks(execute=True):
            order.total_price = 900
            order.save(update_fields=['total_price'])
        self.assertEqual(self.client.get('/api/prescriptions/').data[0]['total_price'], 900)
        self.assertEqual(order.audit_history.count(), 1)

    def test_history_and_prescriptions_are_protected_from_destructive_writes(self):
        order = self.create_order()
        event = order.audit_history.get()
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()
        with self.assertRaises(ValidationError):
            PrescriptionHistory.objects.filter(pk=event.pk).update(action_notes='Tamper')
        with self.assertRaises(ValidationError):
            PrescriptionHistory.objects.filter(pk=event.pk).delete()
        with self.assertRaises(ProtectedError):
            order.delete()
        self.assertEqual(self.client.delete(f'/api/prescriptions/{order.pk}/').status_code, 400)
        with self.assertRaises(ValidationError):
            Prescription.objects.filter(pk=order.pk).update(status='LIVRE')
        with self.assertRaises(ValidationError):
            Prescription.objects.bulk_create([Prescription()])
        for statement in [
            'UPDATE api_prescriptionhistory SET action_notes = %s',
            'DELETE FROM api_prescriptionhistory WHERE action_notes = %s',
        ]:
            with self.assertRaises(DatabaseError):
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(statement, ['tamper'])
        self.assertEqual(order.audit_history.count(), 1)

    def test_serializer_accepts_audit_notes_without_exposing_audit_actor_override(self):
        order = self.create_order(accepted=True)
        response = self.client.patch(f'/api/prescriptions/{order.pk}/', {
            'status': 'ANALYSE_DEMANDE', 'action_notes': 'Rework review', 'changed_by': 'spoofed',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        event = order.audit_history.last()
        self.assertEqual(event.action_notes, 'Rework review')
        self.assertEqual(event.changed_by, 'anonymous')
        self.assertNotIn('action_notes', response.data)

    def test_cache_failure_does_not_abort_audited_writes_or_database_reads(self):
        with patch('api.views.cache.get', side_effect=RedisConnectionError('offline')), \
                patch('api.views.cache.set', side_effect=RedisConnectionError('offline')):
            with self.assertLogs('api.views', level='WARNING'):
                self.assertEqual(self.client.get('/api/prescriptions/').status_code, 200)
        with patch('api.signals.cache.delete', side_effect=RedisConnectionError('offline')):
            with self.assertLogs('api.signals', level='ERROR'):
                with self.captureOnCommitCallbacks(execute=True):
                    order = self.create_order()
        self.assertEqual(order.audit_history.count(), 1)
