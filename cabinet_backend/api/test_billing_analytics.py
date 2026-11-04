from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from importlib import import_module
from unittest.mock import patch
import psycopg2

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from customers.models import Client, PlatformAccount
from .analytics import PIPELINE, refresh_billing_catalog
from .models import AnalyticsRefreshState, MonthlyBillingCatalog, MonthlyBillingSummary, PartnerClinic, Prescription
from .tasks import refresh_monthly_billing_catalog_task, refresh_tenant_billing_catalog_task


class BillingAnalyticsTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = 'Analytics laboratory'

    def setUp(self):
        connection.set_tenant(self.tenant)
        with schema_context('public'):
            self.manager = get_user_model().objects.create_user(username='analytics-manager', is_superuser=True)
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.client.force_authenticate(user=self.manager)
        self.clinic = PartnerClinic.objects.create(name='Clinic A', pickup_address='12 Main Street', contact_phone='123')

    def order(self, **changes):
        payload = dict(patient_ref='ANALYTICS', dentist_name='Dentist', tooth_number=11, shade='A2', material='Zircone', disinfected=True, total_price=500, partner_clinic=self.clinic)
        return Prescription.objects.create(**{**payload, **changes})

    def invoice(self, order):
        order.billing_stage = 'FACTURE'
        order.save(update_fields=['billing_stage'])
        return order

    def refresh(self):
        return refresh_billing_catalog(self.tenant.schema_name)

    def test_invoice_timestamp_amount_and_clinic_snapshot_are_immutable(self):
        order = self.invoice(self.order())
        self.assertIsNotNone(order.invoiced_at)
        self.assertEqual(order.invoiced_amount, Decimal('500'))
        self.assertEqual(order.invoiced_clinic_name, 'Clinic A')
        initial_date = order.invoiced_at
        order.technical_notes = 'Unrelated edit'
        order.save(update_fields=['technical_notes'])
        order.refresh_from_db()
        self.assertEqual(order.invoiced_at, initial_date)
        self.clinic.name = 'Renamed clinic'
        self.clinic.save()
        self.assertEqual(order.invoiced_clinic_name, 'Clinic A')
        for field, value in [('total_price', 999), ('billing_stage', 'COMMANDE'), ('partner_clinic_id', None), ('invoiced_amount', Decimal('999'))]:
            with self.subTest(field=field):
                order.refresh_from_db()
                setattr(order, field, value)
                with self.assertRaises(ValidationError):
                    order.save()

    def test_invoice_uses_persisted_price_when_update_fields_excludes_price(self):
        order = self.order()
        order.total_price = 999
        self.invoice(order)
        order.refresh_from_db()
        self.assertEqual(order.total_price, 500)
        self.assertEqual(order.invoiced_amount, Decimal('500'))

    def test_catalog_preaggregates_history_without_multiplying_invoice_totals(self):
        order = self.order()
        order.status = 'ANALYSE_DEMANDE'
        order.save(update_fields=['status'])
        order.status = 'A_CONFIRMER'
        order.save(update_fields=['status'])
        self.invoice(order)
        self.invoice(self.order(total_price=700))
        self.invoice(self.order(partner_clinic=None, total_price=100))
        self.order(total_price=900)
        self.assertEqual(self.refresh()['status'], 'refreshed')
        self.assertEqual(MonthlyBillingCatalog.objects.count(), 4)
        detail = MonthlyBillingCatalog.objects.get(pk=order.pk)
        self.assertEqual(detail.audit_event_count, 3)
        self.assertEqual(detail.status_transition_count, 2)
        summary = MonthlyBillingSummary.objects.get(partner_clinic_id=self.clinic.pk)
        self.assertEqual(summary.invoice_count, 2)
        self.assertEqual(summary.invoiced_total, Decimal('1200'))
        self.assertEqual(summary.status_transition_count, 2)
        self.assertEqual(MonthlyBillingSummary.objects.get(partner_clinic_id__isnull=True).invoiced_total, Decimal('100'))
        self.assertIsNotNone(AnalyticsRefreshState.objects.get(pk=PIPELINE).last_success_at)

    def test_invoice_month_uses_casablanca_calendar(self):
        order = self.order()
        with patch('api.models.timezone.now', return_value=datetime(2026, 11, 30, 23, 30, tzinfo=dt_timezone.utc)):
            self.invoice(order)
        self.refresh()
        self.assertEqual(MonthlyBillingCatalog.objects.get(pk=order.pk).billing_month.isoformat(), '2026-12-01')

    def test_legacy_undated_invoices_are_flagged_not_assigned_invented_dates(self):
        order = self.order()
        # Simulate a record that pre-dates the timestamp migration.
        with connection.cursor() as cursor:
            cursor.execute("UPDATE api_prescription SET billing_stage = 'FACTURE' WHERE id = %s", [order.pk])
        order.refresh_from_db()
        order.technical_notes = 'Legacy notes'
        order.save(update_fields=['technical_notes'])
        self.assertIsNone(order.invoiced_at)
        self.refresh()
        self.assertTrue(MonthlyBillingCatalog.objects.get(pk=order.pk).legacy_invoice_without_date)
        self.assertEqual(MonthlyBillingSummary.objects.count(), 0)
        self.assertEqual(AnalyticsRefreshState.objects.get(pk=PIPELINE).undated_invoice_count, 1)

    def test_endpoint_uses_only_catalog_and_metadata_with_pagination_and_filters(self):
        order = self.invoice(self.order())
        self.refresh()
        month = MonthlyBillingSummary.objects.get().billing_month.strftime('%Y-%m')
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(f'/api/analytics/monthly-billing/?month={month}&clinic={self.clinic.pk}&page_size=1')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['invoiced_total'], '500.00')
        self.assertFalse(response.data['analytics']['stale'])
        analytics_queries = [q for q in queries if 'monthly_billing_summary' in q['sql']]
        self.assertGreaterEqual(len(analytics_queries), 2)
        self.assertTrue(all('GROUP BY' not in q['sql'].upper() for q in analytics_queries))
        self.assertTrue(all('JOIN' not in q['sql'].upper() for q in analytics_queries))
        self.assertTrue(all('FROM "api_prescription"' not in q['sql'] for q in queries))
        detail = self.client.get(f'/api/analytics/billing-catalog/{order.pk}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(self.client.post('/api/analytics/monthly-billing/', {}, format='json').status_code, 405)
        for query in ['month=bad', 'month=0000-01', 'clinic=-1', 'clinic=' + '9' * 30]:
            self.assertEqual(self.client.get('/api/analytics/monthly-billing/?' + query).status_code, 400)

    def test_anonymous_public_and_inactive_tenants_are_denied(self):
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get('/api/analytics/monthly-billing/').status_code, [401, 403])
        self.client.force_authenticate(user=self.manager)
        self.assertIn(self.client.get('/api/analytics/monthly-billing/', HTTP_HOST='localhost').status_code, [403, 404])
        with schema_context('public'):
            Client.objects.filter(pk=self.tenant.pk).update(is_active=False)
        self.assertEqual(self.client.get('/api/analytics/monthly-billing/').status_code, 403)
        self.assertEqual(self.refresh()['reason'], 'inactive_or_missing_tenant')
        self.assertEqual(refresh_billing_catalog('public')['reason'], 'public_schema')

    def test_tenant_catalogs_are_isolated(self):
        self.invoice(self.order())
        self.refresh()
        with schema_context('public'):
            other = Client.objects.create(schema_name='analytics_other', name='Other lab')
        try:
            with schema_context(other.schema_name):
                self.assertEqual(MonthlyBillingCatalog.objects.count(), 0)
                self.assertEqual(MonthlyBillingSummary.objects.count(), 0)
            self.assertEqual(MonthlyBillingCatalog.objects.count(), 1)
        finally:
            with schema_context('public'):
                with connection.cursor() as cursor:
                    cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
                other.delete(force_drop=True)

    def test_refresh_failure_is_recorded_without_destroying_previous_snapshot(self):
        self.invoice(self.order())
        self.refresh()
        original_success = AnalyticsRefreshState.objects.get(pk=PIPELINE).last_success_at
        with patch('api.analytics.MonthlyBillingCatalog.objects.filter', side_effect=DatabaseError('simulated failure')):
            with self.assertRaises(DatabaseError):
                self.refresh()
        state = AnalyticsRefreshState.objects.get(pk=PIPELINE)
        self.assertEqual(state.last_success_at, original_success)
        self.assertIn('simulated failure', state.last_error)
        response = self.client.get('/api/analytics/monthly-billing/')
        self.assertTrue(response.data['analytics']['refresh_failed'])
        self.assertEqual(response.data['count'], 1)

    def test_overlapping_refresh_is_skipped(self):
        other_connection = psycopg2.connect(**connection.get_connection_params())
        try:
            other_connection.autocommit = True
            with other_connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_lock(hashtextextended(%s, 0))', [f'cabinet:billing-refresh:{self.tenant.schema_name}'])
            self.assertEqual(self.refresh()['reason'], 'already_refreshing')
        finally:
            other_connection.close()

    def test_dispatcher_continues_after_one_tenant_queue_failure(self):
        with schema_context('public'):
            inactive = Client(schema_name='inactive_dispatch', name='Inactive', is_active=False)
            inactive.auto_create_schema = False
            inactive.save()
        def enqueue(*, args, expires):
            self.assertNotEqual(args[0], 'public')
            self.assertNotEqual(args[0], inactive.schema_name)
            raise RuntimeError('broker unavailable')
        with patch('api.tasks.refresh_tenant_billing_catalog_task.apply_async', side_effect=enqueue):
            with self.assertLogs('api.tasks', level='ERROR'):
                result = refresh_monthly_billing_catalog_task()
        self.assertIn(self.tenant.schema_name, result['failed'])
        self.assertNotIn(inactive.schema_name, result['failed'])
        with patch('api.tasks.refresh_billing_catalog', side_effect=DatabaseError('transient')):
            with patch.object(refresh_tenant_billing_catalog_task, 'retry', side_effect=RuntimeError('retry queued')) as retry:
                with self.assertLogs('api.tasks', level='ERROR'):
                    with self.assertRaisesMessage(RuntimeError, 'retry queued'):
                        refresh_tenant_billing_catalog_task.run(self.tenant.schema_name)
                retry.assert_called_once()

    def test_materialized_view_migration_reverses_and_recreates_cleanly(self):
        migration = import_module('api.migrations.0017_monthly_billing_materialized_views')
        with connection.schema_editor() as editor:
            migration.drop_catalogs(None, editor)
            migration.create_catalogs(None, editor)
        with connection.cursor() as cursor:
            cursor.execute('SELECT matviewname, ispopulated FROM pg_matviews WHERE schemaname = %s', [self.tenant.schema_name])
            views = dict(cursor.fetchall())
        self.assertTrue(views['monthly_billing_catalog'])
        self.assertTrue(views['monthly_billing_summary'])
