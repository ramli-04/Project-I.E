import re
import uuid
from datetime import datetime, date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context, tenant_context
from rest_framework.test import APIClient

from customers.models import Client, PlatformAccount
from .capacity import capacity_preview
from .models import EmployeeProfile, PartnerClinic, Prescription
from .planning import TZ
from .planning_models import EmployeeAvailability, PlanningSettings, PlanningTask

NOW = datetime(2026, 11, 9, 8, tzinfo=TZ)


@override_settings(OUTBOX_PUBLISH_ON_COMMIT=False, EXTERNAL_DELIVERY_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CapacityPreviewTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = 'Capacity preview lab'

    def setUp(self):
        connection.set_tenant(self.tenant)
        clock = patch('django.utils.timezone.now', return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)
        with schema_context('public'):
            self.manager = PlatformAccount.objects.create(name='Capacity manager', login_key='capacity-manager',
                role='LAB', workstation_role='MANAGER', laboratory=self.tenant)
            self.dentist = PlatformAccount.objects.create(name='Capacity dentist', login_key='capacity-dentist', role='DENTIST')
        self.clinic = PartnerClinic.objects.create(name='Private clinic name', pickup_address='Private address',
            contact_phone='000', platform_dentist=self.dentist)
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.client.force_authenticate(self.manager)
        self.payload = {'delivery_service': 'STANDARD', 'impression_type': 'NUMERIQUE', 'clinical_item_count': 1}

    def resources(self):
        return [EmployeeProfile.objects.create(user=get_user_model().objects.create_user(username='cap-'+role),
            role=role, contract_type='CDI', hire_date=date(2026, 1, 1))
            for role in ['RECEPTION', 'CAO', 'FAO', 'QUALITE']]

    def preview(self, **changes):
        return self.client.post('/api/prescriptions/capacity-preview/', {**self.payload, **changes}, format='json')

    def test_available_route_is_feasible_and_never_selects_a_production_method(self):
        self.resources()
        response = self.preview()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIs(response.data['feasible'], True)
        self.assertTrue(response.data['provisional'])
        self.assertEqual(response.data['earliest_feasible_date'], '2026-11-09')
        self.assertEqual(response.data['requested_deadline'], datetime(2026, 11, 13, 8, tzinfo=TZ).isoformat())
        self.assertIsNone(response.data['reason_code'])
        self.assertFalse(Prescription.objects.exists())
        self.assertNotIn('production_method', response.data)

    def test_all_routes_compare_only_routes_with_the_required_resources(self):
        self.resources()
        self.assertIs(self.preview(production_method='CFAO').data['feasible'], None)
        self.assertIs(self.preview(production_method='IMPRESSION_3D').data['feasible'], None)
        self.assertIs(self.preview(production_method='CONVENTIONNEL').data['feasible'], True)
        self.assertIs(self.preview().data['feasible'], True)

    def test_capacity_shortage_returns_a_later_date_without_reserving_anything(self):
        staff = self.resources()
        for employee in staff:
            EmployeeAvailability.objects.create(employee=employee, availability_type='ABSENCE',
                starts_at=NOW, ends_at=NOW+timedelta(days=7))
        result = self.preview().data
        self.assertIs(result['feasible'], False)
        self.assertEqual(result['reason_code'], 'CAPACITY')
        self.assertEqual(result['earliest_feasible_date'], '2026-11-16')
        self.assertFalse(PlanningTask.objects.exists())

    def test_requested_closed_day_keeps_calendar_day_deadline_and_is_advisory(self):
        self.resources()
        with patch('django.utils.timezone.now', return_value=NOW+timedelta(days=2)):
            result = self.preview().data
        self.assertIs(result['feasible'], False)
        self.assertEqual(result['reason_code'], 'CLOSED_DAY')
        self.assertTrue(result['requested_deadline'].startswith('2026-11-15T08:00:00'))
        self.assertEqual(result['earliest_feasible_date'], '2026-11-11')

    def test_unknown_projection_returns_no_warning(self):
        result = self.preview().data
        self.assertIsNone(result['feasible'])
        self.assertIsNone(result['reason_code'])
        self.assertIsNone(result['earliest_feasible_date'])
        self.assertEqual(result['message'], '')

    def test_malformed_routing_is_unknown_instead_of_blocking_submission(self):
        for changes in [{'delivery_service': []}, {'impression_type': {}}, {'production_method': ['CFAO']},
                        {'clinical_item_count': 0}, {'clinical_item_count': 33}, {'clinical_item_count': True}]:
            with self.subTest(changes=changes):
                self.assertIsNone(self.preview(**changes).data['feasible'])
        self.assertIsNone(capacity_preview([])['feasible'])

    def test_preview_is_read_only_including_when_settings_do_not_exist(self):
        self.resources()
        self.assertFalse(PlanningSettings.objects.exists())
        with CaptureQueriesContext(connection) as queries:
            response = self.preview()
        self.assertEqual(response.status_code, 200)
        sql = '\n'.join(item['sql'] for item in queries.captured_queries)
        self.assertFalse(re.search(r'\b(INSERT|UPDATE|DELETE|FOR UPDATE|FOR NO KEY UPDATE|pg_advisory)\b', sql, re.I), sql)
        self.assertFalse(PlanningSettings.objects.exists())
        self.assertFalse(PlanningTask.objects.exists())
        self.assertFalse(Prescription.objects.exists())

    def test_lab_role_matrix_and_dentist_link_checks(self):
        with schema_context('public'):
            accounts = [PlatformAccount.objects.create(name='Cap '+role, login_key='cap-'+role.lower(),
                role='LAB', workstation_role=role, laboratory=self.tenant)
                for role in ['MANAGER', 'RECEPTION', 'CAO', 'FAO', 'QUALITE', 'COMPTABILITE']]
            unrelated = PlatformAccount.objects.create(name='Unrelated dentist', login_key='cap-unrelated', role='DENTIST')
        for account in accounts:
            self.client.force_authenticate(account)
            self.assertEqual(self.preview().status_code, 200 if account.workstation_role in {'MANAGER', 'RECEPTION'} else 403)
        self.client.force_authenticate(self.dentist)
        self.assertEqual(self.preview().status_code, 200)
        self.client.force_authenticate(unrelated)
        self.assertEqual(self.preview().status_code, 403)
        self.client.force_authenticate(None)
        self.assertIn(self.preview().status_code, [401, 403])

    def test_dentist_public_gateway_returns_dates_without_other_clinic_or_staff_data(self):
        self.resources()
        self.client.force_authenticate(self.dentist)
        result = self.client.post('/platform/dentist/capacity-preview/',
            {**self.payload, 'laboratory_id': self.tenant.schema_name}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertIs(result.data['feasible'], True)
        self.assertEqual(set(result.data), {'requested_deadline', 'feasible', 'earliest_feasible_date',
                                           'reason_code', 'message', 'provisional'})
        self.assertNotIn('Private', str(result.data))
        self.assertNotIn('cap-FAO', str(result.data))
        self.assertFalse(Prescription.objects.exists())

    def test_tenants_project_their_own_resources_and_unlinked_lab_is_denied(self):
        self.resources()
        with schema_context('public'):
            other = Client.objects.create(schema_name='capacity_isolation_lab', name='Other capacity lab')
        def remove_other():
            with schema_context('public'):
                other.delete(force_drop=True)
        self.addCleanup(remove_other)
        with tenant_context(other):
            self.assertIsNone(capacity_preview(self.payload)['feasible'])
        self.client.force_authenticate(self.dentist)
        response = self.client.post('/platform/dentist/capacity-preview/',
            {**self.payload, 'laboratory_id': other.schema_name}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertIs(self.client.post('/platform/dentist/capacity-preview/',
            {**self.payload, 'laboratory_id': self.tenant.schema_name}, format='json').data['feasible'], True)

    def test_warning_does_not_block_creation_and_completeness_remains_required(self):
        staff = self.resources()
        for employee in staff:
            EmployeeAvailability.objects.create(employee=employee, availability_type='ABSENCE',
                starts_at=NOW, ends_at=NOW+timedelta(days=7))
        self.assertIs(self.preview().data['feasible'], False)
        self.client.force_authenticate(self.dentist)
        body = {'laboratory_id': self.tenant.schema_name, 'partner_clinic': self.clinic.pk,
                'patient_ref': 'CAPACITY-ADVISORY', 'disinfected': True,
                'impression_type': 'NUMERIQUE', 'delivery_service': 'STANDARD',
                'clinical_items': [{'tooth_number': 11, 'function': 'Couronne', 'form': 'Anatomique',
                                    'shade': 'A2', 'material': 'Zircone'}]}
        response = self.client.post('/platform/dentist/orders/', body, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['production_method'], '')
        invalid = self.client.post('/platform/dentist/orders/', {**body, 'disinfected': False},
                                  format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(Prescription.objects.count(), 1)
