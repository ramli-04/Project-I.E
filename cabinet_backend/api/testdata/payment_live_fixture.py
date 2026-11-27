"""Create one historical invoice through real APIs, in verification only.

Not a registered management command or product endpoint. Run via the live suite.
A process-local test clock never changes worker time or any existing case.
"""
import json
import os
import uuid
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from datetime import datetime, timezone as utc
from unittest.mock import patch

import django
from django.conf import settings

django.setup()
assert os.environ.get('GESTION_LABO_VERIFICATION') == '1', 'Verification project required.'
assert settings.CABINET_SIMULATION and not settings.EXTERNAL_DELIVERY_ENABLED
assert settings.DATABASES['default']['NAME'] == 'cabinet_demo' and settings.DATABASES['default']['HOST'] == 'postgres'

from django.test import override_settings
from django_tenants.utils import tenant_context, schema_context
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile
from customers.models import Client, PlatformAccount
from api.models import Prescription
from api.case_commands import execute_case_command, qr_token

with schema_context('public'):
    lab = Client.objects.get(schema_name='simlab', is_active=True)
    manager = PlatformAccount.objects.get(laboratory=lab, name='Demo Manager', is_active=True)
    dentist = PlatformAccount.objects.get(name='Demo Dentist', role='DENTIST', is_active=True)
actor = f'platform:{manager.pk}:{manager.name}'
reference = 'BROWSER-PAY-'+uuid.uuid4().hex[:8]
client = APIClient(HTTP_HOST='simlab.localhost')
client.force_authenticate(manager)
with tenant_context(lab), override_settings(OUTBOX_PUBLISH_ON_COMMIT=False):
    response = client.post('/api/partner-clinics/', {'name': reference, 'pickup_address': 'Synthetic payment fixture only',
        'contact_phone': '0000000000', 'platform_dentist': dentist.pk}, format='json')
    assert response.status_code == 201, 'Synthetic clinic creation failed.'
    clinic_id = response.data['id']
    with patch('django.utils.timezone.now', return_value=datetime(2026,10,10,12,tzinfo=utc.utc)):
        client.force_authenticate(dentist)
        response = client.post('/platform/dentist/orders/', {'laboratory_id': 'simlab', 'partner_clinic': clinic_id,
            'patient_ref': reference, 'disinfected': True, 'impression_type': 'NUMERIQUE', 'delivery_service': 'STANDARD',
            'clinical_items': [{'tooth_number': 11, 'function': 'Couronne', 'form': 'Anatomique', 'shade': 'A2', 'material': 'Zircone'}]},
            format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        assert response.status_code == 201, 'Synthetic case creation failed.'
        source_id = response.data['id']
        pin = response.data['delivery_pin_once']
        client.force_authenticate(manager)
        mesh = b'solid test\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid test\n'
        response = client.post(f'/api/prescriptions/{source_id}/attachments/',
            {'kind': 'STL', 'file': SimpleUploadedFile('payment-test.stl', mesh)}, format='multipart')
        assert response.status_code == 201, 'Synthetic STL upload failed.'
        def command(action, data=None):
            return execute_case_command(source_id, action, data or {}, actor, 'MANAGER', uuid.uuid4())
        command('accept')
        for _ in range(40):
            order = Prescription.objects.get(pk=source_id)
            stage = order.status
            if stage == 'LIVRE':
                break
            if stage == 'ANALYSE_DEMANDE': command('advance', {'analysis_validated': True})
            elif stage == 'A_CONFIRMER':
                command('inspection', {'stage': 'DIGITAL', 'checks': dict.fromkeys(['margins', 'occlusion', 'space', 'scan_quality'], True)})
                command('advance', {'reception_validated': True})
            elif stage == 'PLANIFICATION':
                response = client.post('/api/production-lots/', {'code': reference, 'prescriptions': [source_id]}, format='json')
                assert response.status_code == 201, 'Synthetic production lot failed.'
                command('advance', {'production_method': 'CONVENTIONNEL', 'delivery_date': '2026-10-14'})
            elif stage == 'CONTROLE_QUALITE':
                command('inspection', {'stage': 'QUALITY', 'checks': dict.fromkeys(['margins','contacts','shade','occlusion','cosmetic','glazing','polishing'], True)})
                command('advance')
            elif stage == 'PRET_EXPEDITION': command('checkout', {'qr_token': qr_token(order)})
            elif stage == 'EN_ROUTE_CABINET': command('confirm-delivery', {'pin': pin})
            else: command('advance')
        else:
            raise AssertionError('Synthetic case did not reach delivery.')
    order = Prescription.objects.get(pk=source_id)
    period = order.statement_line.period
    assert str(period.month) == '2026-10-01', 'Only the new October fixture may close.'
    response = client.post(f'/api/billing/periods/{period.pk}/close/', {}, format='json')
    assert response.status_code == 200, 'Synthetic invoice closing failed.'
    print(json.dumps({'invoice': response.data['id'], 'number': response.data['number'], 'clinic': clinic_id,
                      'amount': response.data['total_amount'], 'reference': reference, 'case': source_id}))
