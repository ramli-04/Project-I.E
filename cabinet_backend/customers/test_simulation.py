from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class SimulationSeedBoundaryTests(SimpleTestCase):
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
