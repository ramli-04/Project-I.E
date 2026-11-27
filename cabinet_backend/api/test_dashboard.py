"""Dashboard composition verified against real synthetic workflow evidence."""
from datetime import datetime, timedelta, timezone as utc
from decimal import Decimal
from unittest.mock import patch
import uuid

from django.db import connection, transaction
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIClient
from customers.models import Client, PlatformAccount

from .analytics import refresh_billing_catalog
from .billing import close_period
from .models import PartnerClinic, Prescription, BillingDispute
from .payments import record_payment
from .planning_models import PlanningSettings
from .test_support import WorkflowFixtures

NOW = datetime(2026, 11, 25, 12, tzinfo=utc.utc)


@override_settings(OUTBOX_PUBLISH_ON_COMMIT=False, EXTERNAL_DELIVERY_ENABLED=False)
class DashboardTests(WorkflowFixtures, TenantTestCase):
    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        clock = patch('django.utils.timezone.now', return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)
        self.manager = self.account('MANAGER')
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.client.force_authenticate(self.manager)
        self.clinic = PartnerClinic.objects.create(name='Dashboard clinic', pickup_address='Synthetic address')

    def account(self, role, tenant=None):
        with schema_context('public'):
            return PlatformAccount.objects.create(name='Dashboard '+role, login_key='dash-'+uuid.uuid4().hex,
                role='DENTIST' if role == 'DENTIST' else 'COURIER' if role == 'COURIER' else 'LAB',
                workstation_role=role if role not in {'DENTIST','COURIER'} else '',
                laboratory=(tenant or self.tenant) if role != 'DENTIST' else None)

    def order(self, target='DEMANDE_RECUE', created=None, **values):
        with patch('django.utils.timezone.now', return_value=created or NOW):
            order = Prescription.objects.create(patient_ref='DASH-'+uuid.uuid4().hex[:8], dentist_name='Synthetic dentist',
                tooth_number=11, shade='A2', material='Zircone', disinfected=True, total_price='1000.00',
                base_amount='1000.00', accepted=True, impression_type='NUMERIQUE', intake_version=1,
                partner_clinic=self.clinic, **values)
        if target != 'DEMANDE_RECUE':
            self.deliver_case(order, stop_at=target)
        return order

    def invoice(self, now=NOW):
        order = self.order(created=datetime(2025, 1, 1, 12, tzinfo=utc.utc))
        delivery = (now.replace(day=1)-timedelta(days=1)).replace(day=10, hour=12)
        with patch('django.utils.timezone.now', return_value=delivery):
            self.deliver_case(order)
        with patch('django.utils.timezone.now', return_value=now):
            invoice = close_period(order.statement_line.period_id, 'test:dashboard')
        return invoice

    def summary(self, account=None):
        if account:
            self.client.force_authenticate(account)
        response = self.client.get('/api/dashboard/summary/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response['Cache-Control'], 'no-store')
        return response.data

    def test_role_matrix_and_finance_subset(self):
        self.assertIn('operations', self.summary())
        accounting = self.summary(self.account('COMPTABILITE'))
        self.assertIn('finance', accounting)
        self.assertNotIn('operations', accounting)
        for role in ['RECEPTION','CAO','FAO','QUALITE','COURIER','DENTIST']:
            self.client.force_authenticate(self.account(role))
            response = self.client.get('/api/dashboard/summary/')
            self.assertEqual(response.status_code, 403, (role, response.data))
        self.client.force_authenticate(None)
        self.assertIn(self.client.get('/api/dashboard/summary/').status_code, [401,403])

    def test_operations_known_stages_risk_deadlines_and_pause_union(self):
        fresh = self.order()
        late = self.order(created=NOW-timedelta(days=10))
        pending = self.order('SALLE_CAO')
        self.workflow_command(pending, 'pause', {'paused': True, 'notes': 'Synthetic pause'})
        result = self.summary()['operations']
        self.assertEqual(result['active_cases'], 3)
        stages = {row['key']:row['count'] for row in result['stages']}
        self.assertEqual(stages['COMMANDE'], 2)
        self.assertEqual(stages['CONCEPTION'], 1)
        self.assertEqual(sum(stages.values()), 3)
        self.assertEqual([row['id'] for row in result['late']], [str(late.pk)])
        self.assertIn(str(fresh.pk), [row['id'] for row in result['at_risk']])
        self.assertEqual(result['paused_cases'], 1)
        self.assertGreaterEqual(result['paused_or_blocked_cases'], 1)
        self.assertIsNone(result['rework_30_days']['rate_percent'])
        self.assertEqual(result['deliveries_due_today'], 0)
        self.assertEqual(result['deliveries_due_this_week'], 2)

    def test_delivered_cases_are_active_for_fitting_but_have_no_delivery_risk(self):
        self.order('LIVRE', created=NOW-timedelta(days=10))
        result = self.summary()['operations']
        self.assertEqual(result['active_cases'], 1)
        self.assertEqual(result['late'], [])
        self.assertEqual(result['at_risk'], [])
        self.assertEqual(result['rework_30_days'], {'reworks':0,'delivered':1,'rate_percent':0.0})

    def test_rework_ratio_uses_evidence_and_delivery_window(self):
        self.order('LIVRE')
        remake = self.order('SALLE_CAO')
        self.workflow_command(remake, 'rework', {'origin':'LAB','cause':'Synthetic correction',
            'corrective_action':'Review design','restart_status':'SALLE_CAO','losses':[]})
        self.assertEqual(self.summary()['operations']['rework_30_days'], {'reworks':1,'delivered':1,'rate_percent':100.0})

    def test_finance_reuses_catalogs_and_live_receivables(self):
        invoice = self.invoice()
        record_payment({'clinic':self.clinic.pk,'method':'ESPECES','amount':'400.00','received_on':'2026-11-25',
            'allocations':[{'invoice':str(invoice.pk),'amount':'400.00'}]},'test:dashboard',uuid.uuid4())
        BillingDispute.objects.create(prescription_id=invoice.lines[0]['case_id'], invoice=invoice,
            reason='Synthetic dispute', raised_by='test:dashboard')
        refresh_billing_catalog(self.tenant.schema_name)
        data = self.summary()['finance']
        self.assertEqual(data['billed_this_month'], '1000.00')
        self.assertEqual(data['last_closed_month'].isoformat(), '2026-10-01')
        self.assertEqual(data['invoiced_last_closed_month'], '1000.00')
        self.assertEqual(data['total_receivables'], '600.00')
        self.assertEqual(data['over_60_days'], '0.00')
        self.assertEqual(data['open_disputes'], 1)
        self.assertFalse(data['analytics']['stale'])
        # Catalog figures can be stale; the read never silently refreshes or writes.
        with patch('django.utils.timezone.now', return_value=NOW+timedelta(minutes=21)):
            self.assertTrue(self.summary()['finance']['analytics']['stale'])

    def test_month_uses_casablanca_boundary_and_existing_catalog_definition(self):
        boundary = datetime(2026, 1, 31, 23, 30, tzinfo=utc.utc)
        self.invoice(now=boundary)
        refresh_billing_catalog(self.tenant.schema_name)
        with patch('django.utils.timezone.now', return_value=boundary):
            data = self.summary()['finance']
            self.assertEqual(data['month'].isoformat(), '2026-02-01')
            self.assertEqual(data['billed_this_month'], '1000.00')
        with patch('django.utils.timezone.now', return_value=boundary-timedelta(hours=1)):
            self.assertEqual(self.summary()['finance']['billed_this_month'], '0.00')

    def test_read_is_uncached_and_does_not_create_missing_settings(self):
        self.assertFalse(PlanningSettings.objects.exists())
        with patch('django.core.cache.cache.get') as get, patch('django.core.cache.cache.set') as put:
            with CaptureQueriesContext(connection) as queries:
                self.summary()
            get.assert_not_called()
            put.assert_not_called()
        writes = [q['sql'] for q in queries if q['sql'].lstrip().upper().startswith(('INSERT','UPDATE','DELETE'))]
        self.assertEqual(writes, [])
        self.assertFalse(PlanningSettings.objects.exists())
        self.order()
        self.assertEqual(self.summary()['operations']['active_cases'], 1)

    def test_tenant_summary_and_cross_tenant_membership(self):
        local = self.order()
        other = Client(schema_name='dashboardother', name='Other dashboard lab')
        with schema_context('public'):
            other.save()
        foreign_account = None
        try:
            foreign_account = self.account('MANAGER', other)
            with schema_context(other.schema_name):
                clinic = PartnerClinic.objects.create(name='Other dashboard clinic', pickup_address='Other address')
                foreign = Prescription.objects.create(patient_ref='DASH-FOREIGN', dentist_name='Synthetic foreign dentist',
                    tooth_number=11,shade='A2',material='Zircone',disinfected=True,partner_clinic=clinic,accepted=True)
                other_client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
                other_client.force_authenticate(foreign_account)
                # APIRequestFactory preserves the real tenant membership and endpoint checks.
                from rest_framework.test import APIRequestFactory, force_authenticate
                from .dashboard import dashboard_summary
                request = APIRequestFactory().get('/api/dashboard/summary/')
                request.tenant = other
                force_authenticate(request, foreign_account)
                foreign_summary = dashboard_summary(request)
                self.assertEqual(foreign_summary.status_code, 200)
                rows = foreign_summary.data['operations']['at_risk']
                self.assertEqual([r['id'] for r in rows], [str(foreign.pk)])
                self.assertNotIn(str(local.pk), str(foreign_summary.data))
                request = APIRequestFactory().get('/api/dashboard/summary/')
                request.tenant = other
                force_authenticate(request, self.manager)
                self.assertEqual(dashboard_summary(request).status_code, 403)
            self.assertNotIn('DASH-FOREIGN', str(self.summary()))
        finally:
            # Evaluate deferred evidence guards before removing this test-only schema.
            connection.check_constraints()
            connection.set_tenant(self.tenant)
            with schema_context('public'):
                if foreign_account:
                    PlatformAccount.objects.filter(pk=foreign_account.pk).update(laboratory=None)
                other.delete(force_drop=True)
