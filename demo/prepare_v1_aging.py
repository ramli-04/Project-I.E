"""Two historical invoices through guarded commands, in Docker verification only."""
import json
import os
from pathlib import Path
import sys
import uuid
from datetime import datetime, timedelta, timezone as utc
from unittest.mock import patch


def ensure_verification(env=None, container=None):
    env = os.environ if env is None else env
    container = Path('/.dockerenv').is_file() if container is None else container
    if (not container or env.get('GESTION_LABO_VERIFICATION') != '1'
            or env.get('CABINET_SIMULATION') != '1' or env.get('POSTGRES_HOST') != 'postgres'
            or env.get('POSTGRES_DB') != 'cabinet_demo'):
        raise RuntimeError('Outil reserve au projet Docker de verification.')


def main():
    ensure_verification()
    import django
    django.setup()
    from django.conf import settings
    from django.test import override_settings
    from django_tenants.utils import tenant_context, schema_context
    from rest_framework.test import APIClient
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.utils import timezone
    from customers.models import Client, PlatformAccount
    from api.models import Prescription
    from api.case_commands import CHECKS, qr_token
    assert settings.CABINET_SIMULATION and not settings.EXTERNAL_DELIVERY_ENABLED
    assert settings.DATABASES['default']['NAME'] == 'cabinet_demo'
    assert settings.DATABASES['default']['HOST'] == 'postgres'
    with schema_context('public'):
        lab = Client.objects.get(schema_name='simlab', is_active=True)
        manager = PlatformAccount.objects.get(laboratory=lab, name='Demo Manager', is_active=True)
        dentist = PlatformAccount.objects.get(name='Demo Dentist', role='DENTIST', is_active=True)
    client = APIClient(HTTP_HOST='simlab.localhost')
    result = []
    with tenant_context(lab), override_settings(OUTBOX_PUBLISH_ON_COMMIT=False):
        today = timezone.localdate()
        for issued_days_ago, bucket in [(85, '31_60'), (45, '0_30')]:
            issued_on = today - timedelta(days=issued_days_ago)
            delivered_on = issued_on.replace(day=1) - timedelta(days=1)
            period_month = delivered_on.replace(day=1).isoformat()
            delivery_clock = datetime(delivered_on.year, delivered_on.month, delivered_on.day, 12, tzinfo=utc.utc)
            invoice_clock = datetime(issued_on.year, issued_on.month, issued_on.day, 12, tzinfo=utc.utc)
            reference = 'V1-AGING-' + bucket + '-' + uuid.uuid4().hex[:8]
            client.force_authenticate(manager)
            response = client.post('/api/partner-clinics/', {
                'name': reference, 'pickup_address': 'V1 - adresse fictive',
                'contact_phone': '0000000000', 'platform_dentist': dentist.pk,
                'payment_terms_days': 30}, format='json')
            assert response.status_code == 201, 'Synthetic clinic rejected.'
            clinic = response.data['id']
            def post(path, data):
                response = client.post(path, data, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
                assert 200 <= response.status_code < 300, 'Synthetic action rejected: ' + path
                return response.data
            with patch('django.utils.timezone.now', return_value=delivery_clock):
                client.force_authenticate(dentist)
                created = post('/platform/dentist/orders/', {
                    'laboratory_id': 'simlab', 'partner_clinic': clinic, 'patient_ref': reference,
                    'disinfected': True, 'impression_type': 'NUMERIQUE', 'delivery_service': 'STANDARD',
                    'clinical_items': [{'tooth_number': 11, 'function': 'Couronne', 'form': 'Anatomique',
                                        'shade': 'A2', 'material': '100% Métal'}]})
                case = str(created['id'])
                assert created['patient_ref'] == reference and created['partner_clinic'] == clinic
                pin = created['delivery_pin_once']
                client.force_authenticate(manager)
                mesh = b'solid v1\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid v1\n'
                response = client.post('/api/prescriptions/' + case + '/attachments/',
                    {'kind': 'STL', 'file': SimpleUploadedFile('V1-NON-MANUFACTURING.stl', mesh)}, format='multipart')
                assert response.status_code == 201
                def owned():
                    order = Prescription.objects.get(pk=case)
                    assert order.patient_ref == reference and reference.startswith('V1-')
                    assert order.partner_clinic_id == clinic
                    return order
                def command(action, data=None):
                    owned()
                    return post('/api/prescriptions/' + case + '/command/',
                        {'action': action, 'data': {'notes': 'V1 - decision fictive explicite', **(data or {})}})
                command('accept')
                for _ in range(40):
                    order = owned()
                    step = order.status
                    if step == 'LIVRE':
                        break
                    if step == 'ANALYSE_DEMANDE':
                        command('advance', {'analysis_validated': True})
                    elif step == 'A_CONFIRMER':
                        command('advance', {'reception_validated': True})
                    elif step in {'CONTROLE_DOSSIER', 'CONTROLE_QUALITE'}:
                        inspection = 'DIGITAL' if step == 'CONTROLE_DOSSIER' else 'QUALITY'
                        command('inspection', {'stage': inspection, 'checks': dict.fromkeys(CHECKS[inspection], True), 'advance': True})
                    elif step == 'PLANIFICATION':
                        post('/api/production-lots/', {'code': reference, 'prescriptions': [case]})
                        command('advance', {'production_method': 'CONVENTIONNEL', 'thermal_treatment': 'AUCUN',
                                            'delivery_date': (delivered_on + timedelta(days=4)).isoformat()})
                    elif step == 'PRET_EXPEDITION':
                        command('checkout', {'qr_token': qr_token(order)})
                    elif step == 'EN_ROUTE_CABINET':
                        command('confirm-delivery', {'pin': pin})
                    else:
                        command('advance')
                else:
                    raise AssertionError('Synthetic delivery incomplete.')
            period = owned().statement_line.period
            assert str(period.month) == period_month
            assert period.clinic_id == clinic and period.closed_at is None
            with patch('django.utils.timezone.now', return_value=invoice_clock):
                invoice = post('/api/billing/periods/' + str(period.pk) + '/close/', {})
            result.append({'reference': reference, 'clinic': clinic, 'case': case,
                           'invoice': invoice['id'], 'number': invoice['number'], 'expected_bucket': bucket})
        response = client.get('/api/billing/receivables/')
        assert response.status_code == 200
        for item in result:
            row = next(row for row in response.data if row['clinic'] == item['clinic'])
            assert row['buckets'][item['expected_bucket']] != '0.00'
            item['buckets'] = row['buckets']
            item['total_due'] = row['total_due']
    print(json.dumps({'V1_AGING_RESULT': result}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Preparation V1 vieillissement interrompue : ' + str(error), file=sys.stderr)
        raise SystemExit(1)
