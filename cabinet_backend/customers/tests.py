from api.models import PartnerClinic
from django.contrib.auth.hashers import check_password
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIClient
from .models import Domain, PlatformAccount, AccessLog


class PlatformTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = 'Laboratoire test'

    def setUp(self):
        from django.contrib.auth.hashers import make_password
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.password = 'secure-test-pass'
        h = make_password(self.password)
        self.admin = PlatformAccount.objects.create(name='Admin', login_key='admin', role='ADMIN', password_hash=h)
        self.dentist = PlatformAccount.objects.create(name='Dentiste 1', login_key='dentiste1', role='DENTIST', password_hash=h)
        self.other = PlatformAccount.objects.create(name='Dentiste 2', login_key='dentiste2', role='DENTIST', password_hash=h)
        self.worker = PlatformAccount.objects.create(name='Labo 1 - Mohamed', login_key='labo1mohamed', role='LAB', laboratory=self.tenant, password_hash=h)

    def login(self, name, password=None):
        response = self.client.post('/platform/login/', {'name': name, 'password': password or self.password}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["token"]}')
        return response.data

    def test_name_routing_and_login_logs(self):
        login = self.login('  LABO 1 – Mohamed ')
        self.assertEqual(login['account']['laboratory_id'], self.tenant.schema_name)
        self.assertEqual(login['account']['role'], 'LAB')
        self.assertEqual(self.client.get('/api/prescriptions/').status_code, 200)
        self.assertEqual(self.client.post('/platform/logout/').status_code, 204)
        self.assertEqual(self.client.post('/platform/login/', {'name': 'unknown'}, format='json').status_code, 400)
        self.assertTrue(AccessLog.objects.filter(event='LOGIN', success=False).exists())
        self.assertTrue(AccessLog.objects.filter(event='LOGOUT', account=self.worker).exists())

    def test_portal_login_accepts_short_name_in_selected_laboratory(self):
        response = self.client.post('/platform/login/', {
            'name': '  Mohamed  ', 'role': 'LAB', 'laboratory': self.tenant.schema_name, 'password': self.password,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['account']['id'], self.worker.pk)
        self.assertEqual(response.data['account']['laboratory_id'], self.tenant.schema_name)
        self.worker.is_active = False
        self.worker.save()
        response = self.client.post('/platform/login/', {
            'name': 'Mohamed', 'role': 'LAB', 'laboratory': self.tenant.schema_name, 'password': self.password,
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_portal_login_enforces_role_and_laboratory(self):
        invalid = [
            {'name': 'Mohamed', 'role': 'LAB'},
            {'name': self.worker.name, 'role': 'LAB', 'laboratory': 'unknown'},
            {'name': self.worker.name, 'role': 'DENTIST'},
            {'name': 'Admin', 'role': 'DENTIST'},
            {'name': 'Admin', 'role': 'INVALID'},
            {'name': '', 'role': 'LAB', 'laboratory': self.tenant.schema_name},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertIn(self.client.post('/platform/login/', {**payload, 'password': self.password}, format='json').status_code, [400, 401])
        response = self.client.post('/platform/login/', {'name': 'Dentiste 1', 'role': 'DENTIST', 'password': self.password}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['account']['id'], self.dentist.pk)

    def test_portal_login_rejects_ambiguous_short_names(self):
        PlatformAccount.objects.create(name='Mohamed', login_key='mohamed', role='LAB', laboratory=self.tenant)
        response = self.client.post('/platform/login/', {
            'name': 'Mohamed', 'role': 'LAB', 'laboratory': self.tenant.schema_name, 'password': self.password,
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_admin_permissions_account_assignment_and_deactivation(self):
        self.assertIn(self.client.get('/platform/accounts/').status_code, [401, 403])
        self.login('Dentiste 1')
        self.assertEqual(self.client.get('/platform/accounts/').status_code, 403)
        self.assertEqual(self.client.post('/platform/laboratories/', {'name': 'Forbidden', 'identifier': 'forbidden'}, format='json').status_code, 403)
        self.login('Admin')
        response = self.client.post('/platform/accounts/', {'name': 'Labo test - Sara', 'role': 'LAB', 'laboratory': self.tenant.pk}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        account_id = response.data['id']
        self.assertNotIn('password_hash', response.data)
        self.assertEqual(self.client.post('/platform/accounts/', {'name': 'Labo test Sara', 'role': 'LAB', 'laboratory': self.tenant.pk}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/platform/accounts/', {'name': 'No lab', 'role': 'LAB'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/platform/accounts/{account_id}/', {'is_active': False}, format='json').status_code, 200)
        self.assertIn(self.client.post('/platform/login/', {'name': 'Labo test - Sara', 'password': 'any'}, format='json').status_code, [400, 401])
        self.assertEqual(self.client.patch(f'/platform/accounts/{self.admin.pk}/', {'is_active': False}, format='json').status_code, 400)

    def test_password_reset_hash_and_session_expiry(self):
        old_token = self.login('Dentiste 1')['token']
        self.login('Admin')
        response = self.client.post(f'/platform/accounts/{self.dentist.pk}/reset-password/')
        self.assertEqual(response.status_code, 200, response.data)
        self.dentist.refresh_from_db()
        self.assertTrue(check_password(response.data['temporary_password'], self.dentist.password_hash))
        self.assertNotIn(response.data['temporary_password'], str(list(AccessLog.objects.values())))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {old_token}')
        self.assertIn(self.client.get('/platform/dentist/orders/').status_code, [401, 403])
        self.login('Dentiste 1')
        self.assertEqual(self.client.get('/platform/dentist/orders/').status_code, 200)

    def test_lab_creation_and_order_isolation(self):
        self.login('Admin')
        created = self.client.post('/platform/laboratories/', {'name': 'Autre labo', 'identifier': 'otherlab'}, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        self.assertTrue(Domain.objects.filter(domain='otherlab.localhost').exists())
        self.assertEqual(self.client.post('/platform/laboratories/', {'name': 'Duplicate', 'identifier': 'otherlab'}, format='json').status_code, 400)
        self.login('Labo 1 - Mohamed')
        self.assertEqual(self.client.get('/api/prescriptions/', HTTP_HOST='otherlab.localhost').status_code, 403)
        self.login('Dentiste 1')
        payload = {'laboratory_id': 'otherlab', 'patient_ref': 'QA-ROUTING', 'dentist_name': 'Spoofed', 'tooth_number': 11, 'shade': 'A2', 'material': 'Zircone', 'disinfected': True, 'clinical_items': [{'tooth_number': 11, 'function': 'Couronne', 'form': 'Anatomique', 'shade': 'A2', 'material': 'Zircone'}], 'partner_clinic': PartnerClinic.objects.create(name='Other Clinic', pickup_address='123 Road', platform_dentist=self.dentist).pk}
        order = self.client.post('/platform/dentist/orders/', payload, format='json')
        self.assertEqual(order.status_code, 201, order.data)
        self.assertEqual(order.data['dentist_name'], self.dentist.name)
        self.assertEqual(order.data['laboratory_id'], 'otherlab')
        from api.models import Prescription
        self.assertEqual(Prescription.objects.count(), 0)
        with schema_context('otherlab'):
            self.assertEqual(Prescription.objects.get().dentist_account_id, self.dentist.pk)
        self.assertEqual(len(self.client.get('/platform/dentist/orders/').data), 1)
        self.login('Dentiste 2')
        self.assertEqual(self.client.get('/platform/dentist/orders/').data, [])
        self.assertEqual(self.client.get('/api/prescriptions/').status_code, 403)

    def test_technical_support_and_overview(self):
        self.login('Dentiste 1')
        created = self.client.post('/platform/support/', {'subject': 'Test technique', 'message': 'Description du problème'}, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        self.login('Dentiste 2')
        self.assertEqual(self.client.get('/platform/support/').data, [])
        self.assertEqual(self.client.patch(f'/platform/support/{created.data["id"]}/', {'status': 'RESOLVED'}, format='json').status_code, 403)
        self.login('Admin')
        self.assertEqual(len(self.client.get('/platform/support/').data), 1)
        self.assertEqual(self.client.get('/platform/overview/').data['open_tickets'], 1)
        self.assertEqual(self.client.patch(f'/platform/support/{created.data["id"]}/', {'status': 'RESOLVED'}, format='json').status_code, 200)
        self.assertEqual(self.client.get('/platform/overview/').data['open_tickets'], 0)
        self.assertEqual(self.client.get('/platform/logs/').status_code, 200)

    def test_accounts_patch_does_not_revoke_sessions_when_sensitive_fields_unchanged(self):
        dentist_token = self.login('Dentiste 1')['token']
        self.login('Admin')
        # Admin updates name only; sensitive fields untouched
        response = self.client.patch(f'/platform/accounts/{self.dentist.pk}/', {'name': 'Dentiste 1 Modifie'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        # Dentist session is STILL valid
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {dentist_token}')
        self.assertEqual(self.client.get('/platform/dentist/orders/').status_code, 200)

        # Admin changes role to LAB (sensitive change)
        self.login('Admin')
        response = self.client.patch(f'/platform/accounts/{self.dentist.pk}/', {'role': 'LAB', 'laboratory': self.tenant.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        # Dentist session is now REVOKED
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {dentist_token}')
        self.assertIn(self.client.get('/platform/dentist/orders/').status_code, [401, 403])

    def test_dentist_attachment_download_and_isolation(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.login('Dentiste 1')
        clinic = PartnerClinic.objects.create(name='Clinic 1', pickup_address='123 St', platform_dentist=self.dentist)
        payload = {
            'laboratory_id': self.tenant.schema_name, 'patient_ref': 'ATTACH-1', 'dentist_name': self.dentist.name,
            'tooth_number': 11, 'shade': 'A2', 'material': 'Zircone', 'disinfected': True,
            'clinical_items': [{'tooth_number': 11, 'function': 'Couronne', 'form': 'Anatomique', 'shade': 'A2', 'material': 'Zircone'}],
            'partner_clinic': clinic.pk,
        }
        order_res = self.client.post('/platform/dentist/orders/', payload, format='json')
        self.assertEqual(order_res.status_code, 201, order_res.data)
        order_id = order_res.data['id']

        # Upload STL attachment
        stl_file = SimpleUploadedFile('scan.stl', b'solid a\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid a\n')
        upload_res = self.client.post(f'/platform/dentist/orders/{self.tenant.schema_name}/{order_id}/attachments/',
                                     {'kind': 'STL', 'file': stl_file}, format='multipart')
        self.assertEqual(upload_res.status_code, 201, upload_res.data)
        attachment_id = upload_res.data['id']

        # Dentist downloads their own attachment
        download_res = self.client.get(f'/platform/dentist/orders/{self.tenant.schema_name}/{order_id}/attachment/{attachment_id}/')
        self.assertEqual(download_res.status_code, 200)

        # Other dentist cannot download
        self.login('Dentiste 2')
        other_res = self.client.get(f'/platform/dentist/orders/{self.tenant.schema_name}/{order_id}/attachment/{attachment_id}/')
        self.assertEqual(other_res.status_code, 404)
