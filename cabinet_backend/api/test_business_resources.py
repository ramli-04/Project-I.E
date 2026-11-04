from datetime import date
import uuid

from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from customers.models import Client, PlatformAccount
from .models import EmployeeProfile, Inventory, Machine, PartnerClinic


class LaboratoryBusinessResourceTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = 'Business resource test laboratory'

    def setUp(self):
        connection.set_tenant(self.tenant)
        with schema_context('public'):
            self.manager = get_user_model().objects.create_user(
                username='resource-manager', is_superuser=True,
            )
            self.employee = get_user_model().objects.create_user(username='resource-employee')
            self.dentist = get_user_model().objects.create_user(username='resource-dentist')
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.client.force_authenticate(user=self.manager)

    def test_resource_crud_and_public_user_relationships(self):
        resources = {
            'employee-profiles': {
                'user': self.employee.pk, 'role': 'CAO', 'contract_type': 'CDI',
                'hire_date': '2026-10-31',
            },
            'machines': {
                'name': 'CNC', 'machine_type': 'USINEUSE_CNC', 'capacity': 8,
                'status': 'ACTIF',
            },
            'inventory': {
                'material_name': 'Zircone A2', 'quantity': 2.5,
                'unit': 'DISQUE', 'alert_threshold': 3,
            },
            'partner-clinics': {
                'name': 'Clinic', 'pickup_address': '12 Main Street',
                'contact_phone': '+212600000000', 'linked_dentist': self.dentist.pk,
            },
        }
        for endpoint, payload in resources.items():
            with self.subTest(endpoint=endpoint):
                url = f'/api/{endpoint}/'
                response = self.client.post(url, payload, format='json')
                self.assertEqual(response.status_code, 201, response.data)
                detail = f'{url}{response.data["id"]}/'
                self.assertEqual(self.client.get(detail).status_code, 200)
                patch = {'is_available': False} if endpoint == 'employee-profiles' else (
                    {'material_name': 'Updated'} if endpoint == 'inventory' else {'name': 'Updated'}
                )
                self.assertEqual(self.client.patch(detail, patch, format='json').status_code, 200)
                self.assertEqual(self.client.delete(detail).status_code, 400 if endpoint == 'inventory' else 204)
                self.assertEqual(self.client.get(detail).status_code, 200 if endpoint == 'inventory' else 404)
        with schema_context('public'):
            self.assertTrue(get_user_model().objects.filter(pk=self.employee.pk).exists())
            self.assertNotIn('api_employeeprofile', connection.introspection.table_names())

    def test_validation_and_low_stock_boundary(self):
        inventory = {'material_name': 'PMMA', 'quantity': 3, 'unit': 'DISQUE', 'alert_threshold': 3}
        result = self.client.post('/api/inventory/', inventory, format='json')
        self.assertTrue(result.data['is_low_stock'])
        movement = self.client.post('/api/inventory-transactions/', {
            'inventory_item': result.data['id'], 'quantity_changed': '1', 'transaction_type': 'RESTOCK',
            'idempotency_key': str(uuid.uuid4()),
        }, format='json')
        self.assertEqual(movement.status_code, 201, movement.data)
        updated = self.client.get(f'/api/inventory/{result.data["id"]}/')
        self.assertFalse(updated.data['is_low_stock'])
        invalid = [
            ('inventory', {**inventory, 'quantity': -1}, 'quantity'),
            ('inventory', {**inventory, 'quantity': 'NaN'}, 'quantity'),
            ('inventory', {**inventory, 'alert_threshold': 'Infinity'}, 'alert_threshold'),
            ('inventory', {**inventory, 'alert_threshold': -1}, 'alert_threshold'),
            ('inventory', {**inventory, 'unit': 'UNKNOWN'}, 'unit'),
            ('machines', {'name': 'Four', 'machine_type': 'FOUR_FRITTAGE', 'capacity': 0}, 'capacity'),
            ('partner-clinics', {'name': 'Clinic', 'pickup_address': '   ', 'contact_phone': '123'}, 'pickup_address'),
            ('partner-clinics', {'name': 'Clinic', 'contact_phone': '123'}, 'pickup_address'),
            ('employee-profiles', {'user': self.employee.pk, 'role': 'UNKNOWN', 'contract_type': 'CDI', 'hire_date': '2026-10-31'}, 'role'),
        ]
        for endpoint, payload, field in invalid:
            with self.subTest(endpoint=endpoint, field=field, payload=payload):
                response = self.client.post(f'/api/{endpoint}/', payload, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(field, response.data)

    def test_employee_is_unique_within_laboratory(self):
        payload = {'user': self.employee.pk, 'role': 'RECEPTION', 'contract_type': 'CDD', 'hire_date': '2026-10-31'}
        self.assertEqual(self.client.post('/api/employee-profiles/', payload, format='json').status_code, 201)
        duplicate = self.client.post('/api/employee-profiles/', payload, format='json')
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn('user', duplicate.data)

    def test_anonymous_and_unassigned_users_cannot_access_resources(self):
        self.client.force_authenticate(user=None)
        for endpoint in ['employee-profiles', 'machines', 'inventory', 'partner-clinics']:
            self.assertIn(self.client.get(f'/api/{endpoint}/').status_code, [401, 403])
        self.client.force_authenticate(user=self.employee)
        self.assertEqual(self.client.get('/api/machines/').status_code, 403)
        EmployeeProfile.objects.create(user=self.employee, role='CAO', contract_type='CDI', hire_date=date.today())
        self.assertEqual(self.client.get('/api/machines/').status_code, 200)
        self.client.force_authenticate(user=self.manager)
        self.assertIn(self.client.get('/api/machines/', HTTP_HOST='localhost').status_code, [403, 404])

    def test_demo_laboratory_account_is_supported(self):
        from django.contrib.auth.hashers import make_password
        with schema_context('public'):
            PlatformAccount.objects.create(name='Resource lab', login_key='resourcelab', role='LAB', laboratory=self.tenant,
                                           password_hash=make_password('secure-test-pass'))
        self.client.force_authenticate(user=None)
        bad_login = self.client.post('/platform/login/', {'name': 'Resource lab'}, format='json')
        self.assertEqual(bad_login.status_code, 401)
        login = self.client.post('/platform/login/', {'name': 'Resource lab', 'password': 'secure-test-pass'}, format='json')
        self.assertEqual(login.status_code, 200, login.data)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["token"]}')
        self.assertEqual(self.client.get('/api/machines/').status_code, 200)

    def test_business_data_is_isolated_between_schemas(self):
        machine = Machine.objects.create(name='Private CNC', machine_type='USINEUSE_CNC', capacity=1)
        with schema_context('public'):
            other = Client.objects.create(schema_name='resource_other', name='Other laboratory')
        try:
            with schema_context('resource_other'):
                self.assertFalse(Machine.objects.filter(pk=machine.pk).exists())
                self.assertEqual(Inventory.objects.count(), 0)
                self.assertEqual(PartnerClinic.objects.count(), 0)
                self.assertEqual(EmployeeProfile.objects.count(), 0)
                EmployeeProfile.objects.create(user=self.employee, role='FAO', contract_type='CDI', hire_date=date.today())
            self.assertEqual(EmployeeProfile.objects.count(), 0)
        finally:
            with schema_context('public'):
                with connection.cursor() as cursor:
                    cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
                other.delete(force_drop=True)
