from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class SimulationSeedBoundaryTests(SimpleTestCase):
    @override_settings(CORS_ALLOWED_ORIGINS=['http://localhost:18080'])
    def test_browser_preflight_accepts_idempotency_and_default_headers(self):
        from corsheaders.middleware import CorsMiddleware
        from django.http import HttpResponse
        from django.test import RequestFactory
        request=RequestFactory().options('/api/prescriptions/', HTTP_ORIGIN='http://localhost:18080',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='authorization,content-type,idempotency-key')
        response=CorsMiddleware(lambda request:HttpResponse())(request)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Access-Control-Allow-Origin'],'http://localhost:18080')
        allowed={header.strip() for header in response['Access-Control-Allow-Headers'].split(',')}
        self.assertTrue({'authorization','content-type','idempotency-key'} <= allowed)

    @override_settings(CABINET_SIMULATION=False)
    def test_native_application_refuses_synthetic_seed_before_database_access(self):
        with self.assertRaisesMessage(CommandError, 'dedicated cabinet_demo database'):
            call_command('seed_virtual_lab')

    @override_settings(CABINET_SIMULATION=True)
    def test_simulation_flag_alone_cannot_seed_normal_database(self):
        with patch('customers.management.commands.seed_virtual_lab.settings') as configured:
            configured.CABINET_SIMULATION = True
            configured.DATABASES = {'default': {'NAME': 'cabinet'}}
            with self.assertRaisesMessage(CommandError, 'dedicated cabinet_demo database'):
                call_command('seed_virtual_lab')

    def test_demo_requires_explicit_password_before_database_access(self):
        with patch('customers.management.commands.seed_virtual_lab.settings') as configured, patch.dict('os.environ', {'DEMO_ACCOUNT_PASSWORD': ''}):
            configured.CABINET_SIMULATION = True
            configured.DATABASES = {'default': {'NAME': 'cabinet_demo'}}
            with self.assertRaisesMessage(CommandError, 'DEMO_ACCOUNT_PASSWORD'):
                call_command('seed_virtual_lab')
